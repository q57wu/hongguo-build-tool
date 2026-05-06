"""
backend/core/incentive_steps.py
激励搭建步骤函数。
"""
import re
import time
import logging
import threading
from pathlib import Path
from datetime import datetime

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout, expect
except ImportError:
    sync_playwright = None
    PlaywrightTimeout = Exception
    expect = None

# 常量、异常、数据类已迁移至 backend.core.constants
from backend.core.constants import (
    TIMEOUT,
    RE_CONFIRM,
    WaitTimes,
    AccountsMissingError,
    StopRequested,
)

# ── 已迁移至独立模块的稳定符号 ──
from backend.core.playwright_utils import (
    safe_click, wait_small, wait_idle, wait_loading_gone,
    _locator_count, select_build_page, get_visible_drawer, get_visible_layer,
    scroll_wrap_to_bottom, scroll_to_module,
    click_top_confirm, click_optional_confirm,
    _safe_page_title, _safe_page_url,
)
from backend.core.logging_utils import setup_logger, fmt_duration
from backend.core.constants import TODAY_STR
import uuid
from backend.core.config_io import (
    load_config, record_build_success,
    get_used_material_names, add_material_history,
)
from backend.core.data_parsers import (
    sanitize_link_text,
    build_runtime_profile_config, profile_groups_from_config,
)

# 异常处理 / 素材操作（已迁移）
from backend.core.exceptions import check_stop
from backend.utils.win_focus import capture_foreground, restore_foreground
from backend.core.material_ops import (
    _configure_material_filters,
    _find_material_card_on_current_page,
    _get_material_pager,
    _has_next_material_page,
    _go_to_next_material_page,
    _go_to_material_page,
)

# 从 build_steps 复用公共步骤
try:
    from backend.core.build_steps import (
        step_select_strategy,
        step_select_media_accounts,
        step_select_audience_package,
        step_submit_and_close,
    )
except ImportError:
    pass


# ═══════════════════════════════════════════════════════════════
#  激励搭建步骤函数
# ═══════════════════════════════════════════════════════════════

def step_link_product_incentive(popup, cfg, logger, W):
    """激励搭建：关联产品（空搜选第一个）"""
    try:
        popup.wait_for_load_state("networkidle", timeout=5_000)
    except PlaywrightTimeout:
        pass
    wait_small(popup, W.LONG)
    edit_btn = popup.locator("tfoot td button:has-text('编辑')").nth(0)
    edit_btn.wait_for(state="visible", timeout=TIMEOUT)
    edit_btn.scroll_into_view_if_needed()
    wait_small(popup, W.MEDIUM)
    edit_btn.click()
    wait_small(popup, W.LOAD)

    drawer, wrap = get_visible_drawer(popup)
    scroll_to_module(popup, wrap, "link-product", W)
    safe_click(popup, popup.locator("#link-product button:has-text('选择产品')"), desc="选择产品按钮", logger=logger, W=W)
    prod_dlg = popup.locator("div.el-dialog__wrapper:visible").last
    prod_dlg.wait_for(state="visible", timeout=TIMEOUT)
    safe_click(popup, prod_dlg.locator("button.el-button--text.el-button--mini:has-text('清空')").first, desc="清空产品", logger=logger, W=W)
    wait_small(popup, W.LONG)
    safe_click(popup, prod_dlg.locator("button:has-text('查询')"), desc="查询全部产品", logger=logger, W=W)
    wait_small(popup, W.HEAVY)
    all_p = prod_dlg.locator("div.el-checkbox-group label.el-checkbox")
    total = all_p.count()
    if total > 0:
        safe_click(popup, all_p.first, desc="选择第一个产品", logger=logger, W=W)
        logger.info(f"🎯 激励模式：空搜选中第 1/{total} 个产品")
    else:
        logger.warning("⚠️ 未找到任何产品")
    click_top_confirm(popup, prod_dlg, desc="产品确认", wait_close=True, logger=logger, W=W)
    wait_small(popup, W.LONG)


