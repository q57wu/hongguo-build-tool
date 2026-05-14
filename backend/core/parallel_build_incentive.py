"""
backend/core/parallel_build_incentive.py
激励搭建并行调度器。

策略：同一 Chrome 实例中开多个 popup Tab，每个 Tab 独立执行一组激励搭建流程。
通过 ThreadPoolExecutor 控制并发数（默认 3 路），并用 Lock 保护主页按钮点击。

与普通并行搭建不同，激励搭建按「组」并行（每组一个 popup），
每个 worker 使用不同的素材起始页以避免选取重复素材。
"""
import sys
import time
import math
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
from backend.core.config_io import (
    load_config, record_build_success,
    get_used_material_names, add_material_history,
)
from backend.services.build_detail_service import add_build_detail
from backend.core.data_parsers import (
    build_runtime_profile_config, profile_groups_from_config,
)
from backend.core.exceptions import check_stop
from backend.core.incentive_steps import (
    step_link_product_incentive,
    step_fill_monitor_links_incentive,
    step_fill_project_name_incentive,
    step_fill_ad_name_incentive,
    step_pick_materials_by_page,
    step_pick_materials_by_ids_incentive,
)
from backend.core.build_steps import (
    step_select_strategy,
    step_select_media_accounts,
    step_select_audience_package,
    step_submit_and_close,
)
from backend.utils.win_focus import capture_foreground, restore_foreground


# ═══════════════════════════════════════════════════════════════
#  页面协调器：分配并行 worker 的素材扫描页区间
# ═══════════════════════════════════════════════════════════════

