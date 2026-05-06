"""
搭建引擎：封装 run_build / run_build_incentive 的线程管理
"""
import threading
import traceback
from backend.bridge import bridge
from backend.core.exceptions import StopRequested


class BuildEngine:
    def __init__(self):
        self._stop_event = threading.Event()
        self._running = False
        self._lock = threading.Lock()
        self._current_profile = None
        self._progress = {}

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def current_profile(self) -> str:
        return self._current_profile

    @property
    def progress(self) -> dict:
        return self._progress

    def run(self, profile_key: str):
        with self._lock:
            self._running = True
        self._current_profile = profile_key
        self._stop_event.clear()
        self._progress = {"step": 0, "total": 0, "message": "初始化..."}
        bridge.emit_build_status("running", {"profile": profile_key})

        try:
            from backend.build_adapter import run_build_task
            run_build_task(
                profile_key=profile_key,
                log_callback=bridge.emit_log,
                stop_event=self._stop_event,
                progress_callback=self._update_progress,
            )
            bridge.emit_build_status("completed", {"profile": profile_key})
        except Exception as e:
            bridge.emit_log(f"❌ 搭建失败: {e}", "error")
            bridge.emit_build_status("error", {"message": str(e)})
            traceback.print_exc()
        finally:
            with self._lock:
                self._running = False
            self._current_profile = None

    def run_parallel(self, profile_key: str, max_workers: int = 3):
        """并行搭建：使用多线程并行执行搭建任务以提升效率"""
        if self._running:
            return

        with self._lock:
            self._running = True
            self._stop_event = threading.Event()

        self._current_profile = profile_key
        self._stop_event.clear()
        self._progress = {"step": 0, "total": 0, "message": "初始化并行搭建..."}
        bridge.emit_build_status("running", {"profile": profile_key, "parallel": True})

        try:
            from backend.core.constants import ALL_PROFILES
            is_incentive = ALL_PROFILES.get(profile_key, {}).get("incentive", False)
            if is_incentive:
                from backend.build_adapter import run_build_task_parallel_incentive
                run_build_task_parallel_incentive(
                    profile_key,
                    log_callback=bridge.emit_log,
                    stop_event=self._stop_event,
                    max_workers=max_workers,
                )
            else:
                from backend.build_adapter import run_build_task_parallel
                run_build_task_parallel(
                    profile_key,
                    log_callback=bridge.emit_log,
                    stop_event=self._stop_event,
                    max_workers=max_workers,
                )
            bridge.emit_build_status("completed", {"profile": profile_key})
        except StopRequested:
            bridge.emit_log("⏹ 搭建已停止", "warn")
            bridge.emit_build_status("stopped", {"profile": profile_key})
        except Exception as e:
            bridge.emit_log(f"❌ 并行搭建失败: {e}", "error")
            bridge.emit_build_status("error", {"message": str(e)})
            traceback.print_exc()
        finally:
            with self._lock:
                self._running = False
            self._current_profile = None

    def stop(self):
        with self._lock:
            running = self._running
        if running:
            self._stop_event.set()
            bridge.emit_build_status("stopping")
            bridge.emit_log("⏹ 正在停止...", "warn")
        from backend.task_registry import task_registry
        task_registry.cleanup()

    def run_resume(self, progress: dict):
        """从断点续传搭建"""
        profile_key = progress["profile"]
        with self._lock:
            self._running = True
        self._current_profile = profile_key
        self._stop_event.clear()
        pending = progress.get("pending", [])
        completed = progress.get("completed", [])
        total = len(progress.get("total_accounts", []))
        self._progress = {"step": len(completed), "total": total, "message": f"续传中...剩余 {len(pending)} 个账户"}
        bridge.emit_build_status("running", {"profile": profile_key, "resumed": True})

        try:
            from backend.build_adapter import run_build_task
            run_build_task(
                profile_key=profile_key,
                log_callback=bridge.emit_log,
                stop_event=self._stop_event,
                progress_callback=self._update_progress,
                resume_accounts=pending,  # 传入待续传的账户列表
            )
            bridge.emit_build_status("completed", {"profile": profile_key})
            # 清除进度文件
            from backend.services.build_progress import clear_progress
            clear_progress()
        except Exception as e:
            bridge.emit_log(f"❌ 续传搭建失败: {e}", "error")
            bridge.emit_build_status("error", {"message": str(e)})
            import traceback
            traceback.print_exc()
        finally:
            with self._lock:
                self._running = False
            self._current_profile = None

    def _update_progress(self, step, total, message):
        self._progress = {"step": step, "total": total, "message": message}
        bridge.emit("build-progress", self._progress)
