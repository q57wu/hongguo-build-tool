"""
backend/core/incentive_steps.py
激励搭建步骤函数。
"""
import re
import time
import math
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
    _get_material_list_wrapper,
    _select_media_material_tab,
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
                                pick_min=30, pick_max=50, resume_position=None,
                                material_lock=None, page_coordinator=None,
                                worker_id=0):
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

    material_dlg = popup.locator("div.el-dialog:visible").last
    pane = _select_media_material_tab(popup, material_dlg, logger, W)

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
    pane = _select_media_material_tab(popup, material_dlg, logger, W)
    logger.info("📦 素材选择弹窗已打开")

    actual_page_size = _configure_material_filters(popup, pane, material_dlg, logger, W)
    if actual_page_size is None:
        actual_page_size = 100  # backward compat default

    material_wrapper = _get_material_list_wrapper(pane)
    material_wrapper.wait_for(state="visible", timeout=TIMEOUT)
    wait_loading_gone(popup, material_wrapper, timeout=30_000)

    # 读取分页总数，用于判断本页期望加载多少条
    from backend.core.material_ops import _get_material_total
    page_total = _get_material_total(pane)
    # 按实际每页条数计算首页期望加载数量
    expected_on_page = min(actual_page_size, page_total) if page_total and page_total > 0 else min(actual_page_size, 50)
    logger.info(f"📊 分页总数: {page_total or '未知'}, 每页条数: {actual_page_size}, 本页期望加载: {expected_on_page} 条")

    # 上报实际总页数给 coordinator（如果有）
    if page_coordinator and page_total and actual_page_size > 0:
        actual_total_pages = math.ceil(page_total / actual_page_size)
        page_coordinator.update_total_pages(actual_total_pages)
        logger.info(f"📊 已上报实际总页数: {actual_total_pages} 页")

    load_start = time.time()
    load_deadline = load_start + 90
    loaded = False
    stable_count = -1
    stable_since = 0.0
    STABLE_THRESHOLD_FULL = 2.0 if actual_page_size < 50 else 3.0
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
        current = material_wrapper.locator(".material-name:visible").count()
        if current > 0:
            if current != stable_count:
                stable_count = current
                stable_since = time.time()
                wait_small(popup, W.LONG)
                continue
            if time.time() - stable_since >= STABLE_THRESHOLD_FULL:
                logger.info(f"✅ 素材列表已加载 | 当前可见 {current} 个素材名 (耗时 {fmt_duration(time.time() - load_start)})")
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

    if page_coordinator:
        # coordinator 已在启动时加载历史，直接用内存集合的快照做本地缓存
        used_names = set()  # 本地缓存仅用于快速跳过，真正去重靠 coordinator.try_reserve_material
        _used_count = page_coordinator.get_used_count()
        logger.info(f"📋 共享去重集合已有 {_used_count} 条素材（含历史 + 其他 worker 已选）")
    elif material_lock:
        with material_lock:
            used_names = get_used_material_names()
    else:
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

    # ── 逐页扫描选取素材（不跳页）──
    # 从起始页开始逐页逐卡片扫描，每个素材名称与 used_names 比对，
    # 未用过则选中，直到达到目标数量。不做任何跳页估算。

    while picked_count < pick_count:
        # ── coordinator: 认领当前页 ──
        if page_coordinator:
            if not page_coordinator.claim_page(worker_id, current_page):
                # 当前页正被其他 worker 扫描，跳过
                logger.info(f"⏭️ 第 {current_page + 1} 页正在被其他 worker 扫描，跳过")
                next_p = page_coordinator.suggest_next_page(worker_id, current_page)
                if next_p is None:
                    logger.info("📄 coordinator: 无更多可扫页面")
                    break
                if not _go_to_material_page(popup, pane, next_p + 1, logger, W):
                    logger.warning(f"⚠️ 跳转到第 {next_p + 1} 页失败")
                    break
                current_page = next_p
                global_offset = 0
                material_wrapper = _get_material_list_wrapper(pane)
                wait_loading_gone(popup, material_wrapper, timeout=10_000)
                continue

        # ── Fix 2: 基于滚动的遍历替代索引遍历，兼容虚拟滚动 ──
        # 每次滚动到当前视口，读取已渲染（非空）的卡片，处理后再下滚一屏
        # 等待卡片出现
        try:
            material_wrapper.locator("div.material-item").first.wait_for(state="visible", timeout=15_000)
        except Exception:
            logger.warning(f"⚠️ 第 {current_page + 1} 页无素材卡片，跳过")
            if page_coordinator:
                page_coordinator.release_page(worker_id, current_page)
            if not _has_next_material_page(pane):
                break
            if not _go_to_next_material_page(popup, pane, logger, W):
                break
            current_page += 1
            global_offset = 0
            continue
        wait_small(popup, W.NORMAL)

        # 获取 material-wrapper 视口高度，用于每次滚动步长
        try:
            viewport_height = material_wrapper.evaluate("el => el.clientHeight") or 600
        except Exception:
            viewport_height = 600

        # 滚动到顶部开始
        try:
            material_wrapper.evaluate("el => el.scrollTop = 0")
        except Exception as e:
            logger.warning(f"step_pick_materials_by_page 滚动到顶部失败: {e}")
        wait_small(popup, W.SHORT)

        total_cards = material_wrapper.locator("div.material-item").count()
        logger.info(f"📄 第 {current_page + 1} 页 DOM 中共 {total_cards} 个素材卡片（含虚拟滚动空壳）")

        # Fix 3: 分离跳过计数器
        skip_history = 0   # 历史记录命中
        skip_dedup = 0     # 本页内重名去重
        skip_empty = 0     # 虚拟滚动未渲染空壳
        pick_on_page = 0
        page_selected_set = set()  # 本页内已选集合，防同页重名重复点击
        seen_names_this_scroll = set()  # 当前滚动批次已处理的名称，用于检测翻到头

        scroll_rounds = 0
        max_scroll_rounds = 200
        no_new_rounds = 0

        while picked_count < pick_count and scroll_rounds < max_scroll_rounds:
            scroll_rounds += 1
            wait_small(popup, W.TINY)

            try:
                scroll_state = material_wrapper.evaluate(
                    "el => ({top: el.scrollTop, height: el.clientHeight, total: el.scrollHeight})"
                )
            except Exception:
                scroll_state = {"top": 0, "height": viewport_height, "total": viewport_height}
            scroll_top = float(scroll_state.get("top") or 0)
            scroll_height = float(scroll_state.get("height") or viewport_height or 600)
            scroll_total = float(scroll_state.get("total") or scroll_height)
            at_bottom_before = scroll_top + scroll_height >= scroll_total - 8

            cards = material_wrapper.locator("div.material-item:visible")
            batch_count = cards.count()
            new_names_this_round = 0
            batch_had_any_rendered = False

            for i in range(batch_count):
                if picked_count >= pick_count:
                    break
                card = cards.nth(i)

                try:
                    name_el = card.locator(".material-name:visible").first
                    if name_el.count() > 0:
                        mat_name = (name_el.get_attribute("title") or "").strip()
                        if not mat_name:
                            mat_name = name_el.inner_text(timeout=2_000).strip()
                    else:
                        mat_name = ""
                except Exception:
                    mat_name = ""

                if not mat_name:
                    skip_empty += 1
                    continue

                batch_had_any_rendered = True
                if mat_name not in seen_names_this_scroll:
                    new_names_this_round += 1
                else:
                    continue

                if mat_name in used_names or (page_coordinator and page_coordinator.is_material_used(mat_name)):
                    skip_history += 1
                    seen_names_this_scroll.add(mat_name)
                    continue

                if mat_name in page_selected_set:
                    skip_dedup += 1
                    seen_names_this_scroll.add(mat_name)
                    continue

                try:
                    # ── 去重判断：优先用 coordinator 内存去重，否则回退文件锁 ──
                    if page_coordinator:
                        # 原子性 check-and-reserve，跨 worker 实时同步
                        if not page_coordinator.try_reserve_material(mat_name):
                            skip_history += 1
                            seen_names_this_scroll.add(mat_name)
                            used_names.add(mat_name)
                            continue
                        card.scroll_into_view_if_needed()
                        wait_small(popup, W.TINY)
                        card.click(force=True)
                        wait_small(popup, W.TINY)
                    elif material_lock:
                        with material_lock:
                            latest_used_names = get_used_material_names()
                            if mat_name in latest_used_names:
                                used_names.update(latest_used_names)
                                skip_history += 1
                                seen_names_this_scroll.add(mat_name)
                                should_skip = True
                            else:
                                should_skip = False
                        if should_skip:
                            continue
                        card.scroll_into_view_if_needed()
                        wait_small(popup, W.TINY)
                        card.click(force=True)
                        wait_small(popup, W.TINY)
                        with material_lock:
                            add_material_history([mat_name])
                    else:
                        card.scroll_into_view_if_needed()
                        wait_small(popup, W.TINY)
                        card.click(force=True)
                        wait_small(popup, W.TINY)
                    picked_count += 1
                    pick_on_page += 1
                    chosen_names.append(mat_name)
                    page_selected_set.add(mat_name)
                    seen_names_this_scroll.add(mat_name)
                    used_names.add(mat_name)
                except Exception as e:
                    if "not attached to the DOM" in str(e) or "not stable" in str(e):
                        try:
                            wait_small(popup, W.SHORT)
                            _retry_cards = material_wrapper.locator("div.material-item:visible")
                            if i < _retry_cards.count():
                                _retry_card = _retry_cards.nth(i)
                                # 重试时同样用 coordinator 去重
                                if page_coordinator:
                                    if not page_coordinator.try_reserve_material(mat_name):
                                        skip_history += 1
                                        seen_names_this_scroll.add(mat_name)
                                        used_names.add(mat_name)
                                        continue
                                    _retry_card.scroll_into_view_if_needed()
                                    wait_small(popup, W.TINY)
                                    _retry_card.click(force=True)
                                    wait_small(popup, W.TINY)
                                elif material_lock:
                                    with material_lock:
                                        latest_used_names = get_used_material_names()
                                        if mat_name in latest_used_names:
                                            used_names.update(latest_used_names)
                                            skip_history += 1
                                            seen_names_this_scroll.add(mat_name)
                                            should_skip = True
                                        else:
                                            should_skip = False
                                    if should_skip:
                                        continue
                                    _retry_card.scroll_into_view_if_needed()
                                    wait_small(popup, W.TINY)
                                    _retry_card.click(force=True)
                                    wait_small(popup, W.TINY)
                                    with material_lock:
                                        add_material_history([mat_name])
                                else:
                                    _retry_card.scroll_into_view_if_needed()
                                    wait_small(popup, W.TINY)
                                    _retry_card.click(force=True)
                                    wait_small(popup, W.TINY)
                                picked_count += 1
                                pick_on_page += 1
                                chosen_names.append(mat_name)
                                page_selected_set.add(mat_name)
                                seen_names_this_scroll.add(mat_name)
                                used_names.add(mat_name)
                                continue
                        except Exception:
                            pass
                    logger.warning(f"step_pick_materials_by_page 点击素材卡片失败: {e}")

            no_new_rounds = no_new_rounds + 1 if new_names_this_round == 0 else 0
            if at_bottom_before and no_new_rounds >= 2:
                logger.debug(f"🔚 第 {current_page + 1} 页已滚到底且连续无新素材（第 {scroll_rounds} 轮）")
                break

            try:
                before_top = material_wrapper.evaluate("el => el.scrollTop") or 0
                material_wrapper.evaluate(
                    "(el, step) => { el.scrollTop = Math.min(el.scrollTop + step, el.scrollHeight); }",
                    max(300, int(viewport_height * 0.85)),
                )
                wait_small(popup, W.SHORT)
                after_state = material_wrapper.evaluate(
                    "el => ({top: el.scrollTop, height: el.clientHeight, total: el.scrollHeight})"
                )
                after_top = float(after_state.get("top") or 0)
                after_bottom = after_top + float(after_state.get("height") or viewport_height or 600) >= float(after_state.get("total") or 0) - 8
                if after_top <= float(before_top) + 2 and after_bottom:
                    no_new_rounds += 1
            except Exception:
                break
            wait_small(popup, W.SHORT)

        # Fix 3: 分类记录跳过日志
        if skip_empty > 0:
            logger.debug(f"🕳️ 第 {current_page + 1} 页跳过 {skip_empty} 个空壳卡片（虚拟滚动未渲染）")
        if skip_history > 0:
            logger.info(f"⏭️ 第 {current_page + 1} 页跳过 {skip_history} 条（历史已用）")
        if skip_dedup > 0:
            logger.info(f"⏭️ 第 {current_page + 1} 页跳过 {skip_dedup} 条（本页重名去重）")
        if pick_on_page > 0:
            logger.info(f"✅ 第 {current_page + 1} 页选取 {pick_on_page} 条 (累计 {picked_count}/{pick_count})")

        # ── coordinator: 释放当前页 ──
        if page_coordinator:
            page_coordinator.release_page(worker_id, current_page)

        if picked_count >= pick_count:
            break

        # ── 决定下一页 ──
        if page_coordinator:
            next_p = page_coordinator.suggest_next_page(worker_id, current_page)
            if next_p is None:
                logger.info("📄 coordinator: 无更多可扫页面（已遍历一圈）")
                break
            # 如果建议页就是下一页且有下一页按钮，用简单翻页（更快更稳）
            if next_p == current_page + 1 and _has_next_material_page(pane):
                if not _go_to_next_material_page(popup, pane, logger, W):
                    break
            else:
                logger.info(f"🔄 coordinator 建议跳转: 第{current_page + 1}页 → 第{next_p + 1}页")
                if not _go_to_material_page(popup, pane, next_p + 1, logger, W):
                    logger.warning(f"⚠️ 跳转到第 {next_p + 1} 页失败")
                    break
        else:
            # 无 coordinator：原有逻辑
            if not _has_next_material_page(pane):
                logger.info("📄 已到最后一页，无更多素材")
                break
            if not _go_to_next_material_page(popup, pane, logger, W):
                break
        material_wrapper = _get_material_list_wrapper(pane)
        wait_loading_gone(popup, material_wrapper, timeout=30_000)
        _page_load_start = time.time()
        _page_load_deadline = _page_load_start + 60
        _pg_stable_count = -1
        _pg_stable_since = 0.0
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
            _pg_current = material_wrapper.locator(".material-name:visible").count()
            if _pg_current >= 1:
                if _pg_current != _pg_stable_count:
                    _pg_stable_count = _pg_current
                    _pg_stable_since = time.time()
                    wait_small(popup, W.LONG)
                    continue
                if time.time() - _pg_stable_since >= STABLE_THRESHOLD_FULL:
                    logger.info(f"📄 新页素材已加载: 当前可见 {_pg_current} 条 (耗时 {fmt_duration(time.time() - _page_load_start)})")
                    break
            wait_small(popup, W.EXTRA)
        if page_coordinator:
            # 跳页模式下，从 pane 获取真实当前页码
            from backend.core.material_ops import _get_active_material_page
            current_page = _get_active_material_page(pane) - 1  # 0-based
        else:
            current_page += 1
        global_offset = 0

    new_resume = {"page": current_page, "offset": global_offset}
    if picked_count < pick_count:
        _used_total = page_coordinator.get_used_count() if page_coordinator else len(used_names)
        logger.warning(
            f"⚠️ 素材选取不足: 目标 {pick_count} 条，实际仅选到 {picked_count} 条"
            f"（已扫描至第 {current_page + 1} 页）。"
            f"可能原因：可用新素材总量不足，或历史已用素材 ({_used_total} 条) 覆盖了大部分库存。"
        )
        try:
            from backend.utils.diagnostics import dump_page_structure
            dump_page_structure(popup, logger=logger, reason="incentive material picked insufficient")
        except Exception:
            pass
    logger.info(f"📦 素材选取完成: 已选 {picked_count}/{pick_count} 条 | 结束位置: 第{current_page+1}页 偏移{global_offset}")

    if picked_count == 0:
        logger.warning("⚠️ 没有选到任何素材")
        cancel_btn = material_dlg.locator("button:visible").filter(has_text="取消").last
        if cancel_btn.count() > 0:
            cancel_btn.click(force=True)
            wait_small(popup, W.NORMAL)
        new_resume["picked_count"] = picked_count
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

    logger.info(f"✅ 素材选择完成，已记录 {len(chosen_names)} 条素材到历史")

    # coordinator 模式下，选取过程中只做内存去重，结束时批量持久化到文件
    if page_coordinator and chosen_names:
        try:
            add_material_history(chosen_names)
            logger.info(f"💾 已批量写入 {len(chosen_names)} 条素材到历史文件")
        except Exception as e:
            logger.warning(f"⚠️ 批量写入素材历史失败: {e}")

    new_resume["picked_count"] = picked_count

    try:
        # Check if drawer is still visible before trying to close
        visible_drawers = popup.locator("div.drawer-content:visible")
        if visible_drawers.count() == 0:
            logger.info("✅ 素材编辑抽屉已自动关闭")
        else:
            drawer, wrap = get_visible_drawer(popup)
            scroll_wrap_to_bottom(popup, wrap, W)
            try:
                click_top_confirm(popup, logger=logger, W=W, timeout=8_000)
            except Exception:
                # Confirm button not found, try Escape
                try:
                    popup.keyboard.press("Escape")
                    wait_small(popup, W.NORMAL)
                except Exception:
                    pass
            wait_small(popup, W.LONGER)
            # Final check
            if popup.locator("div.drawer-content:visible").count() == 0:
                logger.info("✅ 素材编辑抽屉已关闭")
            else:
                logger.warning("⚠️ 素材编辑抽屉仍未关闭，尝试Escape")
                try:
                    popup.keyboard.press("Escape")
                    wait_small(popup, W.NORMAL)
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"⚠️ 关闭素材编辑抽屉失败(忽略继续): {e}")

    return new_resume


