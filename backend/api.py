"""
JS Bridge API：暴露给前端的所有 Python 方法
前端通过 window.pywebview.api.xxx() 调用
"""
import threading
from backend.task_registry import task_registry
from backend.config_manager import (
    load_config, save_config,
    load_build_records, load_material_history, save_material_history,
)
from backend.build_engine import BuildEngine
from backend.bridge import bridge


class Api:
    def __init__(self):
        self._engine = BuildEngine()
        from backend.utils.stop_events import stop_pool
        self._stop_pool = stop_pool

    def shutdown(self):
        """释放资源，清理过期任务记录"""
        task_registry.cleanup()

    # ═══ 配置管理 ═══

    def get_config(self) -> dict:
        try:
            cfg = load_config()
            return {"ok": True, "data": cfg}
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("get_config 失败")
            return {"ok": False, "error": str(e), "data": {}}

    def get_raw_config(self) -> dict:
        """直接读取 config.json 原始内容（不经过旧模块过滤）"""
        try:
            import json
            from backend.config_manager import CONFIG_FILE
            if CONFIG_FILE.exists():
                return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return {}
        except Exception as e:
            return {"error": str(e)}

    def save_config(self, cfg: dict) -> dict:
        try:
            save_config(cfg)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_profiles(self) -> list:
        cfg = load_config()
        return list(cfg.get("profiles", {}).keys())

    def get_profile(self, key: str) -> dict:
        cfg = load_config()
        return cfg.get("profiles", {}).get(key, {})

    def update_profile(self, key: str, data: dict) -> dict:
        cfg = load_config()
        cfg.setdefault("profiles", {})[key] = data
        save_config(cfg)
        return {"ok": True}

    # ═══ 浏览器管理 ═══

    def check_browser(self) -> dict:
        """检查浏览器 CDP 连接状态"""
        from backend.services.browser_service import is_cdp_available, get_cdp_info
        available = is_cdp_available()
        info = get_cdp_info() if available else {}
        return {
            "connected": available,
            "browser": info.get("Browser", ""),
            "endpoint": f"http://127.0.0.1:9222" if available else "",
        }

    def launch_browser(self) -> dict:
        """在后台线程启动浏览器调试模式，立即返回；结果通过 EventBridge 推送。

        前端监听 ``honguo:browser_ready`` / ``honguo:browser_error`` 获取结果。
        """
        from backend.services.browser_service import launch_chrome_async
        launch_chrome_async()
        return {"ok": True, "message": "正在启动浏览器，请稍候…"}

    # ═══ 搭建控制 ═══

    def start_build(self, profile_key: str, parallel: bool = False, max_workers: int = 3) -> dict:
        if self._engine.is_running:
            return {"ok": False, "error": "搭建正在运行中"}
        if parallel:
            threading.Thread(target=self._engine.run_parallel, args=(profile_key, max_workers), daemon=True).start()
        else:
            threading.Thread(target=self._engine.run, args=(profile_key,), daemon=True).start()
        return {"ok": True}

    def start_build_parallel(self, profile_key: str, max_workers: int = 3) -> dict:
        if self._engine.is_running:
            return {"ok": False, "error": "搭建正在运行中"}
        threading.Thread(target=self._engine.run_parallel, args=(profile_key, max_workers), daemon=True).start()
        return {"ok": True}

    def stop_build(self) -> dict:
        self._engine.stop()
        return {"ok": True}

    def get_build_status(self) -> dict:
        return {
            "running": self._engine.is_running,
            "profile": self._engine.current_profile,
            "progress": self._engine.progress,
        }

    # ═══ 数据查询 ═══

    def get_build_records(self) -> dict:
        try:
            return {"ok": True, "data": load_build_records()}
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("get_build_records 失败")
            return {"ok": False, "error": str(e), "data": {}}

    def get_material_history(self) -> list:
        try:
            return load_material_history()
        except Exception:
            return []

    def delete_material_history(self, index: int) -> dict:
        try:
            history = load_material_history()
            if 0 <= index < len(history):
                history.pop(index)
                save_material_history(history)
                return {"ok": True}
            return {"ok": False, "error": "索引超出范围"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def clear_material_history(self) -> dict:
        try:
            save_material_history([])
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ═══ 剧单管理 ═══

    def get_drama_titles(self) -> list:
        cfg = load_config()
        return cfg.get("common", {}).get("drama_titles", [])

    def append_drama_titles(self, titles: list) -> dict:
        try:
            cfg = load_config()
            common = cfg.setdefault("common", {})
            existing = set(common.get("drama_titles", []))
            new_titles = [t.strip() for t in titles if t.strip() and t.strip() not in existing]
            common.setdefault("drama_titles", []).extend(new_titles)
            save_config(cfg)
            return {"ok": True, "added": len(new_titles)}
        except Exception as e:
            return {"ok": False, "error": str(e), "added": 0}

    def add_result_to_profile(self, profile_key: str, result_text: str) -> dict:
        """将批量分配结果解析并写入指定profile的groups"""
        try:
            from backend.tool_adapter import parse_and_add_to_profile
            return parse_and_add_to_profile(profile_key, result_text)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def add_incentive_result_to_profile(self, profile_key: str, result_text: str) -> dict:
        """将激励链接分配结果写入指定profile"""
        try:
            from backend.tool_adapter import add_incentive_groups_to_profile
            return add_incentive_groups_to_profile(profile_key, result_text)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ═══ 工具函数 ═══

    def _run_tool_in_thread(self, tool_name: str, func, *args):
        """通用：在后台线程运行工具函数（由 task_registry 统一管理）"""
        self._stop_pool.clear(tool_name)
        def _worker(*_args):
            try:
                func(*_args)
                bridge.emit_tool_done(0)
            except Exception as e:
                bridge.emit_tool_log(f"❌ 执行失败: {e}")
                bridge.emit_tool_done(-1)
        task_registry.register(tool_name, _worker, args=args)
        return {"ok": True}

    def batch_assign(self, account_ids_text: str, dramas_text: str,
                     ids_per_group: int, dramas_per_group: int,
                     material_ids_text: str = '', spacing: int = 1) -> dict:
        try:
            from backend.tool_adapter import do_batch_assign
            return do_batch_assign(account_ids_text, dramas_text, ids_per_group, dramas_per_group,
                                   material_ids_text, spacing)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def generate_promo_chain(self, drama_names: list, directions: list) -> dict:
        from backend.tool_adapter import do_promo_chain
        stop_event = self._stop_pool.get("promo_chain")
        return self._run_tool_in_thread("promo_chain", do_promo_chain, drama_names, directions, bridge.emit_tool_log, stop_event)

    def stop_promo_chain(self) -> dict:
        self._stop_pool.stop("promo_chain")
        return {"ok": True}

    def split_promo_links(self, mode: str = "normal", drama_filter: list = None) -> dict:
        from backend.tool_adapter import do_promo_split
        stop_event = self._stop_pool.get("promo_split")
        return self._run_tool_in_thread("promo_split", do_promo_split, mode, bridge.emit_tool_log, bridge, stop_event, drama_filter or [])

    def split_incentive_links(self) -> dict:
        from backend.tool_adapter import do_incentive_split
        stop_event = self._stop_pool.get("incentive_split")
        return self._run_tool_in_thread("incentive_split", do_incentive_split, bridge.emit_tool_log, bridge, stop_event)

    def search_material_push(self, drama_names_text: str, account_id: str) -> dict:
        from backend.tool_adapter import do_material_push
        names = [n.strip() for n in drama_names_text.split('\n') if n.strip()]
        stop_event = self._stop_pool.get("material_push")
        return self._run_tool_in_thread("material_push", do_material_push, names, account_id, bridge.emit_tool_log, stop_event)

    def stop_material_push(self) -> dict:
        self._stop_pool.stop("material_push")
        return {"ok": True}

    def generate_incentive_chain(self, params: dict) -> dict:
        from backend.tool_adapter import do_incentive_chain
        stop_event = self._stop_pool.get("incentive_chain")
        return self._run_tool_in_thread(
            "incentive_chain", do_incentive_chain, params.get("count", 10), params.get("suffix", "每留"),
            bridge.emit_tool_log, stop_event)

    def stop_incentive_chain(self) -> dict:
        self._stop_pool.stop("incentive_chain")
        return {"ok": True}

    def start_incentive_push(self, account_id: str, config: dict) -> dict:
        from backend.tool_adapter import do_incentive_push
        stop_event = self._stop_pool.get("incentive_push")
        return self._run_tool_in_thread("incentive_push", do_incentive_push, account_id, bridge.emit_tool_log, stop_event)

    def stop_incentive_push(self) -> dict:
        self._stop_pool.stop("incentive_push")
        return {"ok": True}

    def crawl_material_ids(self, drama_names: list, min_cost: float = 1000, min_count: int = 6) -> dict:
        from backend.tool_adapter import do_crawl_material
        stop_event = self._stop_pool.get("crawl_material")
        return self._run_tool_in_thread(
            "crawl_material", do_crawl_material, drama_names, min_cost, min_count,
            bridge.emit_tool_log, stop_event)

    def stop_crawl_material(self) -> dict:
        self._stop_pool.stop("crawl_material")
        return {"ok": True}

    def process_incentive_links(self, params: dict) -> dict:
        try:
            from backend.tool_adapter import do_incentive_link_assign
            return do_incentive_link_assign(params)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def rta_set(self, drama_type: str, aadvids: list) -> dict:
        """RTA 设置 — 批量设置生效范围"""
        from backend.tool_adapter import do_rta_set
        return self._run_tool_in_thread(
            "rta_set", do_rta_set, drama_type, aadvids, bridge.emit_tool_log
        )

    def stop_rta_set(self) -> dict:
        self._stop_pool.stop("rta_set")
        return {"ok": True}

    def rta_check(self, drama_type: str, aadvids: list) -> dict:
        """RTA 检测 — 批量检测启用状态"""
        from backend.tool_adapter import do_rta_check
        return self._run_tool_in_thread(
            "rta_check", do_rta_check, drama_type, aadvids, bridge.emit_tool_log
        )

    def stop_rta_check(self) -> dict:
        self._stop_pool.stop("rta_check")
        return {"ok": True}

    # ═══ 断点续传 ═══

    def get_pending_build(self) -> dict:
        """检查是否有未完成的搭建任务"""
        from backend.services.build_progress import load_progress
        progress = load_progress()
        if progress:
            return {
                "has_pending": True,
                "task_id": progress["task_id"],
                "profile": progress["profile"],
                "completed_count": len(progress["completed"]),
                "failed_count": len(progress["failed"]),
                "pending_count": len(progress["pending"]),
                "total_count": len(progress["total_accounts"]),
                "updated_at": progress["updated_at"],
            }
        return {"has_pending": False}

    def resume_build(self) -> dict:
        """续传未完成的搭建"""
        from backend.services.build_progress import load_progress
        progress = load_progress()
        if not progress:
            return {"ok": False, "error": "没有未完成的搭建任务"}
        if self._engine.is_running:
            return {"ok": False, "error": "搭建正在运行中"}
        # 用 pending 列表继续搭建
        import threading
        threading.Thread(
            target=self._engine.run_resume,
            args=(progress,),
            daemon=True
        ).start()
        return {"ok": True, "task_id": progress["task_id"]}

    def dismiss_pending_build(self) -> dict:
        """忽略未完成的搭建"""
        from backend.services.build_progress import clear_progress
        clear_progress()
        return {"ok": True}

    # ═══ 每日任务 ═══

    def get_daily_tasks(self, date: str) -> dict:
        """获取指定日期的每日任务列表"""
        try:
            from backend.services.daily_task_service import get_tasks
            tasks = get_tasks(date)
            return {"ok": True, "tasks": tasks, "note": ""}
        except Exception as e:
            return {"ok": False, "tasks": [], "note": "", "error": str(e)}

    def parse_daily_tasks(self, raw_text: str, date: str = "") -> dict:
        """解析原始任务文本并保存到指定日期（默认今天）"""
        try:
            from backend.services.daily_task_service import parse_raw_input, add_tasks, get_tasks
            from datetime import date as dt_date
            tasks = parse_raw_input(raw_text)
            target_date = date or dt_date.today().isoformat()
            if tasks:
                add_tasks(target_date, tasks)
                all_tasks = get_tasks(target_date)
                return {"ok": True, "tasks": all_tasks, "note": ""}
            return {"ok": True, "tasks": [], "note": ""}
        except Exception as e:
            return {"ok": False, "tasks": [], "note": "", "error": str(e)}

    def toggle_daily_task(self, date: str, task_id: str) -> dict:
        """切换每日任务完成状态"""
        try:
            from backend.services.daily_task_service import toggle_task
            new_state = toggle_task(date, task_id)
            return {"ok": True, "done": new_state}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def delete_daily_task(self, date: str, task_id: str) -> dict:
        """删除每日任务"""
        try:
            from backend.services.daily_task_service import delete_task
            delete_task(date, task_id)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def add_manual_daily_task(self, date: str, task_data: dict) -> dict:
        """手动添加一条每日任务（前端表单提交）"""
        try:
            from backend.services.daily_task_service import add_tasks, get_tasks
            from datetime import date as dt_date
            target_date = date or dt_date.today().isoformat()

            params = {}
            if task_data.get("drama_count"):
                params["drama_count"] = task_data["drama_count"]
            if task_data.get("dramas_per_group"):
                params["dramas_per_group"] = task_data["dramas_per_group"]
            if task_data.get("accounts_per_group"):
                params["accounts_per_group"] = task_data["accounts_per_group"]

            task = {
                "person": task_data.get("person", ""),
                "title": task_data.get("title", task_data.get("profile_key", "")),
                "detail": "",
                "profile_key": task_data.get("profile_key", ""),
                "params": params,
                "build_count": 0,
                "build_total": params.get("drama_count", 0),
            }
            add_tasks(target_date, [task])
            all_tasks = get_tasks(target_date)
            return {"ok": True, "tasks": all_tasks}
        except Exception as e:
            return {"ok": False, "error": str(e)}
