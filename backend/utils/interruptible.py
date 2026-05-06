"""
可中断等待工具：把 Playwright 的长 wait 拆成短 poll，让 stop_event 能秒级生效。

用法：
    from backend.utils.interruptible import StopRequested, sleep_ms, wait_for_visible, wait_for_hidden

    sleep_ms(page, 2000, stop_event)                       # 替代 page.wait_for_timeout(2000)
    wait_for_visible(locator, timeout=10_000, stop_event)  # 替代 locator.wait_for(state='visible', timeout=10_000)
    wait_for_hidden(locator, timeout=120_000, stop_event)  # 替代 locator.wait_for(state='hidden', timeout=120_000)

任何一个等待中检测到 stop_event 被 set，立刻抛 StopRequested。调用方在最外层 try/except 捕获即可干净退出。
"""
import time
import logging

_logger = logging.getLogger(__name__)


class StopRequested(Exception):
    """工具被外部 stop_event 中断时抛出。

    注意：此类与 backend.core.exceptions.StopRequested 功能相同。
    tool_adapter 中两者均可被 except Exception 捕获，不会穿透。
    保留独立定义以避免 interruptible 模块对 core 的循环依赖。
    """


_POLL_MS = 200  # 轮询间隔（毫秒）；停止响应延迟最坏 ~200ms


def _check(stop_event):
    if stop_event is not None and stop_event.is_set():
        raise StopRequested()


def sleep_ms(page, total_ms: int, stop_event=None, poll_ms: int = _POLL_MS):
    """可中断的 page.wait_for_timeout 替代品。"""
    if total_ms <= 0:
        _check(stop_event)
        return
    deadline = time.monotonic() + total_ms / 1000.0
    while True:
        _check(stop_event)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        step = min(poll_ms, int(remaining * 1000))
        if step <= 0:
            return
        try:
            page.wait_for_timeout(step)
        except Exception as e:
            # page 已关闭等情况，直接退出循环交给上层处理
            _logger.debug(f"sleep_ms: page.wait_for_timeout 异常(已忽略): {e}")
            return


def wait_for_state(locator, state: str, timeout: int, stop_event=None, poll_ms: int = _POLL_MS):
    """
    可中断版 locator.wait_for(state=..., timeout=...)。
    把一次长等待切成多段短等待，每段之间检查 stop_event。
    超时仍然抛 PlaywrightTimeout，停止抛 StopRequested。
    """
    from playwright.sync_api import TimeoutError as PWTimeout
    if timeout <= 0:
        timeout = 1
    deadline = time.monotonic() + timeout / 1000.0
    last_exc = None
    while True:
        _check(stop_event)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            if last_exc:
                raise last_exc
            raise PWTimeout(f"wait_for(state={state!r}) timed out")
        step = min(poll_ms, int(remaining * 1000))
        if step <= 0:
            step = 1
        try:
            locator.wait_for(state=state, timeout=step)
            return
        except PWTimeout as e:
            last_exc = e
            # 继续轮询直到外层 deadline


def wait_for_visible(locator, timeout: int, stop_event=None, poll_ms: int = _POLL_MS):
    return wait_for_state(locator, "visible", timeout, stop_event, poll_ms)


def wait_for_hidden(locator, timeout: int, stop_event=None, poll_ms: int = _POLL_MS):
    return wait_for_state(locator, "hidden", timeout, stop_event, poll_ms)


def check_stop(stop_event):
    """暴露给业务代码做主动检测点，例如循环内每一步都调一下。"""
    _check(stop_event)
