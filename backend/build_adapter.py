"""
搭建适配器：桥接 pywebview 架构与搭建逻辑。
直接从 backend.core 导入业务模块。
"""
import sys
import asyncio
import logging
import re
from pathlib import Path

_gui_dir = Path(__file__).resolve().parent.parent
if str(_gui_dir) not in sys.path:
    sys.path.insert(0, str(_gui_dir))

from backend.core.build_steps import run_build
from backend.core.incentive_steps import run_build_incentive
from backend.core.constants import ALL_PROFILES


def _setup_event_loop():
    """初始化事件循环，解决 Windows Playwright 兼容问题"""
    # Windows 的 ProactorEventLoop 与 Playwright 的 greenlet 调度在 pywebview
    # 子线程中冲突，导致 sync_playwright().__enter__ 无法完成初始化。
    # 强制使用 SelectorEventLoop 解决此问题。
    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop()
    else:
        loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # 修复 Windows 控制台 GBK 编码无法输出 emoji 的问题
    for handler in logging.root.handlers:
        if hasattr(handler, 'stream') and hasattr(handler.stream, 'reconfigure'):
            try:
                handler.stream.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            try:
                stream.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass


def _make_log_adapter(profile_key, log_callback):
    """创建日志适配器，自动推断日志级别并更新每日任务计数"""
    def _log_adapter(message):
        level = "info"
        if "❌" in message or "错误" in message or "失败" in message:
            level = "error"
        elif "⚠" in message or "警告" in message:
            level = "warn"
        elif "✅" in message or "✔" in message or "成功" in message:
            level = "success"
        log_callback(message, level)

        # 检测单部剧搭建完成日志，更新每日任务计数
        # 日志格式: "✅ {drama_name} 搭建完成" 或 "✅ {drama_name} 搭建完成（预估 N 条广告）"
        if "搭建完成" in message and "✅" in message:
            m = re.search(r'✅\s*(.+?)\s*搭建完成', message)
            if m:
                try:
                    from backend.bridge import bridge
                    bridge.on_drama_completed(profile_key, m.group(1))
                except Exception as e:
                    logging.getLogger(__name__).warning(f"更新每日任务计数失败: {e}")
    return _log_adapter


def run_build_task(profile_key: str, log_callback, stop_event, progress_callback=None, resume_accounts=None):
    """
    适配层：调用真实的 run_build / run_build_incentive。

    新架构 log_callback 签名: (message: str, level: str)
    原始 log_callback 签名: (message: str)  -- 通过 logging.Handler

    注意：此函数在子线程中运行，需要确保 Playwright 能获取到事件循环。
    """
    _setup_event_loop()
    _log_adapter = _make_log_adapter(profile_key, log_callback)

    profile = ALL_PROFILES.get(profile_key, {})
    is_incentive = profile.get("incentive", False)

    # 断点续传支持
    if resume_accounts is not None:
        log_callback("🔄 断点续传模式：只处理剩余账户", "info")
        target = run_build_incentive if is_incentive else run_build
        try:
            target(
                profile_key=profile_key,
                log_callback=_log_adapter,
                stop_event=stop_event,
                progress_callback=progress_callback,
                resume_accounts=resume_accounts,
            )
        except TypeError:
            _log_adapter("⚠️ 当前模块不支持断点续传参数，将完整执行")
            target(profile_key=profile_key, log_callback=_log_adapter, stop_event=stop_event,
                   progress_callback=progress_callback)
        return

    if is_incentive:
        run_build_incentive(
            profile_key=profile_key,
            log_callback=_log_adapter,
            stop_event=stop_event,
            progress_callback=progress_callback,
        )
    else:
        run_build(
            profile_key=profile_key,
            log_callback=_log_adapter,
            stop_event=stop_event,
            progress_callback=progress_callback,
        )

    # After build completes, update last_used for all accounts in this profile
    try:
        from backend.services.account_pool import touch_accounts
        from backend.config_manager import load_config
        cfg = load_config()
        profile_cfg = (cfg.get("profiles") or {}).get(profile_key, {})
        all_ids = []
        for group in profile_cfg.get("groups", []):
            all_ids.extend(group.get("account_ids", []))
        if all_ids:
            _pool = "incentive" if "激励" in profile_key else "normal"
            touch_accounts(all_ids, "media", pool=_pool)
    except Exception:
        pass


def run_build_task_parallel(profile_key, log_callback=None, stop_event=None, max_workers=3):
    """
    并行搭建适配层：调用 parallel_build 模块的 run_build_parallel。

    与 run_build_task 类似，但使用多线程并行执行搭建任务以提升效率。
    注意：此函数在子线程中运行，需要确保 Playwright 能获取到事件循环。
    """
    _setup_event_loop()
    _log_adapter = _make_log_adapter(profile_key, log_callback)

    from backend.core.parallel_build import run_build_parallel

    run_build_parallel(
        profile_key,
        log_callback=_log_adapter,
        stop_event=stop_event,
        max_workers=max_workers,
    )

    # After build completes, update last_used for all accounts in this profile
    try:
        from backend.services.account_pool import touch_accounts
        from backend.config_manager import load_config
        cfg = load_config()
        profile_cfg = (cfg.get("profiles") or {}).get(profile_key, {})
        all_ids = []
        for group in profile_cfg.get("groups", []):
            all_ids.extend(group.get("account_ids", []))
        if all_ids:
            _pool = "incentive" if "激励" in profile_key else "normal"
            touch_accounts(all_ids, "media", pool=_pool)
    except Exception:
        pass


def run_build_task_parallel_incentive(profile_key, log_callback=None, stop_event=None, max_workers=3):
    """
    并行激励搭建适配层：调用 parallel_build_incentive 模块的 run_build_incentive_parallel。

    与 run_build_task_parallel 类似，但针对激励搭建，按组并行且素材页偏移避免重复。
    """
    _setup_event_loop()
    _log_adapter = _make_log_adapter(profile_key, log_callback)

    from backend.core.parallel_build_incentive import run_build_incentive_parallel

    run_build_incentive_parallel(
        profile_key,
        log_callback=_log_adapter,
        stop_event=stop_event,
        max_workers=max_workers,
    )

    # After build completes, update last_used for all accounts in this profile
    try:
        from backend.services.account_pool import touch_accounts
        from backend.config_manager import load_config
        cfg = load_config()
        profile_cfg = (cfg.get("profiles") or {}).get(profile_key, {})
        all_ids = []
        for group in profile_cfg.get("groups", []):
            all_ids.extend(group.get("account_ids", []))
        if all_ids:
            _pool = "incentive" if "激励" in profile_key else "normal"
            touch_accounts(all_ids, "media", pool=_pool)
    except Exception:
        pass
