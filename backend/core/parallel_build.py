"""
backend/core/parallel_build.py
多 Tab 并行搭建调度器。

策略：同一 Chrome 实例中开多个 popup Tab，每个 Tab 独立执行一部剧的 8 步搭建流程。
通过 ThreadPoolExecutor 控制并发数（默认 3 路），并用 Lock 保护主页按钮点击（同一时刻只有一个 worker 创建新 Tab）。

关键改动：每个 worker 线程创建独立的 sync_playwright() 实例并通过 CDP 连接浏览器，
避免跨线程共享 Page 对象导致的 greenlet 错误。
"""
import sys
import time
import asyncio
import threading
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout, expect

from backend.core.constants import (
    TIMEOUT, ALL_PROFILES, WaitTimes,
    AccountsMissingError, BuildSubmitError, StopRequested,
)
from backend.core.playwright_utils import (
    safe_click, wait_small, wait_idle, select_build_page,
    _safe_page_title, _safe_page_url,
)
from backend.core.logging_utils import setup_logger, fmt_duration
from backend.core.config_io import load_config, record_build_success
from backend.core.data_parsers import (
    build_runtime_profile_config, profile_groups_from_config,
)
from backend.core.exceptions import check_stop
from backend.core.build_steps import (
    step_select_strategy,
    step_select_media_accounts,
    step_link_product,
    step_fill_monitor_links,
    step_select_audience_package,
    step_fill_project_name,
    step_fill_ad_name,
    step_pick_media_materials,
    step_submit_and_close,
)
from backend.utils.win_focus import capture_foreground, restore_foreground


# ═══════════════════════════════════════════════════════════════
#  并行进度追踪器：找出最快的 worker 并推送到前端状态栏
# ═══════════════════════════════════════════════════════════════