class PageCoordinator:
    """
    线程安全的素材页面协调器。

    核心功能：
    1. 均匀分配每个 worker 的起始页（W1从第1页, W2从第15页, ...）
    2. claim_page / release_page 避免多个 worker 同时操作同一页（防平台UI并发bug）
    3. suggest_next_page 提供环形兜底：扫完自己区间后可借道其他未扫页
    4. worker 上报实际总页数后动态调整分配
    """

    # 页面状态
    UNSCANNED = 0       # 未被任何 worker 扫描
    IN_PROGRESS = 1     # 正在被某个 worker 扫描
    DONE = 2            # 已扫描完成

    def __init__(self, estimated_total_pages: int = 60, num_workers: int = 4):
        self._lock = threading.Lock()
        self._total_pages = max(estimated_total_pages, 1)
        self._num_workers = max(num_workers, 1)

        # 页面状态追踪
        self._page_status = {}       # page_no (0-based) -> status
        self._page_owner = {}        # page_no -> worker_id (当前正在扫的)
        self._page_claim_time = {}   # page_no -> claim 时间戳（用于超时释放）

        # worker 状态
        self._worker_ranges = {}     # worker_id -> (start, end) 主管区间 (0-based)
        self._worker_scanned = {}    # worker_id -> set of scanned page_no

        # ── 共享素材去重集合（内存级，跨 worker 实时同步） ──
        self._shared_used_names = set()  # 所有 worker 已选/已见的素材名

        self._assign_ranges()

    def _assign_ranges(self):
        """按 worker 数均匀分配主管区间（0-based 页码）。"""
        chunk = math.ceil(self._total_pages / self._num_workers)
        for w in range(self._num_workers):
            start = w * chunk
            end = min((w + 1) * chunk, self._total_pages) - 1
            wid = w + 1  # worker_id 从 1 开始
            self._worker_ranges[wid] = (start, max(start, end))
            if wid not in self._worker_scanned:
                self._worker_scanned[wid] = set()

    def update_total_pages(self, actual_total_pages: int):
        """worker 上报实际总页数后动态调整（仅扩大，不缩小）。"""
        with self._lock:
            if actual_total_pages > self._total_pages:
                self._total_pages = actual_total_pages
                self._assign_ranges()

    def get_start_page(self, worker_id: int) -> int:
        """获取 worker 的起始页（0-based）。"""
        with self._lock:
            rng = self._worker_ranges.get(worker_id)
            return rng[0] if rng else 0

    def claim_page(self, worker_id: int, page_no: int) -> bool:
        """
        尝试认领某页进行扫描。

        返回 True：可以扫描该页。
        返回 False：该页正在被其他 worker 扫描，应跳过。

        包含30秒超时释放机制：防止 worker 崩溃后页面永久锁定。
        """
        with self._lock:
            status = self._page_status.get(page_no, self.UNSCANNED)
            owner = self._page_owner.get(page_no)
            claim_time = self._page_claim_time.get(page_no, 0)

            # 正在被其他 worker 扫且未超时 → 拒绝
            if (status == self.IN_PROGRESS
                    and owner is not None
                    and owner != worker_id
                    and time.time() - claim_time < 30):
                return False

            # 认领
            self._page_status[page_no] = self.IN_PROGRESS
            self._page_owner[page_no] = worker_id
            self._page_claim_time[page_no] = time.time()
            return True

    def release_page(self, worker_id: int, page_no: int):
        """worker 扫完某页后释放。"""
        with self._lock:
            self._page_status[page_no] = self.DONE
            if self._page_owner.get(page_no) == worker_id:
                del self._page_owner[page_no]
            self._page_claim_time.pop(page_no, None)
            self._worker_scanned.setdefault(worker_id, set()).add(page_no)

    def suggest_next_page(self, worker_id: int, current_page: int):
        """
        为 worker 建议下一个应该扫描的页（0-based）。

        优先级：
        1. 主管区间内的下一个未扫描页
        2. 环形方向上第一个未被占用的页（借道）

        返回 None 表示无可用页。
        """
        with self._lock:
            total = self._total_pages
            my_scanned = self._worker_scanned.get(worker_id, set())
            my_range = self._worker_ranges.get(worker_id, (0, total - 1))
            now = time.time()

            # 第一圈：只在主管区间内找
            for offset in range(1, total):
                candidate = (current_page + offset) % total
                if candidate in my_scanned:
                    continue
                in_my_range = my_range[0] <= candidate <= my_range[1]
                if not in_my_range:
                    continue
                status = self._page_status.get(candidate, self.UNSCANNED)
                if status == self.IN_PROGRESS:
                    owner = self._page_owner.get(candidate)
                    claim_time = self._page_claim_time.get(candidate, 0)
                    if owner != worker_id and now - claim_time < 30:
                        continue
                return candidate

            # 第二圈：借道 — 在主管区间外找未扫过的页
            for offset in range(1, total):
                candidate = (current_page + offset) % total
                if candidate in my_scanned:
                    continue
                status = self._page_status.get(candidate, self.UNSCANNED)
                if status == self.IN_PROGRESS:
                    owner = self._page_owner.get(candidate)
                    claim_time = self._page_claim_time.get(candidate, 0)
                    if owner != worker_id and now - claim_time < 30:
                        continue
                # 借道时只去 UNSCANNED 的页（别人扫过的不重复去）
                if status == self.UNSCANNED:
                    return candidate

            return None

    # ── 共享素材去重 ──

    def init_used_names(self, names):
        """初始化已用素材集合（从历史文件加载一次，避免每次读文件）。"""
        with self._lock:
            self._shared_used_names.update(names)

    def try_reserve_material(self, mat_name: str) -> bool:
        """
        原子性地尝试预留一条素材。

        返回 True：该素材未被任何 worker 选过，已成功预留（其他 worker 再调用会返回 False）。
        返回 False：该素材已被预留或已在历史中。
        """
        with self._lock:
            if mat_name in self._shared_used_names:
                return False
            self._shared_used_names.add(mat_name)
            return True

    def is_material_used(self, mat_name: str) -> bool:
        """检查素材是否已被使用（不预留）。"""
        with self._lock:
            return mat_name in self._shared_used_names

    def get_used_count(self) -> int:
        """返回当前已用素材总数。"""
        with self._lock:
            return len(self._shared_used_names)

    def get_range_info(self, worker_id: int) -> str:
        """返回 worker 区间信息（用于日志）。"""
        with self._lock:
            rng = self._worker_ranges.get(worker_id, (0, 0))
            return f"第{rng[0]+1}-{rng[1]+1}页"


