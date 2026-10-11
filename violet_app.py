#!/usr/bin/env python3
"""Violet 桌面入口：启动本地服务并打开 pywebview 窗口。

  python violet_app.py            # 桌面窗口（关掉窗口会退到托盘，可在设置里关闭）
  python violet_app.py --browser  # 在默认浏览器中打开（无需 pywebview）
  python violet_app.py --serve --port 8765  # 只启动服务，供前端开发代理

个人数据统一放在 %APPDATA%\\Violet（可用环境变量 VIOLET_DATA_DIR 改到别处）；
第一次启动时把旧版放在程序旁边的设置、记录与来信复制过去，原文件保留。
"""
import argparse
import ctypes
import json
import os
import sys
import threading
import time
import urllib.request
import webbrowser

import violet_core
from violet_core import APP_NAME, DATA_DIR, migrate_legacy
from violet_server import VioletServer, VioletService

if getattr(sys, 'frozen', False):
    ICON = os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(sys.executable)), 'tools', 'violet.ico')
else:
    ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools', 'violet.ico')
INSTANCE_FILE = DATA_DIR / 'instance.json'


APP_MUTEX = 'VioletRunning'  # the installer's AppMutex: setup and uninstall wait until Violet is closed
_mutex = None


def _windows_identity():
    """Group the taskbar button under Violet instead of python.exe."""
    global _mutex
    if os.name == 'nt':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Violet')  # also the sender name on notifications
            _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, APP_MUTEX)
        except Exception:
            pass