def step_fill_monitor_links_incentive(popup, meta, cfg, logger, W):
    """激励搭建：监测链接（从 meta 取 URL）"""
    drawer, wrap = get_visible_drawer(popup)
    scroll_to_module(popup, wrap, "goal", W)

    safe_click(popup,
        popup.locator(f"#select-track-group button:has-text('{cfg['monitor_btn_text']}')"),
        desc=cfg['monitor_btn_text'], logger=logger, W=W)

    popup.locator("text=手动输入监测链接").first.wait_for(state="visible", timeout=TIMEOUT)
    monitor_drawer, monitor_wrap = get_visible_drawer(popup)

    def switch_on(label):
        item = monitor_drawer.locator(f"div.el-form-item:has(label.el-form-item__label:text-is('{label}'))").first
        if item.count() > 0:
            item.locator("label.el-radio-button:has-text('开启')").first.click(force=True)
            wait_small(popup, W.MEDIUM)

    def fill_link(label, value):
        item = monitor_drawer.locator(f"div.el-form-item:has(label.el-form-item__label:has-text('{label}'))").first
        input_box = item.locator("input.el-input__inner:visible").first
        input_box.wait_for(state="visible", timeout=TIMEOUT)
        input_box.click(force=True)
        wait_small(popup, W.TINY)
        input_box.fill(sanitize_link_text(value))
        wait_small(popup, W.SHORT)
        try:
            actual = input_box.input_value().strip()
        except Exception:
            actual = ""
        if not actual:
            raise Exception(f"{label}未填写成功")

    switch_on('展示链接'); switch_on('有效触点链接'); switch_on('视频有效播放链接')
    fill_link('请输入展示链接', meta.get("show_url", ""))
    logger.info("  展示链接☑️")
    fill_link('请输入有效触点链接', meta.get("click_url", ""))
    logger.info("  监测链接☑️")
    fill_link('请输入视频有效播放链接', meta.get("play_url", ""))
    logger.info("  播放链接☑️")
    logger.info("  ✅ 三个链接已填写完成")

    scroll_wrap_to_bottom(popup, monitor_wrap, W)
    click_top_confirm(popup, logger=logger, W=W)
    wait_small(popup, W.LONG)


def step_fill_project_name_incentive(popup, group_name, cfg, logger, W):
    """激励搭建：项目名称（用组名）"""
    drawer, wrap = get_visible_drawer(popup)
    scroll_to_module(popup, wrap, "project-name", W)
    project_name = f"{cfg['name_prefix']}-lzp-<日期>-{group_name}"
    name_input = popup.locator("#project-name input.el-input__inner").first
    name_input.wait_for(state="visible", timeout=TIMEOUT)
    name_input.click(force=True); name_input.fill("")
    wait_small(popup, W.TINY)
    name_input.fill(project_name)
    wait_small(popup, W.SHORT)
    try: actual_value = name_input.input_value().strip()
    except Exception as e:
        logger.warning(f"step_fill_project_name_incentive 获取输入值失败: {e}")
        actual_value = ""
    if actual_value != project_name:
        name_input.click(force=True); name_input.fill("")
        wait_small(popup, W.TINY); name_input.fill(project_name)
        wait_small(popup, W.SHORT)
    logger.info(f"📝 项目名称: {project_name}")
    name_input.press("Tab"); wait_small(popup, W.SHORT)
    scroll_wrap_to_bottom(popup, wrap, W)
    drawer_confirm = drawer.locator("button.el-button--primary:not(.is-disabled):visible").filter(has_text=RE_CONFIRM).last
    if _locator_count(drawer_confirm) == 0:
        drawer_confirm = popup.locator("div.drawer-content:visible").last.locator("button:not(.is-disabled):visible").filter(has_text=RE_CONFIRM).last
    if _locator_count(drawer_confirm) > 0:
        safe_click(popup, drawer_confirm, desc="项目名称确定按钮", logger=logger, W=W)
    else:
        click_top_confirm(popup, desc="项目名称确定按钮", logger=logger, W=W)
    wait_idle(popup, mask_timeout=W.LOAD)