# ═══════════════════════════════════════════════════════════════
#  并行进度追踪器：找出最快的 worker 并推送到前端状态栏
# ═══════════════════════════════════════════════════════════════

class _ProgressTrackerIncentive:
    """线程安全地追踪各 worker 当前任务，向前端推送最快进度（激励版）。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._worker_tasks = {}  # worker_id -> {g_idx, group_name, total_groups, step_desc}

    def update(self, worker_id, g_idx, total_groups, group_name, step_desc=""):
        """worker 报告当前正在执行的任务和步骤"""
        with self._lock:
            self._worker_tasks[worker_id] = {
                "g_idx": g_idx,
                "total_groups": total_groups,
                "group_name": group_name,
                "step_desc": step_desc,
            }
        self._emit_best()

    def remove(self, worker_id):
        """worker 完成或失败后移除追踪"""
        with self._lock:
            self._worker_tasks.pop(worker_id, None)
        self._emit_best()

    def _emit_best(self):
        """找出进度最快的 worker（g_idx 最大），推送到前端"""
        with self._lock:
            if not self._worker_tasks:
                return
            best = max(
                self._worker_tasks.values(),
                key=lambda t: t["g_idx"],
            )
        msg = f"第{best['g_idx']}组 {best['group_name']}"
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
#  单组激励搭建（在独立 popup 中执行）
# ═══════════════════════════════════════════════════════════════

def _build_single_group_incentive(
    cdp_endpoint, ids, meta, cfg, W, stop_event,
    logger, worker_id, tab_lock, g_idx, total_groups,
    start_page=0, material_lock=None, progress_tracker=None,
    session_id="", profile_key="",
    page_coordinator=None,
):
    """
    在独立 Playwright 实例中连接浏览器，打开一个新的"批量新建" popup，
    执行完整激励搭建 8 步流程。

    参数:
        cdp_endpoint: Chrome CDP 连接端点
        ids: 当前组的账号 ID 列表
        meta: 组元数据 {group_name, click_url, show_url, play_url}
        cfg: 运行时配置
        W: WaitTimes 实例
        stop_event: 全局停止事件
        logger: logger
        worker_id: worker 编号
        tab_lock: 保护主页按钮点击的锁
        g_idx: 组索引（用于日志）
        total_groups: 总组数（用于日志）
        start_page: 素材起始页码（0-based），用于避免与其他 worker 选取重复素材
        material_lock: 保护素材历史读写的锁
        progress_tracker: _ProgressTrackerIncentive 实例，用于向前端推送最快任务进度
    """
    # Windows 上每个线程需要自己的 asyncio 事件循环
    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    group_name = meta.get("group_name", f"组{g_idx}")
    group_t0 = time.time()
    prefix = f"[W{worker_id}]"

    logger.info(
        f"{prefix} 🎬 [组{g_idx}/{total_groups}] {group_name} | 账号数: {len(ids)} | 素材起始页: {start_page + 1}"
    )

    # 报告进度追踪
    if progress_tracker:
        progress_tracker.update(worker_id, g_idx, total_groups, group_name, "准备中")

    popup = None
    pw_instance = None
    browser = None
    _stopped_by_user = False

    try:
        check_stop(stop_event)

        # ── 创建本线程独立的 Playwright 实例和浏览器连接 ──
        pw_instance = sync_playwright().start()

        # CDP 连接重试：最多 3 次，指数退避 2 / 4 / 8 秒
        _cdp_max_retries = 3
        _cdp_backoff = [2, 4, 8]
        for _attempt in range(_cdp_max_retries):
            try:
                browser = pw_instance.chromium.connect_over_cdp(cdp_endpoint)
            except Exception as _cdp_err:
                if _attempt < _cdp_max_retries - 1:
                    _wait = _cdp_backoff[_attempt]
                    logger.warning(
                        f"{prefix} ⚠️ CDP 连接失败（第 {_attempt + 1} 次），"
                        f"{_wait}s 后重试: {_cdp_err}"
                    )
                    time.sleep(_wait)
                    continue
                # 最终仍失败，交由外层 except 处理
                raise

            # 已连接——检查 contexts 是否就绪，若空则视为未就绪并重试
            if not browser.contexts:
                if _attempt < _cdp_max_retries - 1:
                    _wait = _cdp_backoff[_attempt]
                    logger.warning(
                        f"{prefix} ⚠️ 已连接浏览器但 contexts 为空（第 {_attempt + 1} 次），"
                        f"{_wait}s 后重试"
                    )
                    try:
                        browser.close()
                    except Exception:
                        pass
                    time.sleep(_wait)
                    continue
                raise RuntimeError(f"{prefix} 已连接浏览器，但没有可用的浏览器上下文")

            # 连接成功且 contexts 就绪
            break

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

            # 等待 popup 基本加载
            try:
                popup.wait_for_load_state("domcontentloaded", timeout=30_000)
            except PlaywrightTimeout:
                logger.warning(f"{prefix} ⚠️ popup domcontentloaded 超时，继续")

            # 错开启动
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
            progress_tracker.update(worker_id, g_idx, total_groups, group_name, "步骤1/8 选择策略")
        logger.info(f"{prefix} ➡️ 步骤1/8：选择策略")
        step_select_strategy(popup, cfg, logger, W)

        check_stop(stop_event)
        if progress_tracker:
            progress_tracker.update(worker_id, g_idx, total_groups, group_name, "步骤2/8 选择账户")
        logger.info(f"{prefix} ➡️ 步骤2/8：选择媒体账户")
        step_select_media_accounts(popup, ids, cfg, logger, W)

        check_stop(stop_event)
        if progress_tracker:
            progress_tracker.update(worker_id, g_idx, total_groups, group_name, "步骤3/8 关联产品")
        logger.info(f"{prefix} ➡️ 步骤3/8：关联产品（激励-空搜）")
        step_link_product_incentive(popup, cfg, logger, W)

        check_stop(stop_event)
        if progress_tracker:
            progress_tracker.update(worker_id, g_idx, total_groups, group_name, "步骤4/8 监测链接")
        logger.info(f"{prefix} ➡️ 步骤4/8：填写监测链接")
        step_fill_monitor_links_incentive(popup, meta, cfg, logger, W)

        check_stop(stop_event)
        if progress_tracker:
            progress_tracker.update(worker_id, g_idx, total_groups, group_name, "步骤5/8 定向包")
        logger.info(f"{prefix} ➡️ 步骤5/8：选择定向包")
        step_select_audience_package(popup, cfg, logger, W)

        check_stop(stop_event)
        if progress_tracker:
            progress_tracker.update(worker_id, g_idx, total_groups, group_name, "步骤6/8 项目名称")
        logger.info(f"{prefix} ➡️ 步骤6/8：填写项目名称")
        step_fill_project_name_incentive(popup, group_name, cfg, logger, W)

        check_stop(stop_event)
        if progress_tracker:
            progress_tracker.update(worker_id, g_idx, total_groups, group_name, "步骤7/8 广告名称")
        logger.info(f"{prefix} ➡️ 步骤7/8：填写广告名称")
        step_fill_ad_name_incentive(popup, group_name, cfg, logger, W)

        check_stop(stop_event)
        if progress_tracker:
            progress_tracker.update(worker_id, g_idx, total_groups, group_name, "步骤8/8 素材提交")
        custom_mids = meta.get("material_ids", []) if meta else []
        if custom_mids:
            logger.info(f"{prefix} ➡️ 步骤8/8：使用自定义素材ID（{len(custom_mids)} 个）")
            step_pick_materials_by_ids_incentive(popup, custom_mids, cfg, logger, W)
        else:
            range_info = page_coordinator.get_range_info(worker_id) if page_coordinator else f"第{start_page + 1}页起"
            logger.info(f"{prefix} ➡️ 步骤8/8：选取素材（主管区间 {range_info}）")
            resume_position = {"page": start_page, "offset": 0}
            resume_position = step_pick_materials_by_page(
                popup, cfg.get("pages_per_round", 3), cfg, logger, W,
                resume_position=resume_position,
                material_lock=material_lock,
                page_coordinator=page_coordinator,
                worker_id=worker_id,
            )
            picked = (resume_position or {}).get("picked_count", -1)
            if picked == 0:
                raise Exception(f"❌ 组{group_name} 素材选取为0，跳过提交")

        check_stop(stop_event)
        # 在 tab_lock 保护下执行提交和关闭
        with tab_lock:
            ad_count = step_submit_and_close(popup, page, logger, W)

        group_elapsed = time.time() - group_t0
        if ad_count:
            logger.info(
                f"{prefix} ✅ {group_name} 搭建完成"
                f"（{len(ids)} 个账号，预估 {ad_count} 条广告），"
                f"用时 {fmt_duration(group_elapsed)}"
            )
        else:
            logger.info(
                f"{prefix} ✅ {group_name} 搭建完成"
                f"（{len(ids)} 个账号），"
                f"用时 {fmt_duration(group_elapsed)}"
            )

        if progress_tracker:
            progress_tracker.remove(worker_id)
        # 记录搭建详情（成功）
        for _acc_id in ids:
            try:
                add_build_detail(session_id, profile_key, _acc_id, "success", group_name)
            except Exception:
                pass
        return {
            "status": "ok",
            "group_name": group_name,
            "ad_count": ad_count or 0,
            "ids": ids,
        }

    except StopRequested:
        _stopped_by_user = True
        logger.info(f"{prefix} ⏹ 用户中止（保留当前标签页）: {group_name}")
        if progress_tracker:
            progress_tracker.remove(worker_id)
        raise

    except AccountsMissingError as e:
        logger.warning(f"{prefix} ⏭️ 账户缺失: {group_name} — {e}")
        if progress_tracker:
            progress_tracker.remove(worker_id)
        # 记录搭建详情（跳过）
        for _acc_id in ids:
            try:
                add_build_detail(session_id, profile_key, _acc_id, "skipped", group_name, f"账户缺失: {e}")
            except Exception:
                pass
        try:
            if popup and not popup.is_closed():
                popup.close()
        except Exception:
            pass
        return {"status": "skipped", "group_name": group_name, "error": str(e)}

    except Exception as e:
        logger.error(f"{prefix} ❌ {group_name} 搭建失败: {e}")
        if progress_tracker:
            progress_tracker.remove(worker_id)
        # 记录搭建详情（失败）
        for _acc_id in ids:
            try:
                add_build_detail(session_id, profile_key, _acc_id, "failed", group_name, str(e))
            except Exception:
                pass
        try:
            if popup and not popup.is_closed():
                popup.close()
        except Exception:
            pass
        return {"status": "failed", "group_name": group_name, "error": str(e)}

    finally:
        # ── 关闭本线程的 Playwright 连接 ──
        # 用户主动停止时，只断开 Playwright 进程，不关闭浏览器标签页
        try:
            if browser and not _stopped_by_user:
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
#  并行激励搭建主函数
# ═══════════════════════════════════════════════════════════════

def run_build_incentive_parallel(
    profile_key: str,
    log_callback=None,
    stop_event=None,
    max_workers: int = 3,
    estimated_pages: int = 60,
):
    """
    并行执行激励搭建流程（多 Tab 同时操作，每 Tab 一组）。

    参数:
        profile_key: 配置键（如 "安卓-激励每留"）
        log_callback: 日志回调 (message: str)
        stop_event: threading.Event，外部可设置以中止
        max_workers: 最大并行 Tab 数（默认 3）
        estimated_pages: 预估素材总页数（默认 60），用于初始分配 worker 区间，
                         worker 上报实际总页数后会动态调整
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

    logger.info(f"🚀 开始并行激励搭建: {profile_key} (并发数: {max_workers}, 预估总页数: {estimated_pages})")
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
    completed_groups = []
    failed_groups = []
    skipped_groups = []
    total_projects = 0
    success_account_ids = set()
    session_id = str(uuid.uuid4())

    groups = profile_groups_from_config(app_cfg, profile_key)
    if not groups:
        logger.error("❌ 没有读取到任何数据")
        return

    logger.info(f"📦 共 {len(groups)} 组，分配到 {max_workers} 路并行执行")

    # 素材历史线程安全锁
    material_lock = threading.Lock()
    tab_lock = threading.Lock()
    # 进度追踪器：向前端推送最快任务信息
    progress_tracker = _ProgressTrackerIncentive()
    # 页面协调器：分配各 worker 的素材扫描区间
    actual_workers = min(max_workers, len(groups))
    page_coordinator = PageCoordinator(
        estimated_total_pages=estimated_pages,
        num_workers=actual_workers,
    )
    # 一次性加载历史素材到内存，后续全部走内存去重
    _history_names = get_used_material_names()
    page_coordinator.init_used_names(_history_names)
    logger.info(f"📋 已加载历史素材 {len(_history_names)} 条到共享去重集合")
    for _w in range(1, actual_workers + 1):
        logger.info(f"  W{_w} 主管区间: {page_coordinator.get_range_info(_w)}")

    try:
        # 主线程先连接一次以验证浏览器可达
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

        # 所有组并行执行（不同于普通搭建的"组间串行、组内并行"）
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="incentive") as pool:
            futures = {}
            for g_idx, group_data in enumerate(groups, 1):
                check_stop(stop_event)
                ids = group_data[0]
                meta = group_data[2] if len(group_data) > 2 else {}

                worker_id = ((g_idx - 1) % max_workers) + 1
                start_page = page_coordinator.get_start_page(worker_id)

                future = pool.submit(
                    _build_single_group_incentive,
                    cdp_endpoint=cdp_endpoint,
                    ids=ids,
                    meta=meta,
                    cfg=cfg,
                    W=W,
                    stop_event=stop_event,
                    logger=logger,
                    worker_id=worker_id,
                    tab_lock=tab_lock,
                    g_idx=g_idx,
                    total_groups=len(groups),
                    start_page=start_page,
                    material_lock=material_lock,
                    progress_tracker=progress_tracker,
                    session_id=session_id,
                    profile_key=profile_key,
                    page_coordinator=page_coordinator,
                )
                group_name = meta.get("group_name", f"组{g_idx}")
                futures[future] = group_name

            # 收集结果
            for future in as_completed(futures):
                group_name = futures[future]
                try:
                    result = future.result()
                    if result["status"] == "ok":
                        completed_groups.append(group_name)
                        success_account_ids.update(result.get("ids", []))
                        total_projects += len(result.get("ids", []))

                        # 通知每日任务
                        try:
                            from backend.bridge import bridge
                            bridge.on_drama_completed(profile_key, group_name)
                        except Exception:
                            pass

                    elif result["status"] == "skipped":
                        skipped_groups.append(group_name)
                    else:
                        failed_groups.append(group_name)

                except StopRequested:
                    logger.info("⏹ 用户中止，取消剩余任务")
                    for f in futures:
                        f.cancel()
                    raise

                except Exception as e:
                    failed_groups.append(group_name)
                    logger.error(f"❌ {group_name} 执行异常: {e}")

    except StopRequested:
        logger.info("⏹ 已停止")
        return

    # ── 汇总报告 ──
    elapsed = time.time() - t0
    logger.info(
        f"\n📊 并行激励搭建结果：成功 {len(completed_groups)} 组，"
        f"失败 {len(failed_groups)} 组，"
        f"跳过 {len(skipped_groups)} 组"
    )
    if skipped_groups:
        logger.warning(f"⏭️ 账户缺失跳过的组：{', '.join(skipped_groups)}")
    if failed_groups:
        logger.error("❌ 未搭建完成组汇总：")
        for name in failed_groups:
            logger.error(f"  {name}")
    else:
        logger.info("✅ 本次没有未搭建完成的组")
    logger.info(f"\n🎉 全部完成! 总耗时: {fmt_duration(elapsed)}")

    if completed_groups:
        record_build_success(len(success_account_ids), total_projects, session_id)
        logger.info(f"📝 基建记录已更新：账户 {len(success_account_ids)} 个，项目 {total_projects} 个")
