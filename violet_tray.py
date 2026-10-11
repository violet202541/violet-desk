"""托盘图标与系统通知（WinForms NotifyIcon，经 pythonnet 调用，不需要额外依赖）。

关掉窗口时 Violet 退到托盘，提醒照常送达；右键菜单可以打开书桌或彻底退出。
NotifyIcon 的气泡提示在 Windows 10/11 上会显示为系统通知。
所有方法都会切到窗口的 UI 线程执行。
"""
import os


class Tray:
    def __init__(self, window, icon_path, on_open, on_quit):
        self.window = window
        self.icon_path = icon_path
        self.on_open = on_open
        self.on_quit = on_quit
        self.icon = None
        self.wanted = True  # the user's "keep in tray" preference
        self._hide_timer = None

    def _ui(self, fn):
        from System import Action
        self.window.native.BeginInvoke(Action(fn))

    def install(self, visible=True):
        self.wanted = visible
        self._ui(self._create)

    def _create(self):
        import clr  # noqa: F401
        clr.AddReference('System.Windows.Forms')
        clr.AddReference('System.Drawing')
        import System.Drawing as Drawing
        import System.Windows.Forms as WinForms

        icon = WinForms.NotifyIcon()
        if os.path.isfile(self.icon_path):
            icon.Icon = Drawing.Icon(self.icon_path)
        icon.Text = 'Violet · 书桌还亮着灯'
        menu = WinForms.ContextMenuStrip()
        for label, action in (('打开 Violet', lambda: self.on_open(None)), ('今天的书桌', lambda: self.on_open('desk')),
                              ('写回信', lambda: self.on_open('write'))):
            item = WinForms.ToolStripMenuItem(label)
            item.Click += lambda sender, args, act=action: act()
            menu.Items.Add(item)
        menu.Items.Add(WinForms.ToolStripSeparator())
        quit_item = WinForms.ToolStripMenuItem('退出 Violet')
        quit_item.Click += lambda sender, args: self.on_quit()
        menu.Items.Add(quit_item)
        icon.ContextMenuStrip = menu
        icon.MouseClick += self._clicked
        icon.BalloonTipClicked += lambda sender, args: self.on_open('desk')
        icon.Visible = self.wanted
        self.icon = icon

    def _clicked(self, sender, args):
        import System.Windows.Forms as WinForms
        if args.Button == WinForms.MouseButtons.Left:
            self.on_open(None)

    def set_visible(self, visible):
        self.wanted = bool(visible)
        if self.icon is not None:
            self._ui(lambda: setattr(self.icon, 'Visible', self.wanted))

    def notify(self, title, text):
        """Show a system notification. Without the tray preference, the icon appears just for it."""
        if self.icon is None:
            return

        def show():
            import System.Windows.Forms as WinForms
            self.icon.Visible = True
            self.icon.ShowBalloonTip(8000, title, text, getattr(WinForms.ToolTipIcon, 'None'))
            if not self.wanted:
                timer = WinForms.Timer()
                timer.Interval = 12000

                def done(sender, args):
                    timer.Stop()
                    if not self.wanted:
                        self.icon.Visible = False

                timer.Tick += done
                timer.Start()
                self._hide_timer = timer

        self._ui(show)

    def dispose(self):
        if self.icon is not None:
            icon, self.icon = self.icon, None
            try:
                icon.Visible = False
                icon.Dispose()
            except Exception:
                pass
