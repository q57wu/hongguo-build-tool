"""
事件桥接：Python 后端 → 前端 (通过 pywebview evaluate_js)
v2: 可注入 + 消息队列 + 丢失日志 + 溢出告警
"""
import json
import time
import logging
import threading
from collections import deque

_logger = logging.getLogger(__name__)


class EventBridge:
    """向前端推送实时事件的桥接器（可注入版本）"""

    def __init__(self, window=None, max_queue_size: int = 100):
        self._window = window
        self._queue = deque(maxlen=max_queue_size)  # 窗口不可用时缓存消息
        self._lock = threading.Lock()
        self._lost_count = 0

    def set_window(self, window):
        """设置 pywebview 窗口对象"""
        self._window = window
        # 窗口就绪后，发送队列中缓存的消息
        self._flush_queue()

    def _flush_queue(self):
        """将缓存的消息全部发送"""
        with self._lock:
            while self._queue:
                event_name, data = self._queue.popleft()
                self._do_emit(event_name, data)

    def _do_emit(self, event_name: str, data: dict) -> bool:
        """实际执行 evaluate_js"""
        if self._window is None:
            return False
        payload = json.dumps(data, ensure_ascii=False)
        js = f"window.dispatchEvent(new CustomEvent('honguo:{event_name}', {{detail: {payload}}}));"
        try:
            self._window.evaluate_js(js)
            return True
        except Exception as e:
            self._lost_count += 1
            _logger.warning(f"EventBridge.emit 失败 ({event_name}): {e} [累计丢失: {self._lost_count}]")
            return False

    def emit(self, event_name: str, data: dict):
        """向前端派发自定义事件（窗口不可用时缓存到队列）"""
        if self._window is None:
            with self._lock:
                before = len(self._queue)
                self._queue.append((event_name, data))
                after = len(self._queue)
                if after <= before:
                    # deque 已满，新消息被丢弃
                    _logger.warning(
                        f"EventBridge 队列已满(maxlen={self._queue.maxlen})，消息已丢弃: {event_name}"
                    )
                else:
                    _logger.debug(f"窗口未就绪，消息已缓存: {event_name} (队列长度: {after})")
            return
        if not self._do_emit(event_name, data):
            # 发送失败，也缓存
            with self._lock:
                before = len(self._queue)
                self._queue.append((event_name, data))
                after = len(self._queue)
                if after <= before:
                    _logger.warning(
                        f"EventBridge 队列已满(maxlen={self._queue.maxlen})，消息已丢弃: {event_name}"
                    )
            if self._lost_count > 0:
                # 通过前端推送一条警告日志，告知消息丢失
                self._do_emit("log", {
                    "message": f"⚠️ EventBridge 累计丢失 {self._lost_count} 条消息",
                    "level": "warn",
                    "time": time.time(),
                })

    def emit_log(self, message: str, level: str = "info"):
        """推送日志消息"""
        self.emit("log", {
            "message": str(message),
            "level": level,
            "time": time.time(),
        })

    def emit_build_status(self, status: str, extra: dict = None):
        """推送搭建状态变化"""
        data = {"status": status}
        if extra:
            data.update(extra)
        self.emit("build-status", data)

        # 搭建完成时，自动标记对应的每日任务为已完成
        if status == "completed" and extra and extra.get("profile"):
            self._auto_complete_daily_task(extra["profile"])

    def _auto_complete_daily_task(self, profile_key: str):
        """搭建完成后自动在每日任务中勾选对应的任务"""
        try:
            from datetime import date as dt_date
            from backend.services.daily_task_service import get_tasks, toggle_task
            today = dt_date.today().isoformat()
            tasks = get_tasks(today)
            for task in tasks:
                if task.get("profile_key") == profile_key and not task.get("done"):
                    toggle_task(today, task["id"])
                    break
        except Exception:
            pass  # 非关键功能，静默失败

    def on_drama_completed(self, profile_key: str, drama_name: str):
        """单部剧搭建成功时，更新每日任务的搭建计数"""
        try:
            from datetime import date as dt_date
            from backend.services.daily_task_service import increment_build_count
            today = dt_date.today().isoformat()
            result = increment_build_count(today, profile_key)
            if result:
                self.emit("drama-completed", {
                    "profile": profile_key,
                    "drama": drama_name,
                    "task_id": result["task_id"],
                    "build_count": result["build_count"],
                })
        except Exception:
            pass  # 非关键功能，静默失败

    def emit_tool_log(self, message: str):
        """推送工具页面日志"""
        self.emit("tool-log", {"message": str(message)})

    def emit_tool_done(self, exit_code: int = 0):
        """推送工具完成事件"""
        self.emit("tool-done", {"code": exit_code})

    @property
    def lost_count(self) -> int:
        """累计丢失的消息数"""
        return self._lost_count

    @property
    def queue_size(self) -> int:
        """当前队列中待发送的消息数"""
        return len(self._queue)


def create_bridge(window=None) -> EventBridge:
    """工厂函数：创建 EventBridge 实例（用于测试时注入）"""
    return EventBridge(window=window)


# 默认全局实例（向后兼容）
bridge = EventBridge()