def step_fill_ad_name_incentive(popup, group_name, cfg, logger, W):
    """激励搭建：广告名称（用组名）"""
    promo_block = popup.locator("div.module-container#promotion-name")
    edit_btn = popup.locator("tfoot td button:has-text('编辑')").nth(1)
    edit_btn.wait_for(state="visible", timeout=TIMEOUT)
    edit_btn.scroll_into_view_if_needed()
    last_err = None
    for _attempt in range(5):
        try: popup.keyboard.press("Escape")
        except Exception as e:
            logger.warning(f"step_fill_ad_name_incentive 按Escape失败: {e}")
        popup.wait_for_timeout(W.SHORT)
        try: edit_btn.click(force=True)
        except Exception as e:
            last_err = e; popup.wait_for_timeout(W.LONG); continue
        try: promo_block.first.wait_for(state="visible", timeout=8_000); break
        except Exception as e:
            last_err = e; popup.wait_for_timeout(W.LONG)
    else:
        raise Exception(f"点击'广告编辑'后始终未出现广告名称模块 (最后错误: {last_err})")
    wait_small(popup, W.NORMAL)
    ad_name = f"{cfg['name_prefix']}-lzp-<日期>-{group_name}-<动态标号>"
    popup.locator("div.module-container#promotion-name").locator(
        "div.el-form-item:has(label:has-text('广告名称')) input.el-input__inner"
    ).first.fill(ad_name)
    logger.info(f"📝 广告名称: {ad_name}")
    drawer, wrap = get_visible_drawer(popup)
    scroll_wrap_to_bottom(popup, wrap, W)
    click_top_confirm(popup, logger=logger, W=W)
    wait_small(popup, W.LONGER)