def step_pick_materials_by_ids_incentive(popup, material_ids, cfg, logger, W):
    """激励搭建：使用自定义素材ID选取素材（复用单本的素材ID逻辑，适配激励UI入口）"""
    logger.info(f"🎯 使用自定义素材ID逻辑，共 {len(material_ids)} 个")
    logger.info("📦 进入素材编辑区域…")

    # 清空已有素材
    clear_btn = popup.locator("div.table-header:has(span:has-text('创意素材')) button:has-text('清空')").first
    if clear_btn.count() > 0:
        safe_click(popup, clear_btn, desc="清空创意素材", logger=logger, W=W)
        wait_small(popup, W.NORMAL)

    # 点击第3个编辑按钮（素材区域）
    edit3 = popup.locator("tfoot td button:has-text('编辑')").nth(2)
    safe_click(popup, edit3, desc="编辑按钮(素材)", logger=logger, W=W)
    wait_small(popup, W.EXTRA)

    # 批量添加素材
    batch_add_btn = popup.locator("button:has-text('批量添加素材')").first
    safe_click(popup, batch_add_btn, desc="批量添加素材", logger=logger, W=W)
    wait_small(popup, W.EXTRA)

    # 切到素材账户tab
    material_dlg = popup.locator("div.el-dialog:visible").last
    pane = _select_media_material_tab(popup, material_dlg, logger, W)

    # 输入素材账户ID
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

    # 切换搜索类型到"素材ID"
    try:
        search_select = pane.locator("div.cl-search-input div.el-select, div.cl-input-area div.el-select").first
        if search_select.count() > 0:
            select_input = search_select.locator("input.el-input__inner").first
            safe_click(popup, select_input, desc="搜索类型下拉", logger=logger, W=W)
            wait_small(popup, W.NORMAL)
            dropdown = popup.locator("ul.el-select-dropdown__list:visible").last
            dropdown.wait_for(state="visible", timeout=TIMEOUT)
            id_option = dropdown.locator("li.el-select-dropdown__item").filter(has_text="素材ID").first
            if id_option.count() > 0:
                safe_click(popup, id_option, desc="选择素材ID", logger=logger, W=W)
                wait_small(popup, W.MEDIUM)
    except Exception as e:
        logger.warning(f"⚠️ 切换搜索类型失败: {e}")

    # 批量搜索图标
    batch_search_icon = pane.locator("div.cl-search-input__suffix-icon[title='批量搜索']").first
    if batch_search_icon.count() == 0:
        batch_search_icon = pane.locator("[title='批量搜索']").first
    safe_click(popup, batch_search_icon, desc="批量搜索图标", logger=logger, W=W)
    wait_small(popup, W.LONG)

    # 输入素材ID
    batch_textarea = popup.locator("textarea:visible").last
    batch_input_el = popup.locator("input[placeholder*='请粘贴'], input[placeholder*='请输入'], input[placeholder*='素材']").last
    if batch_textarea.count() > 0:
        target_el = batch_textarea
    elif batch_input_el.count() > 0:
        target_el = batch_input_el
    else:
        target_el = None
    if target_el:
        target_el.wait_for(state="visible", timeout=TIMEOUT)
        target_el.click(force=True)
        wait_small(popup, W.SHORT)
        for mid in material_ids:
            popup.keyboard.type(str(mid))
            popup.keyboard.press("Enter")
        wait_small(popup, W.MEDIUM)
        logger.info(f"✅ 已逐行输入 {len(material_ids)} 个素材ID")

    # 点击搜索
    old_material_count = _get_material_list_wrapper(pane).locator("div.material-item").count()
    safe_click(popup, popup.locator("button.el-button--primary:visible").filter(has_text="搜索").last, desc="搜索素材ID", logger=logger, W=W)
    wait_small(popup, W.SEARCH)

    # 等待素材列表刷新
    material_dlg = popup.locator("div.el-dialog:visible").last
    material_dlg.wait_for(state="visible", timeout=TIMEOUT)
    pane = _select_media_material_tab(popup, material_dlg, logger, W)
    material_wrapper = _get_material_list_wrapper(pane)
    material_wrapper.wait_for(state="visible", timeout=TIMEOUT)
    expected_count = len(material_ids)
    load_deadline = time.time() + 60
    refreshed = False
    stable_count = -1
    stable_since = 0
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
        current_count = material_wrapper.locator("div.material-item").count()
        if current_count == expected_count and current_count > 0:
            refreshed = True
            break
        if current_count != stable_count:
            stable_count = current_count
            stable_since = time.time()
            wait_small(popup, W.LONG)
            continue
        if current_count == stable_count and (time.time() - stable_since) > 3:
            if current_count != old_material_count and current_count > 0:
                refreshed = True
                break
        wait_small(popup, W.LONG)
    if not refreshed:
        logger.error("❌ 素材列表刷新超时(60s)")
        cancel_btn = material_dlg.locator("button:visible").filter(has_text="取消").last
        if cancel_btn.count() > 0:
            cancel_btn.click(force=True)
        return 0

    wait_loading_gone(popup, material_wrapper)
    wait_small(popup, W.NORMAL)

    # 全选所有搜索到的素材
    cards = material_wrapper.locator("div.material-item")
    total = cards.count()
    picked = 0
    for i in range(total):
        try:
            safe_click(popup, cards.nth(i), desc=f"素材卡片{i+1}/{total}", logger=logger, W=W)
            wait_small(popup, W.TINY)
            picked += 1
        except Exception:
            pass
    if picked == 0:
        cancel_btn = material_dlg.locator("button:visible").filter(has_text="取消").last
        if cancel_btn.count() > 0:
            cancel_btn.click(force=True)
        return 0
    logger.info(f"✅ 已全选 {picked}/{total} 个素材")

    # 提交
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

    try:
        # Check if drawer is still visible before trying to close
        visible_drawers = popup.locator("div.drawer-content:visible")
        if visible_drawers.count() == 0:
            logger.info("✅ 素材编辑抽屉已自动关闭")
        else:
            drawer, wrap = get_visible_drawer(popup)
            scroll_wrap_to_bottom(popup, wrap, W)
            try:
                click_top_confirm(popup, logger=logger, W=W, timeout=8_000)
            except Exception:
                # Confirm button not found, try Escape
                try:
                    popup.keyboard.press("Escape")
                    wait_small(popup, W.NORMAL)
                except Exception:
                    pass
            wait_small(popup, W.LONGER)
            # Final check
            if popup.locator("div.drawer-content:visible").count() == 0:
                logger.info("✅ 素材编辑抽屉已关闭")
            else:
                logger.warning("⚠️ 素材编辑抽屉仍未关闭，尝试Escape")
                try:
                    popup.keyboard.press("Escape")
                    wait_small(popup, W.NORMAL)
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"⚠️ 关闭素材编辑抽屉失败(忽略继续): {e}")

    return picked


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
                    logger.info("➡️ 步骤8/8：选取素材")
                    custom_mids = meta.get("material_ids", []) if meta else []
                    if custom_mids:
                        logger.info(f"🎯 检测到自定义素材ID {len(custom_mids)} 个")
                        step_pick_materials_by_ids_incentive(popup, custom_mids, cfg, logger, W)
                    else:
                        logger.info("📦 使用随机翻页选取素材（30-50条）")
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
                    logger.info("⏹ 用户中止（保留当前标签页）")
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
