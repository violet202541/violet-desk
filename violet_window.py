"""Windows 无边框外观：去掉系统标题栏，保留原生拖动、缩放、贴边分屏、阴影与圆角。

做法：窗口保留 WS_CAPTION | WS_THICKFRAME 等样式，子类化窗口过程，在 WM_NCCALCSIZE
中把整个窗口都交给客户区（不绘制标题栏与边框）。网页里的标题区和边缘在按下鼠标时，
请求系统进入自己的移动 / 缩放循环（WM_NCLBUTTONDOWN + HTCAPTION / HTLEFT …），
因此 Aero Snap、Win11 贴靠布局和系统动画都照常工作。

任何一步失败都会抛出异常，由调用方退回普通窗口。
"""
import ctypes
from ctypes import wintypes as wt

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

GWL_STYLE = -16
GWLP_WNDPROC = -4
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU = 0x00080000
WM_NCCALCSIZE = 0x0083
WM_NCACTIVATE = 0x0086
WM_NCLBUTTONDOWN = 0x00A1
WM_SYSCOMMAND = 0x0112
SC_MINIMIZE, SC_MAXIMIZE, SC_RESTORE, SC_CLOSE = 0xF020, 0xF030, 0xF120, 0xF060
SWP_FLAGS = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020  # NOSIZE NOMOVE NOZORDER NOACTIVATE FRAMECHANGED
SM_CXFRAME, SM_CYFRAME, SM_CXPADDEDBORDER = 32, 33, 92
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2

HIT = {'caption': 2, 'left': 10, 'right': 11, 'top': 12, 'topleft': 13, 'topright': 14,
       'bottom': 15, 'bottomleft': 16, 'bottomright': 17}

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = (wt.HWND, ctypes.c_int)
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = (wt.HWND, ctypes.c_int, ctypes.c_ssize_t)
user32.CallWindowProcW.restype = LRESULT
user32.CallWindowProcW.argtypes = (ctypes.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
user32.SendMessageW.restype = LRESULT
user32.SendMessageW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
user32.PostMessageW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
user32.SetWindowPos.argtypes = (wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT)
user32.IsZoomed.argtypes = (wt.HWND,)
user32.GetDpiForWindow.argtypes = (wt.HWND,)
user32.GetSystemMetricsForDpi.argtypes = (ctypes.c_int, wt.UINT)


class NCCALCSIZE_PARAMS(ctypes.Structure):
    _fields_ = [('rgrc', wt.RECT * 3), ('lppos', ctypes.c_void_p)]


class NativeFrame:
    def __init__(self, hwnd):
        self.hwnd = wt.HWND(hwnd)
        self._previous = None
        self._proc = None

    def install(self):
        """Run on the window's UI thread."""
        style = user32.GetWindowLongPtrW(self.hwnd, GWL_STYLE)
        style |= WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU
        user32.SetWindowLongPtrW(self.hwnd, GWL_STYLE, style)
        self._proc = WNDPROC(self._wndproc)
        self._previous = user32.SetWindowLongPtrW(self.hwnd, GWLP_WNDPROC,
                                                  ctypes.cast(self._proc, ctypes.c_void_p).value)
        if not self._previous:
            raise OSError('无法挂接窗口过程')
        preference = ctypes.c_int(DWMWCP_ROUND)
        dwmapi.DwmSetWindowAttribute(self.hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(preference),
                                     ctypes.sizeof(preference))
        user32.SetWindowPos(self.hwnd, None, 0, 0, 0, 0, SWP_FLAGS)

    def _frame(self):
        dpi = user32.GetDpiForWindow(self.hwnd) or 96
        pad = user32.GetSystemMetricsForDpi(SM_CXPADDEDBORDER, dpi)
        return (user32.GetSystemMetricsForDpi(SM_CXFRAME, dpi) + pad,
                user32.GetSystemMetricsForDpi(SM_CYFRAME, dpi) + pad)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_NCCALCSIZE and wparam:
                if user32.IsZoomed(hwnd):
                    # A maximised window extends past the monitor by its frame; pull the client back in.
                    fx, fy = self._frame()
                    rect = ctypes.cast(lparam, ctypes.POINTER(NCCALCSIZE_PARAMS)).contents.rgrc[0]
                    rect.left += fx
                    rect.right -= fx
                    rect.top += fy
                    rect.bottom -= fy
                return 0
            if msg == WM_NCACTIVATE:
                # Skip non-client repainting so no caption flashes when focus changes.
                return user32.CallWindowProcW(self._previous, hwnd, msg, wparam, -1)
        except Exception:
            pass
        return user32.CallWindowProcW(self._previous, hwnd, msg, wparam, lparam)

    # ------------------------------------------------------------ actions (UI thread)

    def begin(self, edge):
        """Hand the pressed mouse button to the system move / resize loop."""
        hit = HIT.get(edge)
        if hit is None:
            return
        if hit != HIT['caption'] and self.maximized:
            return
        user32.ReleaseCapture()
        user32.SendMessageW(self.hwnd, WM_NCLBUTTONDOWN, hit, 0)

    def command(self, action):
        code = {'minimize': SC_MINIMIZE, 'maximize': SC_MAXIMIZE, 'restore': SC_RESTORE, 'close': SC_CLOSE}.get(action)
        if action == 'toggle':
            code = SC_RESTORE if self.maximized else SC_MAXIMIZE
        if code:
            user32.PostMessageW(self.hwnd, WM_SYSCOMMAND, code, 0)

    @property
    def maximized(self):
        return bool(user32.IsZoomed(self.hwnd))
