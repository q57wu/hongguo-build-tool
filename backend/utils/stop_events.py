"""独立的 stop_event 管理，每个工具一个"""
import threading


class StopEventPool:
    """每个工具类型有独立的 stop_event"""

    def __init__(self):
        self._events = {}
        self._lock = threading.Lock()

    def get(self, tool_name: str) -> threading.Event:
        """获取指定工具的 stop_event（不存在则创建）"""
        with self._lock:
            if tool_name not in self._events:
                self._events[tool_name] = threading.Event()
            return self._events[tool_name]

    def stop(self, tool_name: str):
        """停止指定工具"""
        self.get(tool_name).set()

    def clear(self, tool_name: str):
        """清除指定工具的停止标记"""
        self.get(tool_name).clear()

    def stop_all(self):
        """停止所有工具"""
        with self._lock:
            for event in self._events.values():
                event.set()


# 全局实例
stop_pool = StopEventPool()
