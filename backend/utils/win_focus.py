"""
win_focus.py - Windows 前台窗口捕获与还原工具

用于在 Playwright popup 打开后立即将前台焦点归还给原窗口，
防止 Chrome 新 tab/popup 触发 Windows 焦点策略将 Chrome 窗口抢到前台。

使用方法：
    hwnd = capture_foreground()        # click 前保存当前前台窗口
    batch_btn.click(force=True)        # 触发 popup
    popup = popup_info.value
    restore_foreground(hwnd)           # 立刻还原
"""
import ctypes
import ctypes.wintypes
import logging

_logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32


def capture_foreground() -> int:
    """
    获取当前前台窗口句柄（HWND）。
    返回 hwnd int，失败时返回 0。
    """
    try:
        hwnd = user32.GetForegroundWindow()
        return hwnd or 0
    except Exception as e:
        _logger.debug(f"capture_foreground 失败: {e}")
        return 0


def restore_foreground(hwnd: int) -> bool:
    """
    将前台焦点还原到指定 hwnd。
    Win10+ 限制：非前台线程直接 SetForegroundWindow 会被忽略，
    需先 AttachThreadInput 借用当前前台线程的权限。

    返回 True 表示成功，False 表示失败或 hwnd 无效。
    """
    if not hwnd:
        return False
    try:
        target_tid = user32.GetWindowThreadProcessId(hwnd, None)
        cur_tid = ctypes.windll.kernel32.GetCurrentThreadId()

        attached = False
        if cur_tid != target_tid:
            attached = bool(user32.AttachThreadInput(cur_tid, target_tid, True))

        try:
            user32.AllowSetForegroundWindow(0xFFFFFFFF)  # ASFW_ANY
            result = bool(user32.SetForegroundWindow(hwnd))
            if not result:
                user32.BringWindowToTop(hwnd)
            return True
        finally:
            if attached:
                user32.AttachThreadInput(cur_tid, target_tid, False)

    except Exception as e:
        _logger.debug(f"restore_foreground(hwnd={hwnd}) 失败: {e}")
        return False