class _ProgressTracker:
    """线程安全地追踪各 worker 当前任务，向前端推送最快进度。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._worker_tasks = {}  # worker_id -> {g_idx, d_idx, drama_name, step_desc}

    def update(self, worker_id, g_idx, d_idx, total_groups, total_dramas, drama_name, step_desc=""):
        """worker 报告当前正在执行的任务和步骤"""
        with self._lock:
            self._worker_tasks[worker_id] = {
                "g_idx": g_idx,
                "d_idx": d_idx,
                "total_groups": total_groups,
                "total_dramas": total_dramas,
                "drama_name": drama_name,
                "step_desc": step_desc,
            }
        self._emit_best()

    def remove(self, worker_id):
        """worker 完成或失败后移除追踪"""
        with self._lock:
            self._worker_tasks.pop(worker_id, None)
        self._emit_best()

    def _emit_best(self):
        """找出进度最快的 worker（g_idx 最大，同 g_idx 则 d_idx 最大），推送到前端"""
        with self._lock:
            if not self._worker_tasks:
                return
            best = max(
                self._worker_tasks.values(),
                key=lambda t: (t["g_idx"], t["d_idx"]),
            )
        msg = f"第{best['g_idx']}组 第{best['d_idx']}部剧 {best['drama_name']}"
        if best["step_desc"]:
            msg += f" — {best['step_desc']}"
        try:
            from backend.bridge import bridge
            bridge.emit("build-progress", {
                "step": best["g_idx"],
                "total": best["total_groups"],
                "message": msg,
            })
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
#  单个 drama 的完整搭建流程（在独立 popup 中执行）
#  每个 worker 线程拥有独立的 Playwright 实例和 CDP 连接
# ═══════════════════════════════════════════════════════════════

def _build_single_drama(
    cdp_endpoint, ids, drama, cfg, W, stop_event,
    logger, worker_id, tab_lock, g_idx, d_idx, total_groups, total_dramas,
    group_skip_event=None, progress_tracker=None,
):
    """
    在独立的 Playwright 实例中连接浏览器，打开一个新的"批量新建" popup，执行完整 8 步搭建。

    参数:
        cdp_endpoint: Chrome CDP 连接端点
        ids: 当前组的账号 ID 列表
        drama: 当前剧字典 {name, click, show, video, material_ids}
        cfg: 运行时配置
        W: WaitTimes 实例
        stop_event: 全局停止事件
        logger: 带 worker 前缀的 logger
        worker_id: worker 编号
        tab_lock: 保护主页按钮点击的锁（跨线程共享）
        g_idx, d_idx: 组索引和剧索引（用于日志）
        total_groups, total_dramas: 总数（用于日志）
        group_skip_event: 组级跳过事件，某个 worker 发现账户缺失后 set，同组其余 worker 直接跳过
        progress_tracker: _ProgressTracker 实例，用于向前端推送最快任务进度
    """
    # Windows 上每个线程需要自己的 asyncio 事件循环
    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    drama_name = drama["name"]
    drama_t0 = time.time()
    prefix = f"[W{worker_id}]"

    logger.info(
        f"{prefix} 🎬 [组{g_idx}/{total_groups} · 剧{d_idx}/{total_dramas}] {drama_name}"
    )

    # 报告进度追踪
    if progress_tracker:
        progress_tracker.update(worker_id, g_idx, d_idx, total_groups, total_dramas, drama_name, "准备中")

    popup = None
    pw_instance = None
    browser = None

    try:
        check_stop(stop_event)

        # ── 组级跳过：同组其他 worker 已发现账户缺失，直接跳过 ──
        if group_skip_event and group_skip_event.is_set():
            logger.info(f"{prefix} ⏭️ 同组账户缺失，跳过: {drama_name}")
            return {"status": "skipped", "drama": drama_name, "error": "同组账户缺失"}

        # ── 创建本线程独立的 Playwright 实例和浏览器连接 ──
        pw_instance = sync_playwright().start()
        browser = pw_instance.chromium.connect_over_cdp(cdp_endpoint)
        if not browser.contexts:
            raise RuntimeError(f"{prefix} 已连接浏览器，但没有可用的浏览器上下文")
        context = browser.contexts[0]
        page = select_build_page(context, logger)

        # ── 在 tab_lock 保护下点击"批量新建"创建 popup ──
        with tab_lock:
            check_stop(stop_event)
            if page.is_closed():
                raise RuntimeError("主页面已关闭")

            batch_btns = page.locator("button:has-text('批量新建')")
            batch_count = 0
            try:
                batch_count = batch_btns.count()
            except Exception as e:
                logger.warning(f"{prefix} 获取批量新建按钮数量失败: {e}")

            if batch_count == 0:
                raise RuntimeError(f'{prefix} 当前页面没有找到"批量新建"按钮')

            batch_btn = batch_btns.first
            batch_btn.wait_for(state="visible", timeout=TIMEOUT)
            batch_btn.scroll_into_view_if_needed()
            try:
                expect(batch_btn).to_be_enabled(timeout=5_000)
            except Exception:
                pass
            wait_idle(page, mask_timeout=3_000)

            logger.info(f'{prefix} 🖱️ 点击"批量新建"')
            _prev_fg_hwnd = capture_foreground()
            with page.expect_popup() as popup_info:
                batch_btn.click(force=True)
            popup = popup_info.value
            popup.set_default_timeout(15_000)
            restore_foreground(_prev_fg_hwnd)

            # 等待 popup 基本加载，然后释放锁让下一个 worker 可以创建 Tab
            try:
                popup.wait_for_load_state("domcontentloaded", timeout=30_000)
            except PlaywrightTimeout:
                logger.warning(f"{prefix} ⚠️ popup domcontentloaded 超时，继续")

            # 错开启动：释放锁后稍等一下
            time.sleep(1.5)

        # ── 锁外：等待 popup 完全加载 ──
        try:
            popup.wait_for_load_state("networkidle", timeout=60_000)
            logger.info(f"{prefix} ✅ 批量新建页面已加载")
        except PlaywrightTimeout:
            logger.warning(f"{prefix} ⚠️ networkidle 超时，继续")

        # ── 8 步搭建流程 ──
        check_stop(stop_event)
        if progress_tracker:
            progress_tracker.update(worker_id, g_idx, d_idx, total_groups, total_dramas, drama_name, "步骤1/8 选择策略")
        logger.info(f"{prefix} ➡️ 步骤1/8：选择策略")
        step_select_strategy(popup, cfg, logger, W)

        check_stop(stop_event)
        if group_skip_event and group_skip_event.is_set():
            raise AccountsMissingError([], 0, len(ids))
        if progress_tracker:
            progress_tracker.update(worker_id, g_idx, d_idx, total_groups, total_dramas, drama_name, "步骤2/8 选择账户")
        logger.info(f"{prefix} ➡️ 步骤2/8：选择媒体账户")
        step_select_media_accounts(popup, ids, cfg, logger, W)

        check_stop(stop_event)
        if progress_tracker:
            progress_tracker.update(worker_id, g_idx, d_idx, total_groups, total_dramas, drama_name, "步骤3/8 关联产品")
        logger.info(f"{prefix} ➡️ 步骤3/8：关联产品")
        step_link_product(popup, drama_name, cfg, logger, W)

        check_stop(stop_event)
        if progress_tracker:
            progress_tracker.update(worker_id, g_idx, d_idx, total_groups, total_dramas, drama_name, "步骤4/8 监测链接")
        logger.info(f"{prefix} ➡️ 步骤4/8：填写监测链接")
        step_fill_monitor_links(popup, drama, cfg, logger, W)

        check_stop(stop_event)
        if progress_tracker:
            progress_tracker.update(worker_id, g_idx, d_idx, total_groups, total_dramas, drama_name, "步骤5/8 定向包")
        logger.info(f"{prefix} ➡️ 步骤5/8：选择定向包")
        step_select_audience_package(popup, cfg, logger, W)

        check_stop(stop_event)
        if progress_tracker:
            progress_tracker.update(worker_id, g_idx, d_idx, total_groups, total_dramas, drama_name, "步骤6/8 项目名称")
        logger.info(f"{prefix} ➡️ 步骤6/8：填写项目名称")
        step_fill_project_name(popup, drama_name, cfg, logger, W)

        check_stop(stop_event)
        if progress_tracker:
            progress_tracker.update(worker_id, g_idx, d_idx, total_groups, total_dramas, drama_name, "步骤7/8 广告名称")
        logger.info(f"{prefix} ➡️ 步骤7/8：填写广告名称")
        step_fill_ad_name(popup, drama_name, cfg, logger, W)

        check_stop(stop_event)
        if progress_tracker:
            progress_tracker.update(worker_id, g_idx, d_idx, total_groups, total_dramas, drama_name, "步骤8/8 素材提交")
        logger.info(f"{prefix} ➡️ 步骤8/8：选择素材并提交")
        step_pick_media_materials(popup, drama_name, drama.get("material_ids", []), cfg, logger, W)

        check_stop(stop_event)
        # step_submit_and_close 内部会在最后对共享 page 调用 wait_idle，
        # 为安全起见在 tab_lock 保护下执行提交和关闭
        with tab_lock:
            ad_count = step_submit_and_close(popup, page, logger, W)

        drama_elapsed = time.time() - drama_t0
        if ad_count:
            logger.info(f"{prefix} ✅ {drama_name} 搭建完成（预估 {ad_count} 条广告），用时 {fmt_duration(drama_elapsed)}")
        else:
            logger.info(f"{prefix} ✅ {drama_name} 搭建完成，用时 {fmt_duration(drama_elapsed)}")

        if progress_tracker:
            progress_tracker.remove(worker_id)
        return {"status": "ok", "drama": drama_name, "ad_count": ad_count or 0}

    except StopRequested:
        logger.info(f"{prefix} ⏹ 用户中止: {drama_name}")
        if progress_tracker:
            progress_tracker.remove(worker_id)
        try:
            if popup and not popup.is_closed():
                popup.close()
        except Exception:
            pass
        raise

    except AccountsMissingError as e:
        logger.warning(f"{prefix} ⏭️ 账户缺失: {drama_name} — {e}")
        # 通知同组其余 worker 跳过（同组共享相同 account_ids，必然也会缺失）
        if group_skip_event:
            group_skip_event.set()
        if progress_tracker:
            progress_tracker.remove(worker_id)
        try:
            if popup and not popup.is_closed():
                popup.close()
        except Exception:
            pass
        return {"status": "skipped", "drama": drama_name, "error": str(e)}

    except Exception as e:
        logger.error(f"{prefix} ❌ {drama_name} 搭建失败: {e}")
        if progress_tracker:
            progress_tracker.remove(worker_id)
        try:
            if popup and not popup.is_closed():
                popup.close()
        except Exception:
            pass
        return {"status": "failed", "drama": drama_name, "error": str(e)}

    finally:
        # ── 关闭本线程的 Playwright 连接 ──
        try:
            if browser:
                browser.close()
        except Exception:
            pass
        try:
            if pw_instance:
                pw_instance.stop()
        except Exception:
            pass
        try:
            loop.close()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
#  并行搭建主函数
# ═══════════════════════════════════════════════════════════════

def run_build_parallel(
    profile_key: str,
    log_callback=None,
    stop_event=None,
    max_workers: int = 3,
):
    """
    并行执行搭建流程（多 Tab 同时操作）。

    参数:
        profile_key: 配置键（如 "安卓-每留"）
        log_callback: 日志回调 (message: str)
        stop_event: threading.Event，外部可设置以中止
        max_workers: 最大并行 Tab 数（默认 3）
    """
    app_cfg = load_config()
    cfg = build_runtime_profile_config(profile_key, app_cfg)
    cdp_endpoint = (app_cfg.get("common") or {}).get("cdp_endpoint") or "http://localhost:9222"
    cfg.setdefault("operator_name", (app_cfg.get("common") or {}).get("operator_name") or "lzp")

    W = WaitTimes(cfg["wait_scale"])
    logger = setup_logger(cfg["log_dir"])

    # GUI 日志回调
    if log_callback:
        class _GUIHandler(logging.Handler):
            def emit(self, record):
                try:
                    log_callback(self.format(record))
                except Exception:
                    pass
        gh = _GUIHandler()
        gh.setLevel(logging.INFO)
        gh.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
        logger.addHandler(gh)

    logger.info(f"🚀 开始并行搭建: {profile_key} (并发数: {max_workers})")
    logger.info(
        "⚙️ 本次运行变量："
        f"策略={cfg['strategy']} | "
        f"素材账号ID={cfg['material_account_id']} | "
        f"受众关键词={cfg['audience_keyword']} | "
        f"监控按钮={cfg['monitor_btn_text']} | "
        f"命名前缀={cfg['name_prefix']} | "
        f"等待倍率={cfg['wait_scale']}"
    )

    t0 = time.time()
    failed_dramas = []
    completed_dramas = []
    skipped_groups = []
    total_projects = 0
    success_account_ids = set()
    session_id = str(uuid.uuid4())

    groups = profile_groups_from_config(app_cfg, profile_key)
    if groups:
        logger.info(f"📦 数据来源：内置配置 config.json（{len(groups)} 组）")
    else:
        from backend.core.data_parsers import read_data
        logger.info("📄 内置配置为空，回退读取 ids.txt")
        groups = read_data(cfg["ids_file"], logger)
    if not groups:
        logger.error("❌ 没有读取到任何数据")
        return

    # 将所有 (组, 剧) 任务展开为扁平列表，实现全局流水线调度
    all_tasks = []
    group_skip_events = {}  # 每组一个跳过信号，key=g_idx
    group_ids_map = {}      # 记录每组的 account_ids
    group_drama_counts = {} # 记录每组的剧数
    for g_idx, (ids, dramas) in enumerate(groups, 1):
        group_skip_events[g_idx] = threading.Event()
        group_ids_map[g_idx] = ids
        group_drama_counts[g_idx] = len(dramas)
        for d_idx, drama in enumerate(dramas, 1):
            all_tasks.append({
                "g_idx": g_idx,
                "d_idx": d_idx,
                "ids": ids,
                "drama": drama,
                "total_groups": len(groups),
                "total_dramas": len(dramas),
            })

    logger.info(f"📋 共 {len(all_tasks)} 个搭建任务（{len(groups)} 组），分配到 {max_workers} 路流水线并行执行")

    # ── 主流程：验证浏览器连通性 + 全局流水线调度 ──
    tab_lock = threading.Lock()
    # 统计每组完成数（线程安全）
    group_completed = {g_idx: 0 for g_idx in group_ids_map}
    group_completed_lock = threading.Lock()
    # 进度追踪器：向前端推送最快任务信息
    progress_tracker = _ProgressTracker()

    try:
        # 主线程先连接一次以验证浏览器可达，然后立即断开
        _verify_pw = sync_playwright().start()
        try:
            _verify_browser = _verify_pw.chromium.connect_over_cdp(cdp_endpoint)
            if not _verify_browser.contexts:
                raise RuntimeError("已连接浏览器，但没有可用的浏览器上下文")
            _verify_ctx = _verify_browser.contexts[0]
            _verify_page = select_build_page(_verify_ctx, logger)
            logger.info("✅ 已连接浏览器（验证连通性）")
        finally:
            try:
                _verify_pw.stop()
            except Exception:
                pass

        # 全局流水线：所有任务打散到一个线程池，做完一个立刻接下一个
        # 窗口始终保持满载，不再按组串行等待
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="build") as pool:
            futures = {}
            _worker_counter = 0
            for task in all_tasks:
                check_stop(stop_event)
                _worker_counter += 1
                worker_id = ((_worker_counter - 1) % max_workers) + 1
                g_idx = task["g_idx"]
                future = pool.submit(
                    _build_single_drama,
                    cdp_endpoint=cdp_endpoint,
                    ids=task["ids"],
                    drama=task["drama"],
                    cfg=cfg,
                    W=W,
                    stop_event=stop_event,
                    logger=logger,
                    worker_id=worker_id,
                    tab_lock=tab_lock,
                    g_idx=task["g_idx"],
                    d_idx=task["d_idx"],
                    total_groups=task["total_groups"],
                    total_dramas=task["total_dramas"],
                    group_skip_event=group_skip_events[g_idx],
                    progress_tracker=progress_tracker,
                )
                futures[future] = {
                    "drama_name": task["drama"]["name"],
                    "g_idx": g_idx,
                    "ids": task["ids"],
                }

            # 收集结果（as_completed 保证先完成的先处理）
            for future in as_completed(futures):
                task_info = futures[future]
                drama_name = task_info["drama_name"]
                g_idx = task_info["g_idx"]
                task_ids = task_info["ids"]
                try:
                    result = future.result()
                    if result["status"] == "ok":
                        completed_dramas.append(drama_name)
                        success_account_ids.update(task_ids)
                        with group_completed_lock:
                            group_completed[g_idx] += 1

                        # 通知每日任务
                        try:
                            from backend.bridge import bridge
                            bridge.on_drama_completed(profile_key, drama_name)
                        except Exception:
                            pass

                    elif result["status"] == "skipped":
                        skipped_groups.append(f"第{g_idx}组")
                    else:
                        failed_dramas.append(drama_name)

                except StopRequested:
                    logger.info("⏹ 用户中止，取消剩余任务")
                    for f in futures:
                        f.cancel()
                    raise

                except Exception as e:
                    failed_dramas.append(drama_name)
                    logger.error(f"❌ {drama_name} 执行异常: {e}")

        # 统计 total_projects
        for g_idx, cnt in group_completed.items():
            total_projects += len(group_ids_map[g_idx]) * cnt

    except StopRequested:
        logger.info("⏹ 已停止")
        return

    # ── 汇总报告 ──
    elapsed = time.time() - t0
    logger.info(
        f"\n📊 并行搭建结果：成功 {len(completed_dramas)} 个，"
        f"失败 {len(failed_dramas)} 个，"
        f"跳过 {len(skipped_groups)} 组"
    )
    if skipped_groups:
        logger.warning(f"⏭️ 账户缺失跳过的组：{', '.join(set(skipped_groups))}")
    if failed_dramas:
        logger.error("❌ 未搭建完成剧名汇总：")
        for name in failed_dramas:
            logger.error(f"  {name}")
    else:
        logger.info("✅ 本次没有未搭建完成的剧")
    logger.info(f"\n🎉 全部完成! 总耗时: {fmt_duration(elapsed)}")

    if completed_dramas:
        record_build_success(len(success_account_ids), total_projects, session_id)
        logger.info(f"📝 基建记录已更新：账户 {len(success_account_ids)} 个，项目 {total_projects} 个")
