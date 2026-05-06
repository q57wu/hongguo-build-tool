"""后台任务注册表：集中管理所有后台线程的生命周期"""
import threading
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Callable
from enum import Enum

_logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class TaskInfo:
    task_id: str
    name: str
    status: TaskStatus = TaskStatus.PENDING
    thread: Optional[threading.Thread] = field(default=None, repr=False)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error: Optional[str] = None


class TaskRegistry:
    """线程安全的后台任务注册表"""

    def __init__(self):
        self._tasks: dict[str, TaskInfo] = {}
        self._lock = threading.Lock()
        self._counter = 0

    def register(self, name: str, target: Callable, args: tuple = ()) -> str:
        """注册并启动一个后台任务，返回 task_id"""
        with self._lock:
            self._counter += 1
            task_id = f"{name}-{self._counter:04d}"

        def _wrapper():
            with self._lock:
                task = self._tasks[task_id]
                task.status = TaskStatus.RUNNING
                task.started_at = time.time()
            try:
                target(*args)
                with self._lock:
                    task = self._tasks[task_id]
                    task.status = TaskStatus.COMPLETED
            except Exception as e:
                _logger.exception(f"任务 {task_id} 执行失败: {e}")
                with self._lock:
                    task = self._tasks[task_id]
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
            finally:
                with self._lock:
                    self._tasks[task_id].finished_at = time.time()

        t = threading.Thread(target=_wrapper, name=task_id, daemon=True)
        info = TaskInfo(task_id=task_id, name=name, thread=t)

        with self._lock:
            self._tasks[task_id] = info

        t.start()
        _logger.info(f"任务已启动: {task_id}")
        return task_id

    def get(self, task_id: str) -> Optional[TaskInfo]:
        with self._lock:
            return self._tasks.get(task_id)

    def get_all(self) -> list[TaskInfo]:
        with self._lock:
            return list(self._tasks.values())

    def get_running(self) -> list[TaskInfo]:
        with self._lock:
            return [t for t in self._tasks.values() if t.status == TaskStatus.RUNNING]

    def is_running(self, name: str) -> bool:
        """检查指定名称的任务是否正在运行"""
        with self._lock:
            return any(
                t.status == TaskStatus.RUNNING and t.name == name
                for t in self._tasks.values()
            )

    def cleanup(self, max_age: float = 3600):
        """清理已完成超过 max_age 秒的任务记录"""
        now = time.time()
        with self._lock:
            to_remove = [
                tid for tid, t in self._tasks.items()
                if t.finished_at and (now - t.finished_at) > max_age
            ]
            for tid in to_remove:
                del self._tasks[tid]
        if to_remove:
            _logger.debug(f"清理了 {len(to_remove)} 个过期任务记录")

    def stop_all(self):
        """标记所有运行中任务为停止（配合 stop_event 使用）"""
        with self._lock:
            for t in self._tasks.values():
                if t.status == TaskStatus.RUNNING:
                    t.status = TaskStatus.STOPPED
                    _logger.info(f"任务 {t.task_id} 已标记为停止")


# 全局单例
task_registry = TaskRegistry()