def step_pick_materials_by_page(popup, pages_count, cfg, logger, W,
                                pick_min=30, pick_max=50, resume_position=None):
    """激励搭建：随机顺序选取素材（按页翻取，支持断点续选）"""
    import random
    logger.info("📦 进入素材编辑区域…")
    clear_btn = popup.locator("div.table-header:has(span:has-text('创意素材')) button:has-text('清空')").first
    if clear_btn.count() > 0:
        safe_click(popup, clear_btn, desc="清空创意素材", logger=logger, W=W)
        wait_small(popup, W.NORMAL)

    edit3 = popup.locator("tfoot td button:has-text('编辑')").nth(2)
    safe_click(popup, edit3, desc="编辑按钮(素材)", logger=logger, W=W)
    wait_small(popup, W.EXTRA)

    batch_add_btn = popup.locator("button:has-text('批量添加素材')").first
    safe_click(popup, batch_add_btn, desc="批量添加素材", logger=logger, W=W)
    wait_small(popup, W.EXTRA)

    tab_media = popup.locator("#tab-account-material")
    safe_click(popup, tab_media, desc="素材账户tab", logger=logger, W=W)
    wait_small(popup, W.LONGER)

    material_dlg = popup.locator("div.el-dialog:visible").last
    pane = material_dlg.locator("#pane-account-material")

    batch_icon = pane.locator("div.cl-input-area-trigger__icon[title='批量输入']").first
    batch_icon.click(force=True)
    wait_small(popup, W.LONG)
    id_input = popup.locator("input[placeholder*='请粘贴或输入账户ID']").last
    id_input.wait_for(state="visible", timeout=TIMEOUT)
    id_input.click(force=True)
    wait_small(popup, W.SHORT)
    id_input.fill(cfg["material_account_id"])
    wait_small(popup, W.MEDIUM)
    logger.info(f"🧾 固定素材账号已填入: {cfg['material_account_id']}")

    safe_click(popup, popup.locator("button.el-button--primary:visible").filter(has_text="搜索").last, desc="搜索素材", logger=logger, W=W)
    wait_small(popup, W.SEARCH)

    material_dlg = popup.locator("div.el-dialog:visible").last
    material_dlg.wait_for(state="visible", timeout=TIMEOUT)
    pane = material_dlg.locator("#pane-account-material")
    logger.info("📦 素材选择弹窗已打开")

    _configure_material_filters(popup, pane, material_dlg, logger, W)

    material_wrapper = pane.locator("div.material-wrapper").first
    material_wrapper.wait_for(state="visible", timeout=TIMEOUT)
    wait_loading_gone(popup, material_wrapper, timeout=30_000)

    # 读取分页总数，用于判断本页期望加载多少条
    from backend.core.material_ops import _get_material_total
    page_total = _get_material_total(pane)
    # 100条/页时，首页期望加载 min(100, total)
    expected_on_page = min(100, page_total) if page_total and page_total > 0 else 50
    logger.info(f"📊 分页总数: {page_total or '未知'}, 本页期望加载: {expected_on_page} 条")

    load_start = time.time()
    load_deadline = load_start + 90  # 加长超时到90s，100条加载较慢
    loaded = False
    stable_count = -1
    stable_since = 0.0
    # 动态稳定阈值：数量达到期望值才可快速放行，未达到则必须等到超时
    STABLE_THRESHOLD_FULL = 3.0   # 达到期望数量后稳定3秒即可
    MIN_MATERIAL_COUNT = 10
    while time.time() < load_deadline:
        loading_mask = material_wrapper.locator(".el-loading-mask").first
        if loading_mask.count() > 0:
            try:
                style = loading_mask.get_attribute("style") or ""
            except Exception:
                style = ""
            if "display: none" not in style:
                stable_count = -1
                wait_small(popup, W.LONG)
                continue
        current = material_wrapper.locator("div.material-name").count()
        if current >= MIN_MATERIAL_COUNT:
            if current != stable_count:
                stable_count = current
                stable_since = time.time()
                wait_small(popup, W.LONG)
                continue
            # 只有达到期望数量才可放行；未达到则持续等待直到超时
            if current >= expected_on_page:
                if time.time() - stable_since >= STABLE_THRESHOLD_FULL:
                    logger.info(f"✅ 素材列表已加载 | {current} 个素材名 (期望 {expected_on_page}, 耗时 {fmt_duration(time.time() - load_start)})")
                    loaded = True
                    break
        wait_small(popup, W.EXTRA)
    if not loaded:
        if stable_count > 0:
            logger.info(f"⏳ 素材列表加载超时但已有 {stable_count} 个素材名（期望 {expected_on_page}），继续选取")
            loaded = True
        else:
            logger.error("❌ 素材加载超时(90s)")
            cancel_btn = material_dlg.locator("button:visible").filter(has_text="取消").last
            if cancel_btn.count() > 0:
                cancel_btn.click(force=True)
            return resume_position
    wait_loading_gone(popup, material_wrapper)

    used_names = get_used_material_names()
    if used_names:
        logger.info(f"📋 已排除历史素材 {len(used_names)} 条")

    pick_count = random.randint(pick_min, pick_max)
    logger.info(f"🎯 本次目标选取: {pick_count} 条素材")

    start_page = (resume_position or {}).get("page", 0)
    start_offset = (resume_position or {}).get("offset", 0)

    if start_page > 0:
        _go_to_material_page(popup, pane, start_page + 1, logger, W)
        wait_loading_gone(popup, material_wrapper, timeout=10_000)
        logger.info(f"📄 从上次结束位置继续: 第 {start_page + 1} 页, 偏移 {start_offset}")

    picked_count = 0
    chosen_names = []
    current_page = start_page
    global_offset = start_offset

    while picked_count < pick_count:
        # ── 按位置顺序直接遍历素材卡片，逐个点击 ──
        # 参考原版脚本：不按名称查找，而是直接遍历 material-item 卡片
        # 这样即使平台上有大量同名素材，也只跳过"这张卡片"而非所有同名卡
        try:
            material_wrapper.evaluate("el => el.scrollTop = 0")
        except Exception as e:
            logger.warning(f"step_pick_materials_by_page 滚动到顶部失败: {e}")
        wait_small(popup, W.SHORT)

        # 等待卡片出现
        try:
            material_wrapper.locator("div.material-item").first.wait_for(state="visible", timeout=15_000)
        except Exception:
            logger.warning(f"⚠️ 第 {current_page + 1} 页无素材卡片，跳过")
            if not _has_next_material_page(pane):
                break
            if not _go_to_next_material_page(popup, pane, logger, W):
                break
            current_page += 1
            global_offset = 0
            continue
        wait_small(popup, W.NORMAL)

        cards = material_wrapper.locator("div.material-item")
        total_cards = cards.count()
        logger.info(f"📄 第 {current_page + 1} 页共 {total_cards} 个素材卡片")

        skip_on_page = 0
        pick_on_page = 0
        page_selected_set = set()  # 本页内已选集合，防同页重名重复点击

        start_idx = global_offset if current_page == start_page else 0
        for i in range(start_idx, total_cards):
            if picked_count >= pick_count:
                break
            card = cards.nth(i)
            # 读取素材名称
            name_el = card.locator("div.material-name").first
            try:
                mat_name = name_el.inner_text(timeout=3_000).strip() if name_el.count() > 0 else ""
            except Exception:
                mat_name = ""

            # 跳过已用过的素材（历史记录）
            if mat_name and mat_name in used_names:
                skip_on_page += 1
                continue

            # 跳过本页内已选过的同名素材（同页重名视为同一素材的不同上传）
            if mat_name and mat_name in page_selected_set:
                skip_on_page += 1
                continue

            # 选中这个素材卡片
            try:
                card.scroll_into_view_if_needed()
                wait_small(popup, W.TINY)
                card.click(force=True)
                wait_small(popup, W.TINY)
                record_name = mat_name if mat_name else f"未知素材_{int(time.time())}_{i}"
                picked_count += 1
                pick_on_page += 1
                chosen_names.append(record_name)
                if mat_name:
                    page_selected_set.add(mat_name)
            except Exception as e:
                # DOM detached 通常是列表重新渲染导致，尝试重新获取卡片
                if "not attached to the DOM" in str(e) or "not stable" in str(e):
                    try:
                        wait_small(popup, W.SHORT)
                        # 重新获取卡片列表并重试该索引
                        _retry_cards = material_wrapper.locator("div.material-item")
                        if i < _retry_cards.count():
                            _retry_card = _retry_cards.nth(i)
                            _retry_card.scroll_into_view_if_needed()
                            wait_small(popup, W.TINY)
                            _retry_card.click(force=True)
                            wait_small(popup, W.TINY)
                            record_name = mat_name if mat_name else f"未知素材_{int(time.time())}_{i}"
                            picked_count += 1
                            pick_on_page += 1
                            chosen_names.append(record_name)
                            if mat_name:
                                page_selected_set.add(mat_name)
                            continue
                    except Exception:
                        pass
                logger.warning(f"step_pick_materials_by_page 点击素材卡片失败: {e}")

        if skip_on_page > 0:
            logger.info(f"⏭️ 第 {current_page + 1} 页跳过 {skip_on_page} 条（已用/重名）")
        if pick_on_page > 0:
            logger.info(f"✅ 第 {current_page + 1} 页选取 {pick_on_page} 条 (累计 {picked_count}/{pick_count})")

        if picked_count >= pick_count:
            break

        if not _has_next_material_page(pane):
            logger.info("📄 已到最后一页，无更多素材")
            break
        if not _go_to_next_material_page(popup, pane, logger, W):
            break
        # 翻页后等待新页面素材加载完成（与首页相同的稳定检测逻辑）
        wait_loading_gone(popup, material_wrapper, timeout=30_000)
        _page_load_start = time.time()
        _page_load_deadline = _page_load_start + 60
        _pg_stable_count = -1
        _pg_stable_since = 0.0
        # 翻页后即将进入 current_page+1 页（0-based），计算该页期望加载条数
        _next_page = current_page + 1  # 即将进入的页码（0-based）
        if page_total and page_total > 0:
            _items_before_next = (_next_page) * 100  # 前面所有页的总条数
            _remaining = page_total - _items_before_next
            # 非末页: 期望100条；末页: 期望剩余条数（至少1）
            _pg_expected = min(100, max(1, _remaining)) if _remaining < 100 else 100
        else:
            _pg_expected = 100  # 无总数信息时默认期望100条
        while time.time() < _page_load_deadline:
            _pg_mask = material_wrapper.locator(".el-loading-mask").first
            if _pg_mask.count() > 0:
                try:
                    _pg_style = _pg_mask.get_attribute("style") or ""
                except Exception:
                    _pg_style = ""
                if "display: none" not in _pg_style:
                    _pg_stable_count = -1
                    wait_small(popup, W.LONG)
                    continue
            _pg_current = material_wrapper.locator("div.material-name").count()
            if _pg_current >= 1:
                if _pg_current != _pg_stable_count:
                    _pg_stable_count = _pg_current
                    _pg_stable_since = time.time()
                    wait_small(popup, W.LONG)
                    continue
                # 只有达到期望数量才可放行；未达到则持续等待直到超时
                if _pg_current >= _pg_expected:
                    if time.time() - _pg_stable_since >= STABLE_THRESHOLD_FULL:
                        logger.info(f"📄 第 {current_page + 2} 页素材已加载: {_pg_current} 条 (期望 {_pg_expected}, 耗时 {fmt_duration(time.time() - _page_load_start)})")
                        break
            wait_small(popup, W.EXTRA)
        current_page += 1
        global_offset = 0

    new_resume = {"page": current_page, "offset": global_offset}
    logger.info(f"📦 素材选取完成: 已选 {picked_count}/{pick_count} 条 | 结束位置: 第{current_page+1}页 偏移{global_offset}")

    if picked_count == 0:
        logger.warning("⚠️ 没有选到任何素材")
        cancel_btn = material_dlg.locator("button:visible").filter(has_text="取消").last
        if cancel_btn.count() > 0:
            cancel_btn.click(force=True)
            wait_small(popup, W.NORMAL)
        return new_resume

    submit_btn = material_dlg.locator("button.submit-button:visible").last
    if submit_btn.count() > 0:
        safe_click(popup, submit_btn, desc="素材提交按钮", logger=logger, W=W)
    else:
        safe_click(popup, material_dlg.locator("button:visible").filter(has_text="提交").last, desc="素材提交(备选)", logger=logger, W=W)
    click_optional_confirm(popup, desc="素材提交确认按钮", timeout=8_000, logger=logger, W=W)
    try:
        material_dlg.wait_for(state="hidden", timeout=20_000)
        logger.info("✅ 素材弹窗已关闭，已回到批量新建页面")
    except Exception:
        logger.warning("⚠️ 素材弹窗关闭等待超时，继续尝试后续提交")
    wait_idle(popup, mask_timeout=5_000)
    wait_small(popup, W.LOAD)

    add_material_history(chosen_names)
    logger.info(f"✅ 素材选择完成，已记录 {len(chosen_names)} 条素材到历史")
    return new_resume