def _apply_icon(window):
    if os.name != 'nt' or not os.path.isfile(ICON):
        return
    try:
        import ctypes
        hwnd = window.native.Handle.ToInt64()
        user32 = ctypes.windll.user32
        user32.LoadImageW.restype = ctypes.c_void_p
        user32.SendMessageW.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p)
        for which, size in ((0, 16), (1, 32)):  # ICON_SMALL, ICON_BIG
            handle = user32.LoadImageW(None, ICON, 1, size, size, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
            if handle:
                user32.SendMessageW(ctypes.c_void_p(hwnd), 0x80, which, ctypes.c_void_p(handle))  # WM_SETICON
    except Exception:
        pass


# ---------------------------------------------------------------- single instance

def wake_running_instance():
    """If Violet is already running (perhaps hidden in the tray), bring it forward and return True."""
    try:
        info = json.loads(INSTANCE_FILE.read_text(encoding='utf-8'))
        request = urllib.request.Request(
            f'http://127.0.0.1:{int(info["port"])}/api/window', method='POST',
            data=json.dumps({'action': 'show'}).encode(),
            headers={'X-Violet-Token': info['token'], 'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.status == 200
    except Exception:
        return False


def claim_instance(server):
    try:
        INSTANCE_FILE.parent.mkdir(parents=True, exist_ok=True)
        violet_core._write_json(INSTANCE_FILE, {'port': server.server_address[1], 'token': server.service.token,
                                                'pid': os.getpid(), 'time': time.time()})
    except OSError:
        pass


def release_instance():
    try:
        info = json.loads(INSTANCE_FILE.read_text(encoding='utf-8'))
        if info.get('pid') == os.getpid():
            INSTANCE_FILE.unlink()
    except (OSError, ValueError):
        pass


# ---------------------------------------------------------------- window

def portal_login(webview, url, done, title, timeout=600):
    """鸿雁: show a school's own login page in its own window. The user types the password there;
    once the page reaches the portal (`done`, a regex on the address) only the cookies are kept."""
    import re

    finished = threading.Event()
    result = {}
    win = webview.create_window(title, url, width=980, height=720, min_size=(640, 520))

    def watch():
        deadline = time.time() + timeout
        while not finished.is_set() and time.time() < deadline:
            time.sleep(0.6)
            try:
                current = win.get_current_url() or ''
            except Exception:
                continue
            if re.match(done, current):
                time.sleep(1.2)  # let the portal set its own session cookies
                cookies = []
                for jar in win.get_cookies() or []:
                    for name, morsel in jar.items():
                        cookies.append({'name': name, 'value': morsel.value, 'domain': morsel['domain'] or '',
                                        'path': morsel['path'] or '/'})
                result['cookies'] = cookies
                try:
                    win.destroy()
                except Exception:
                    pass
                break
        finished.set()

    win.events.closed += lambda: finished.set()
    threading.Thread(target=watch, name='violet-login', daemon=True).start()
    finished.wait(timeout + 5)
    return result.get('cookies')


def run_window(server, service):
    import webview

    _windows_identity()
    # WinForms must believe the form is borderless, otherwise every maximise / restore cycle
    # re-adds the old border thickness. NativeFrame then restores the native styles underneath.
    custom_frame = os.name == 'nt' and not os.environ.get('VIOLET_SYSTEM_FRAME')
    window = webview.create_window(APP_NAME, server.url, width=1320, height=860, min_size=(980, 660),
                                   background_color='#F3ECDF', text_select=False,
                                   frameless=custom_frame, easy_drag=False)
    state = {'native': None, 'tray': None, 'hinted': False}
    quitting = threading.Event()

    def on_ui_thread(fn):
        from System import Action
        window.native.BeginInvoke(Action(fn))

    def install_frame():
        try:
            from violet_window import NativeFrame
            native = NativeFrame(window.native.Handle.ToInt64())
            native.install()
            state['native'] = native
            service.window_state['frameless'] = True
            service.bus.publish('window', dict(service.window_state))
        except Exception as error:  # Fall back to the ordinary system frame.
            print(f'自绘标题栏不可用，使用系统窗口：{error}', file=sys.stderr, flush=True)
            try:
                import System.Windows.Forms as WinForms
                window.native.FormBorderStyle = WinForms.FormBorderStyle.Sizable
            except Exception:
                pass

    def bring_forward(view=None):
        def front():
            import System.Windows.Forms as WinForms
            form = window.native
            form.Show()
            if form.WindowState == WinForms.FormWindowState.Minimized:
                form.WindowState = WinForms.FormWindowState.Normal
            form.Activate()
        try:
            on_ui_thread(front)
        except Exception:
            window.show()
        if view:
            service.bus.publish('navigate', {'view': view})

    def quit_app():
        quitting.set()
        state['close_lyrics']()
        threading.Thread(target=window.destroy, daemon=True).start()

    def install_tray():
        if os.name != 'nt':
            return
        try:
            from violet_tray import Tray
            tray = Tray(window, ICON, bring_forward, quit_app)
            tray.install(service.settings.tray)
            state['tray'] = tray
            service.hooks['tray'] = tray.set_visible
            service.hooks['notify'] = tray.notify
        except Exception as error:
            print(f'托盘不可用：{error}', file=sys.stderr, flush=True)

    def on_shown():
        _apply_icon(window)
        if custom_frame:
            on_ui_thread(install_frame)
        install_tray()
        if service.settings.desktop_lyrics and service.hooks.get('lyrics'):
            service.hooks['lyrics'](service.settings)

    def window_action(action, edge=None):
        if action == 'show':
            return bring_forward()
        native = state['native']
        if native is None:
            raise RuntimeError('当前使用系统标题栏')
        if action == 'begin':
            on_ui_thread(lambda: native.begin(edge))
        else:
            on_ui_thread(lambda: native.command(action))

    def publish_size(maximized):
        service.window_state['maximized'] = maximized
        service.bus.publish('window', dict(service.window_state))

    window.events.shown += on_shown
    window.events.maximized += lambda: publish_size(True)
    window.events.restored += lambda: publish_size(False)
    service.hooks['window'] = window_action

    def pick_folder(initial):
        result = window.create_file_dialog(webview.FOLDER_DIALOG, directory=initial or '')
        return result[0] if result else ''

    def pick_image():
        result = window.create_file_dialog(webview.OPEN_DIALOG, file_types=('图片 (*.png;*.jpg;*.jpeg;*.webp)',))
        return result[0] if result else ''

    def save_file(name):
        result = window.create_file_dialog(webview.SAVE_DIALOG, save_filename=name, file_types=('PNG 图片 (*.png)',))
        if isinstance(result, (list, tuple)):
            result = result[0] if result else ''
        return result or ''

    service.hooks['save_file'] = save_file

    # ---------------------------------------------------------------- 桌面歌词
    lyrics = {'win': None}
    KEY = (1, 1, 1)  # the colour the desktop shows through

    def lyrics_native(fn):
        win = lyrics['win']
        if not win or not win.native:
            return
        from System import Action
        try:
            win.native.BeginInvoke(Action(fn))
        except Exception:
            pass

    def lyrics_clickthrough(locked):
        def apply():
            hwnd = lyrics['win'].native.Handle.ToInt64()
            user32 = ctypes.windll.user32
            user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
            style = user32.GetWindowLongPtrW(ctypes.c_void_p(hwnd), -20)
            WS_EX_TRANSPARENT, WS_EX_LAYERED = 0x20, 0x80000
            style = (style | WS_EX_TRANSPARENT | WS_EX_LAYERED) if locked else (style & ~WS_EX_TRANSPARENT) | WS_EX_LAYERED
            user32.SetWindowLongPtrW(ctypes.c_void_p(hwnd), -20, ctypes.c_ssize_t(style))
        lyrics_native(apply)

    def lyrics_loaded():
        def key():
            from System.Drawing import Color
            form = lyrics['win'].native
            form.BackColor = Color.FromArgb(255, *KEY)
            form.TransparencyKey = Color.FromArgb(255, *KEY)
        lyrics_native(key)
        lyrics_clickthrough(service.settings.lyrics_locked)

    def lyrics_moved(x, y):
        if lyrics['win'] is not None:
            state['lyrics_pos'] = [int(x), int(y)]

    def open_lyrics():
        if lyrics['win'] is not None:
            return
        width, height = 860, 170
        pos = service.settings.lyrics_pos
        if len(pos) == 2:
            x, y = pos
        else:
            # Bottom centre of the screen the main window is on (the first screen listed is not always the primary).
            screens = webview.screens or []
            cx, cy = (window.x or 0) + (window.width or 0) // 2, (window.y or 0) + (window.height or 0) // 2
            screen = next((sc for sc in screens if sc.x <= cx < sc.x + sc.width and sc.y <= cy < sc.y + sc.height),
                          next((sc for sc in screens if sc.x == 0 and sc.y == 0), screens[0] if screens else None))
            x = int(screen.x + (screen.width - width) / 2) if screen else 300
            y = int(screen.y + screen.height - height - 110) if screen else 700
        win = webview.create_window('Violet · 桌面歌词', server.url + '&view=lyrics', width=width, height=height,
                                    x=x, y=y, frameless=True, easy_drag=True, on_top=True, transparent=True,
                                    shadow=False, focus=False, resizable=False, background_color='#010101')
        lyrics['win'] = win
        win.events.loaded += lyrics_loaded
        win.events.moved += lyrics_moved

        def closed():
            lyrics['win'] = None
            if service.settings.desktop_lyrics and not quitting.is_set():
                service.update_settings({'desktop_lyrics': False})
        win.events.closed += closed

    def close_lyrics():
        win, lyrics['win'] = lyrics['win'], None
        if win is not None:
            if state.get('lyrics_pos'):
                service.update_settings({'lyrics_pos': state.pop('lyrics_pos')})
            win.destroy()

    def sync_lyrics(settings):
        if settings.desktop_lyrics:
            if lyrics['win'] is None:
                open_lyrics()
            else:
                lyrics_clickthrough(settings.lyrics_locked)
        else:
            close_lyrics()

    service.hooks['lyrics'] = lambda settings: threading.Thread(target=sync_lyrics, args=(settings,), daemon=True).start()
    state['close_lyrics'] = close_lyrics
    service.hooks['pick_folder'] = pick_folder
    service.hooks['pick_image'] = pick_image
    service.hooks['login'] = lambda url, done, title: portal_login(webview, url, done, title)

    def on_closing():
        tray = state['tray']
        if not quitting.is_set() and tray is not None and service.settings.tray:
            # Close means "put the desk lamp on low": hide to the tray, reminders keep coming.
            threading.Thread(target=window.hide, daemon=True).start()
            if not state['hinted']:
                state['hinted'] = True
                tray.notify('Violet 还在托盘里', '提醒和下载会继续。右键托盘图标可以彻底退出。')
            return False
        active = service.downloads.active()
        if active and not window.create_confirmation_dialog(
                '还有信件在路上', f'仍有 {len(active)} 封信正在寄送或排队。\n现在退出会撤回它们，确定离开吗？'):
            quitting.clear()
            return False
        if tray is not None:
            tray.dispose()
        quitting.set()  # the lyrics strip closes with the app, but stays switched on for next time
        state['close_lyrics']()
        return True

    window.events.closing += on_closing
    storage = os.environ.get('VIOLET_WEBVIEW_DIR') or os.path.join(os.path.expanduser('~'), '.violet_webview')
    webview.start(private_mode=False, storage_path=storage)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='violet', description='Violet · 音乐、书信与书桌')
    parser.add_argument('--browser', action='store_true', help='在默认浏览器中打开')
    parser.add_argument('--serve', action='store_true', help='只启动本地服务（开发用）')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--token', help='固定令牌（仅开发用）')
    args = parser.parse_args(argv)

    desktop = not args.serve and not args.browser
    if desktop and wake_running_instance():
        return 0
    try:
        source = migrate_legacy()
        if source:
            print(f'已把旧数据从 {source} 复制到 {DATA_DIR}（原文件保留）', flush=True)
    except OSError as error:
        print(f'旧数据搬迁失败，仍从空白开始：{error}', file=sys.stderr, flush=True)

    service = VioletService()
    if args.token:
        service.token = args.token
    server = VioletServer(service, args.port)
    server.start()
    service.start_background()
    try:
        if args.serve:
            print(f'Violet 服务已启动：{server.url}', flush=True)
            threading.Event().wait()
        elif args.browser:
            webbrowser.open(server.url)
            print(f'已在浏览器打开 {server.url}\n按 Ctrl+C 退出', flush=True)
            threading.Event().wait()
        else:
            try:
                import webview  # noqa: F401
            except ImportError as error:
                webbrowser.open(server.url)
                print(f'无法载入 pywebview（{error}），已改用浏览器打开。安装：python -m pip install pywebview', flush=True)
                threading.Event().wait()
            else:
                claim_instance(server)
                run_window(server, service)
    except KeyboardInterrupt:
        pass
    finally:
        release_instance()
        try:
            service.backup_if_changed()
        except Exception as error:
            print(f'退出时的备份没有完成：{error}', file=sys.stderr, flush=True)
        server.stop()
        service.desk.close()


if __name__ == '__main__':
    sys.exit(main())