# ═══════════════════════════════════════════════════════════════
#  激励搭建主流程
# ═══════════════════════════════════════════════════════════════

def run_build_incentive(profile_key: str, log_callback=None, stop_event=None):
    """激励搭建主入口"""
    app_cfg = load_config()
    cfg = build_runtime_profile_config(profile_key, app_cfg)
    cdp_endpoint = (app_cfg.get("common") or {}).get("cdp_endpoint") or "http://localhost:9222"
    pages_per_round = cfg.get("pages_per_round", 3)

    W = WaitTimes(cfg["wait_scale"])
    logger = setup_logger(cfg["log_dir"])

    if log_callback:
        class _GUIHandler(logging.Handler):
            def emit(self, record):
                try: log_callback(self.format(record))
                except Exception as e:
                    import logging as _logging
                    _logging.getLogger(__name__).warning(f"run_build_incentive GUI日志回调失败: {e}")
        gh = _GUIHandler()
        gh.setLevel(logging.INFO)
        gh.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
        logger.addHandler(gh)

    logger.info(f"🚀 开始激励搭建: {profile_key}")
    t0 = time.time()
    completed_groups = []
    failed_groups = []
    skipped_groups = []
    total_projects = 0
    success_account_ids = set()
    session_id = str(uuid.uuid4())

    groups = profile_groups_from_config(app_cfg, profile_key)
    if not groups:
        logger.error("❌ 没有读取到任何数据"); return

    logger.info(f"📦 共 {len(groups)} 组")

    resume_position = None

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(cdp_endpoint)
            if not browser.contexts:
                raise RuntimeError("已连接浏览器，但没有可用的浏览器上下文")
            context = browser.contexts[0]
            page = select_build_page(context, logger)
            logger.info("✅ 已连接浏览器")

            for g_idx, group_data in enumerate(groups, 1):
                check_stop(stop_event)
                ids = group_data[0]
                meta = group_data[2] if len(group_data) > 2 else {}
                group_name = meta.get("group_name", f"组{g_idx}")
                group_t0 = time.time()
                logger.info(f"\n{'='*50}\n📦 第 {g_idx}/{len(groups)} 组: {group_name} | 账号数: {len(ids)}\n{'='*50}")

                popup = None
                try:
                    check_stop(stop_event)
                    if page.is_closed():
                        page = select_build_page(context, logger)
                    # bring_to_front 已移除：无需置前，频繁弹台干扰用户

                    batch_btns = page.locator("button:has-text('批量新建')")
                    batch_count = 0
                    try: batch_count = batch_btns.count()
                    except Exception as e:
                        logger.warning(f"run_build_incentive 获取批量新建按钮数量失败: {e}")
                    if batch_count == 0:
                        page = select_build_page(context, logger)
                        batch_btns = page.locator("button:has-text('批量新建')")
                        try: batch_count = batch_btns.count()
                        except Exception as e:
                            logger.warning(f"run_build_incentive 重新获取批量新建按钮数量失败: {e}")
                            batch_count = 0
                    if batch_count == 0:
                        raise RuntimeError("当前页面没有找到【批量新建】按钮")
                    batch_btn = batch_btns.first
                    batch_btn.wait_for(state="visible", timeout=TIMEOUT)
                    batch_btn.scroll_into_view_if_needed()
                    try: expect(batch_btn).to_be_enabled(timeout=5_000)
                    except Exception as e:
                        logger.warning(f"run_build_incentive 等待批量新建按钮可用失败: {e}")
                    wait_idle(page, mask_timeout=3_000)

                    _prev_fg_hwnd = capture_foreground()
                    with page.expect_popup() as popup_info:
                        batch_btn.click(force=True)
                    popup = popup_info.value
                    popup.set_default_timeout(15_000)
                    # 立刻把焦点还给用户原本在用的软件
                    restore_foreground(_prev_fg_hwnd)
                    try: popup.wait_for_load_state("networkidle", timeout=60_000)
                    except PlaywrightTimeout: pass

                    check_stop(stop_event)
                    logger.info("➡️ 步骤1/8：选择策略")
                    step_select_strategy(popup, cfg, logger, W)
                    check_stop(stop_event)
                    logger.info("➡️ 步骤2/8：选择媒体账户")
                    step_select_media_accounts(popup, ids, cfg, logger, W)
                    check_stop(stop_event)
                    logger.info("➡️ 步骤3/8：关联产品（激励-空搜）")
                    step_link_product_incentive(popup, cfg, logger, W)
                    check_stop(stop_event)
                    logger.info("➡️ 步骤4/8：填写监测链接")
                    step_fill_monitor_links_incentive(popup, meta, cfg, logger, W)
                    check_stop(stop_event)
                    logger.info("➡️ 步骤5/8：选择定向包")
                    step_select_audience_package(popup, cfg, logger, W)
                    check_stop(stop_event)
                    logger.info("➡️ 步骤6/8：填写项目名称")
                    step_fill_project_name_incentive(popup, group_name, cfg, logger, W)
                    check_stop(stop_event)
                    logger.info("➡️ 步骤7/8：填写广告名称")
                    step_fill_ad_name_incentive(popup, group_name, cfg, logger, W)
                    check_stop(stop_event)
                    logger.info("➡️ 步骤8/8：顺序选取素材（30-50条）")
                    resume_position = step_pick_materials_by_page(popup, pages_per_round, cfg, logger, W, resume_position=resume_position)
                    check_stop(stop_event)
                    ad_count = step_submit_and_close(popup, page, logger, W)
                    completed_groups.append(group_name)
                    success_account_ids.update(ids)
                    total_projects += len(ids)
                    group_elapsed = time.time() - group_t0
                    if ad_count:
                        logger.info(f"✅ {group_name} 搭建完成（{len(ids)} 个账号，预估 {ad_count} 条广告），用时 {fmt_duration(group_elapsed)}")
                    else:
                        logger.info(f"✅ {group_name} 搭建完成（{len(ids)} 个账号），用时 {fmt_duration(group_elapsed)}")

                except AccountsMissingError as e:
                    failed_groups.append(group_name)
                    skipped_groups.append(f"第{g_idx}组")
                    logger.error(f"❌ 媒体账户缺失: {e}")
                    try:
                        if popup: popup.close()
                    except Exception as e:
                        logger.warning(f"run_build_incentive 关闭弹窗失败(AccountsMissingError): {e}")
                    continue
                except StopRequested:
                    logger.info("⏹ 用户中止")
                    try:
                        if popup: popup.close()
                    except Exception as e:
                        logger.warning(f"run_build_incentive 关闭弹窗失败(StopRequested): {e}")
                    raise
                except Exception as e:
                    failed_groups.append(group_name)
                    logger.error(f"❌ {group_name} 搭建失败: {e}")
                    try:
                        if popup: popup.close()
                    except Exception as e:
                        logger.warning(f"run_build_incentive 关闭弹窗失败: {e}")
    except StopRequested:
        logger.info("⏹ 已停止"); return

    elapsed = time.time() - t0
    logger.info(f"\n📊 搭建结果：成功 {len(completed_groups)} 组，失败 {len(failed_groups)} 组，账户缺失跳过 {len(skipped_groups)} 组")
    if skipped_groups:
        logger.warning(f"\n⚠️ 账户缺失跳过的组：{', '.join(skipped_groups)}")
    if failed_groups:
        logger.error("\n❌ 未搭建完成组汇总：")
        for name in failed_groups:
            logger.error(f"  {name}")
    logger.info(f"\n🎉 全部完成! 总耗时: {fmt_duration(elapsed)}")

    if completed_groups:
        record_build_success(len(success_account_ids), total_projects, session_id)
        logger.info(f"📝 基建记录已更新：账户 {len(success_account_ids)} 个，项目 {total_projects} 个")
        logger.info(f"📝 本次账户ID: {', '.join(sorted(success_account_ids))}")
