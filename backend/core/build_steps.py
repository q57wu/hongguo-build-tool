"""
backend/core/build_steps.py
单本搭建步骤函数。
"""
import re
import time
import logging
import threading
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout, expect
except ImportError:
    sync_playwright = None
    PlaywrightTimeout = Exception
    expect = None

# ── 常量 & 数据结构已迁移至 backend.core.constants ──
from backend.core.constants import (
    TIMEOUT,
    RE_CONFIRM,
    PROFILES,
    ALL_PROFILES,
    WaitTimes,
    AccountsMissingError,
    BuildSubmitError,
    StopRequested,
)

# ── 已迁移至独立模块的稳定符号 ──
from backend.core.playwright_utils import (
    safe_click, wait_small, wait_idle, wait_loading_gone,
    _locator_count, select_build_page, get_visible_drawer, get_visible_layer,
    scroll_wrap_to_bottom, scroll_to_module,
    click_top_confirm, click_optional_confirm,
    _safe_page_title, _safe_page_url,
    wait_locator_ready, safe_select_option,
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
    read_data, is_valid_material_name, extract_mmdd,
    build_runtime_profile_config, profile_groups_from_config,
)

# ── 异常处理（已迁移）──
from backend.core.exceptions import check_stop
from backend.utils.win_focus import capture_foreground, restore_foreground


# ═══════════════════════════════════════════════════════════════
#  搭建步骤函数（参数化）
# ═══════════════════════════════════════════════════════════════

def step_select_strategy(popup, cfg, logger, W):
    strategy_name = cfg["strategy"]
    logger.info('🔍 查找"选择策略"按钮，目标策略：' + str(strategy_name))
    strategy_buttons = popup.locator("button:has-text('选择策略')")
    try:
        logger.info('🔘 匹配到"选择策略"按钮：' + str(strategy_buttons.count()) + ' 个')
    except Exception as e:
        logger.warning(f"step_select_strategy 获取按钮数量失败: {e}")
    safe_click(popup, strategy_buttons.first, timeout=15_000, desc="选择策略按钮", logger=logger, W=W)
    wait_small(popup, W.MEDIUM)
    strategy_dlg = get_visible_layer(popup, desc="策略弹窗", timeout=15_000, logger=logger, W=W)
    wait_small(popup, W.LOAD)

    rows = strategy_dlg.locator("tbody tr.el-table__row, tbody tr, .el-table__row, tr")
    strategy_row = None
    last_seen = []
    deadline = time.time() + TIMEOUT / 1000
    while time.time() < deadline and strategy_row is None:
        try: rows.first.wait_for(state="visible", timeout=3_000)
        except PlaywrightTimeout:
            wait_small(popup, W.MEDIUM); continue
        row_count = rows.count()
        last_seen = []
        for i in range(row_count):
            row = rows.nth(i)
            cells = row.locator("td")
            try:
                row_text = re.sub(r"\s+", " ", row.inner_text()).strip()
                if row_text: last_seen.append(row_text)
            except Exception as e:
                logger.warning(f"step_select_strategy 读取行文本失败: {e}")
            for j in range(cells.count()):
                if cells.nth(j).inner_text().strip() == strategy_name:
                    strategy_row = row; break
            if strategy_row: break
        if not strategy_row: wait_small(popup, W.NORMAL)

    if not strategy_row:
        try:
            snapshot = re.sub(r"\s+", " ", strategy_dlg.inner_text(timeout=2_000)).strip()
            logger.warning(f"⚠️ 策略弹窗内容片段：{snapshot[:500]}")
        except Exception:
            pass
        raise Exception(f"❌ 未找到策略: {strategy_name}")

    strategy_row.wait_for(state="visible", timeout=TIMEOUT)
    strategy_row.locator("label.el-radio").first.click(force=True)
    wait_small(popup, W.SHORT)
    click_top_confirm(popup, strategy_dlg, desc="策略确认", wait_close=True, logger=logger, W=W)
    wait_small(popup, W.NORMAL)
    logger.info(f"📌 已选择策略: {strategy_name}")


def step_select_media_accounts(popup, ids, cfg, logger, W):
    popup.locator("div.selector:has(label:has-text('媒体账户')) button:has-text('更改')").click()
    wait_small(popup, W.LOAD)
    popup.locator("div.selected-card-header").first.wait_for(state="visible", timeout=TIMEOUT)
    popup.locator("div.selected-card-header button:has-text('清空')").first.click(force=True)
    wait_small(popup, W.MEDIUM)
    popup.get_by_label("选择媒体账户").get_by_title("批量搜索").click(force=True)

    id_input = popup.locator("input[placeholder='请粘贴或输入账户ID，回车可换行']")
    id_input.wait_for(state="visible", timeout=TIMEOUT)
    id_input.click()
    for _id in ids:
        popup.keyboard.type(_id)
        popup.keyboard.press("Enter")
    logger.info(f"📝 已输入 {len(ids)} 个媒体账户ID")

    popup.locator("button.el-button--primary:visible").filter(has_text="搜索").last.click(force=True)
    wait_small(popup, W.SEARCH)

    dlg_acc = popup.locator("div.el-dialog__wrapper:visible").last
    try: dlg_acc.locator("tbody tr").first.wait_for(state="visible", timeout=TIMEOUT)
    except PlaywrightTimeout: raise AccountsMissingError(list(ids), 0, len(ids))
    wait_small(popup, W.MEDIUM)

    # 检查账户行
    rows = dlg_acc.locator("div.el-table__fixed-body-wrapper tbody tr.el-table__row")
    row_count = rows.count()
    found_ids = set()
    for i in range(row_count):
        row = rows.nth(i)
        id_el = row.locator("td:nth-child(2) p").filter(has_text="ID：")
        if id_el.count() > 0:
            try:
                row_text = id_el.first.inner_text().strip()
                match = re.search(r'ID[：:]\s*(\d+)', row_text)
                if match: found_ids.add(match.group(1))
            except Exception as e:
                logger.warning(f"step_select_media_accounts 读取账户ID失败: {e}")
    missing = [_id for _id in ids if _id not in found_ids]
    if row_count < len(ids) or missing:
        if not missing: missing = [f"(未知缺失{len(ids) - row_count}个)"]
        raise AccountsMissingError(missing, row_count, len(ids))

    dlg_acc.locator("thead label.el-checkbox").first.click(force=True)
    click_top_confirm(popup, dlg_acc, desc="媒体账户确认", wait_close=True, logger=logger, W=W)
    wait_small(popup, W.LOAD)
    try: dlg_acc.wait_for(state="hidden", timeout=10_000)
    except Exception as e:
        logger.warning(f"step_select_media_accounts 等待对话框关闭失败: {e}")
    wait_small(popup, W.NORMAL)


def step_link_product(popup, drama_name, cfg, logger, W):
    try:
        popup.wait_for_load_state("networkidle", timeout=5_000)
    except PlaywrightTimeout:
        logger.warning("⚠️ 关联产品前等待网络空闲超时，继续执行")
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
    p_search = prod_dlg.locator("input[placeholder='请输入关键词']").first
    p_search.fill(drama_name)
    wait_small(popup, W.MEDIUM)
    safe_click(popup, prod_dlg.locator("button:has-text('查询')"), desc="查询产品", logger=logger, W=W)
    wait_small(popup, W.HEAVY)

    target_l = prod_dlg.locator(f"div.el-checkbox-group label.el-checkbox:has(div.product-name:has-text('{drama_name}'))")
    if target_l.count() == 0:
        p_search.fill("")
        safe_click(popup, prod_dlg.locator("button:has-text('查询')"), desc="查询全部产品", logger=logger, W=W)
        wait_small(popup, W.HEAVY)
        all_p = prod_dlg.locator("div.el-checkbox-group label.el-checkbox")
        total = all_p.count()
        if total == 0:
            logger.warning(f"⚠️ 未找到任何产品: {drama_name}"); target = None
        else:
            import random
            random_idx = random.randint(0, total - 1)
            target = all_p.nth(random_idx)
            logger.info(f"🎯 未匹配剧名『{drama_name}』，随机选中第 {random_idx + 1}/{total} 个产品")
    else:
        target = target_l.first
        logger.info(f"🎯 已匹配到剧名对应产品: {drama_name}")

    if target is not None:
        safe_click(popup, target, desc="选择产品项", logger=logger, W=W)
        click_top_confirm(popup, prod_dlg, desc="产品确认", wait_close=True, logger=logger, W=W)
        wait_small(popup, W.LONG)


def step_fill_monitor_links(popup, drama, cfg, logger, W):
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
    fill_link('请输入展示链接', drama["show"])
    logger.info("  展示链接☑️")
    fill_link('请输入有效触点链接', drama["click"])
    logger.info("  监测链接☑️")
    fill_link('请输入视频有效播放链接', drama["video"])
    logger.info("  播放链接☑️")
    logger.info(f"  ✅ 三个链接已填写完成")

    scroll_wrap_to_bottom(popup, monitor_wrap, W)
    click_top_confirm(popup, logger=logger, W=W)
    wait_small(popup, W.LONG)


def step_select_audience_package(popup, cfg, logger, W):
    drawer, wrap = get_visible_drawer(popup)
    scroll_to_module(popup, wrap, "audience-package", W)
    safe_click(popup, popup.locator("#audience-package button:has-text('选择定向包')"), desc="选择定向包按钮", logger=logger, W=W)

    search_box = popup.locator(".cl-search-input:visible").first
    wait_locator_ready(popup, search_box, desc="定向包搜索区", W=W)
    wait_loading_gone(popup, popup.locator("body"))
    keyword_input = search_box.locator("input.el-input__inner[placeholder='请输入关键词']")

    if keyword_input.count() > 0:
        try:
            wait_locator_ready(popup, keyword_input, desc="定向包关键词输入框", W=W)
            keyword_input.click(force=True)
            wait_small(popup, W.TINY)
            keyword_input.fill(cfg["audience_keyword"])
            wait_small(popup, W.SHORT)
            search_btn = search_box.locator("button[title='搜索']").first
            if search_btn.count() > 0:
                wait_locator_ready(popup, search_btn, desc="定向包搜索按钮", W=W)
                search_btn.click(force=True)
                wait_loading_gone(popup, popup.locator("body"))
                wait_small(popup, W.NORMAL)
        except Exception as e:
            logger.warning(f"⚠️ 定向包搜索出错: {e}")

    btn_m = popup.locator("button:has-text('多账户快速选择'):visible").last
    wait_locator_ready(popup, btn_m, desc="多账户快速选择按钮", W=W)
    safe_click(popup, btn_m, desc="多账户快速选择(第1次)", logger=logger, W=W)
    wait_loading_gone(popup, popup.locator("body"))
    wait_small(popup, W.LOAD)          # 等第1次点击的网络请求完成
    wait_locator_ready(popup, btn_m, desc="多账户快速选择按钮", W=W)
    safe_click(popup, btn_m, desc="多账户快速选择(第2次)", logger=logger, W=W)
    wait_loading_gone(popup, popup.locator("body"))
    wait_small(popup, W.LOAD)          # 等第2次点击的网络请求完成
    # 额外等一段时间确保所有账户勾选渲染完毕
    popup.wait_for_timeout(2000)
    click_top_confirm(popup, desc="定向包确认", logger=logger, W=W)
    wait_small(popup, W.LONG)


def step_fill_project_name(popup, drama_name, cfg, logger, W):
    drawer, wrap = get_visible_drawer(popup)
    scroll_to_module(popup, wrap, "project-name", W)
    operator_name = cfg.get("operator_name") or "lzp"
    project_name = f"{cfg['name_prefix']}-{drama_name}-{operator_name}-<日期>"
    name_input = popup.locator("#project-name input.el-input__inner").first
    name_input.wait_for(state="visible", timeout=TIMEOUT)
    name_input.click(force=True); name_input.fill("")
    wait_small(popup, W.TINY)
    name_input.fill(project_name)
    wait_small(popup, W.SHORT)

    try: actual_value = name_input.input_value().strip()
    except Exception as e:
        logger.warning(f"step_fill_project_name 获取输入值失败: {e}")
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


def step_fill_ad_name(popup, drama_name, cfg, logger, W):
    promo_block = popup.locator("div.module-container#promotion-name")
    edit_btn = popup.locator("tfoot td button:has-text('编辑')").nth(1)
    edit_btn.wait_for(state="visible", timeout=TIMEOUT)
    edit_btn.scroll_into_view_if_needed()

    last_err = None
    for _attempt in range(5):
        try: popup.keyboard.press("Escape")
        except Exception as e:
            logger.warning(f"step_fill_ad_name 按Escape失败: {e}")
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

    operator_name = cfg.get("operator_name") or "lzp"
    ad_name = f"{cfg['name_prefix']}-{drama_name}-{operator_name}-<日期>-<动态标号>"
    popup.locator("div.module-container#promotion-name").locator(
        "div.el-form-item:has(label:has-text('广告名称')) input.el-input__inner"
    ).first.fill(ad_name)
    logger.info(f"📝 广告名称: {ad_name}")

    drawer, wrap = get_visible_drawer(popup)
    scroll_wrap_to_bottom(popup, wrap, W)
    click_top_confirm(popup, logger=logger, W=W)
    wait_small(popup, W.LONGER)


def _pick_materials_by_keyword(popup, drama_name, cfg, logger, W):
    from backend.core.material_ops import (
        _open_material_dialog,
        _configure_material_filters,
        _collect_material_candidates,
        _select_and_submit_materials,
    )
    material_dlg, pane = _open_material_dialog(popup, drama_name, cfg, logger, W, use_keyword=True)
    _configure_material_filters(popup, pane, material_dlg, logger, W)
    available_candidates = _collect_material_candidates(
        popup, material_dlg, pane, drama_name, logger, W,
        is_valid_material_name, extract_mmdd, fmt_duration, TODAY_STR,
    )
    if not available_candidates:
        logger.warning(f"⚠️ 未找到可用素材: {drama_name}")
        cancel_btn = material_dlg.locator("button:visible").filter(has_text="取消").last
        if cancel_btn.count() > 0:
            cancel_btn.click(force=True)
            wait_small(popup, W.NORMAL)
        return 0
    return _select_and_submit_materials(popup, material_dlg, pane, available_candidates, drama_name, logger, W,
                                         fmt_duration)


def _pick_materials_by_ids(popup, drama_name, material_ids, cfg, logger, W):
    from backend.core.material_ops import (
        _open_material_dialog,
    )
    material_dlg, pane = _open_material_dialog(popup, drama_name, cfg, logger, W, use_keyword=False)
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
    batch_search_icon = pane.locator("div.cl-search-input__suffix-icon[title='批量搜索']").first
    if batch_search_icon.count() == 0:
        batch_search_icon = pane.locator("[title='批量搜索']").first
    safe_click(popup, batch_search_icon, desc="批量搜索图标", logger=logger, W=W)
    wait_small(popup, W.LONG)
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
    old_material_count = pane.locator("div.material-item").count()
    safe_click(popup, popup.locator("button.el-button--primary:visible").filter(has_text="搜索").last, desc="搜索素材ID", logger=logger, W=W)
    wait_small(popup, W.SEARCH)
    material_dlg = popup.locator("div.el-dialog:visible").last
    material_dlg.wait_for(state="visible", timeout=TIMEOUT)
    pane = material_dlg.locator("#pane-account-material")
    material_wrapper = pane.locator("div.material-wrapper").first
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
        current_count = pane.locator("div.material-item").count()
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
    cards = pane.locator("div.material-item")
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
    return picked


def step_pick_media_materials(popup, drama_name, material_ids, cfg, logger, W):
    if material_ids:
        logger.info(f"🎯 检测到配置内素材ID {len(material_ids)} 个，使用自定义素材ID逻辑")
        picked = _pick_materials_by_ids(popup, drama_name, material_ids, cfg, logger, W)
    else:
        logger.info("🎯 未检测到素材ID，使用普通按剧名筛素材逻辑")
        picked = _pick_materials_by_keyword(popup, drama_name, cfg, logger, W)
    if picked <= 0:
        raise Exception(f"❌ 未成功选择素材: {drama_name}")
    logger.info(f"✅ 素材已提交到创意素材区: {picked} 个")


def wait_return_to_main_after_material(popup, logger, W):
    logger.info("⏳ 等待返回 main 主界面")
    deadline = time.time() + 60
    selectors = [
        "main button:has-text('生成广告预览')",
        "#main button:has-text('生成广告预览')",
        ".main button:has-text('生成广告预览')",
        "div.main button:has-text('生成广告预览')",
        "button:has-text('生成广告预览')",
    ]
    while time.time() < deadline:
        wait_idle(popup, mask_timeout=2_000)
        for sel in selectors:
            btn = popup.locator(sel).first
            if _locator_count(btn) > 0:
                try:
                    btn.wait_for(state="visible", timeout=1_000)
                    logger.info(f"✅ 已回到 main 主界面，可生成广告预览：{sel}")
                    return btn
                except Exception as e:
                    logger.warning(f"wait_return_to_main_after_material 等待按钮可见失败: {e}")
        wait_small(popup, W.NORMAL)
    raise Exception('素材提交后未回到 main 主界面，未看到"生成广告预览"按钮')


def step_submit_and_close(popup, page, logger, W):
    logger.info("➡️ 最终提交1/5：生成广告预览")
    preview_btn = wait_return_to_main_after_material(popup, logger, W)
    safe_click(popup, preview_btn, desc="生成广告预览", logger=logger, W=W)
    logger.info("⏳ 已点击生成广告预览，等待预览生成完成")
    try:
        popup.locator(".el-loading-mask").first.wait_for(state="hidden", timeout=60_000)
    except Exception as e:
        logger.warning(f"step_submit_and_close 等待加载遮罩消失失败: {e}")
    wait_idle(popup, mask_timeout=5_000)

    logger.info("➡️ 最终提交2/5：等待提交审核按钮")
    sub = popup.locator("button:has-text('全部提交审核')").first
    try:
        sub.wait_for(state="visible", timeout=120_000)
        logger.info("✅ 已出现全部提交审核按钮")
    except Exception:
        logger.warning("⚠️ 未找到全部提交审核，尝试提交审核")
        sub = popup.locator("button:has-text('提交审核')").first
        sub.wait_for(state="visible", timeout=30_000)

    # 从页面上提取预估生成X条广告
    estimated_ads = 0
    try:
        est_span = popup.locator("span.mr8:has-text('预估生成')").first
        if est_span.count() > 0:
            num_span = est_span.locator("span.opt-link").first
            if num_span.count() > 0:
                estimated_ads = int(num_span.inner_text().strip())
            else:
                est_text = est_span.inner_text()
                m = re.search(r"(\d+)", est_text)
                if m:
                    estimated_ads = int(m.group(1))
        if estimated_ads > 0:
            logger.info(f"📊 预估生成 {estimated_ads} 条广告")
    except Exception as e:
        logger.warning(f"⚠️ 提取预估广告数失败: {e}")

    logger.info("➡️ 最终提交3/5：点击提交审核")
    # ── 等待按钮完全 enabled ─────────────────────────────────────────────
    # el-button 在 disabled/is-disabled 时 force=True 也会被组件层拦截静默丢弃，
    # 必须轮询确认 class 里没有 is-disabled / is-loading 且 disabled 属性为 None。
    _sub_ready = False
    try:
        sub.wait_for(state="visible", timeout=30_000)
        for _w in range(16):   # 最多等 8s（16 × 500ms）
            _cls = sub.get_attribute("class") or ""
            _dis = sub.get_attribute("disabled")
            if "is-disabled" not in _cls and "is-loading" not in _cls and _dis is None:
                _sub_ready = True
                break
            if _w == 0:
                logger.info("⏳ 全部提交审核按钮尚未 enabled，等待中…")
            popup.wait_for_timeout(500)
        else:
            logger.warning("⚠️ 全部提交审核按钮等待 enabled 超时（8s），可能是上一步未完成；等待 2s 后仍尝试点击")
            popup.wait_for_timeout(2_000)
    except Exception as _e:
        logger.warning(f"⚠️ 等待全部提交审核按钮可用失败: {_e}")
    if _sub_ready:
        logger.info("✅ 全部提交审核按钮已 enabled，准备点击")

    # ── 点击后验证确认弹窗出现，否则最多重试 3 次 ───────────────────────
    _dlg_appeared = False
    _dlg_sel_quick = "div.el-dialog__wrapper:visible, div.el-dialog:visible, div[role='dialog']:visible"
    for _click_attempt in range(1, 4):
        safe_click(popup, sub, desc="全部提交审核", logger=logger, W=W)
        wait_idle(popup, mask_timeout=8_000)
        try:
            popup.locator(_dlg_sel_quick).last.wait_for(state="visible", timeout=10_000)
            _dlg_appeared = True
            if _click_attempt > 1:
                logger.info(f"🔁 全部提交审核：第{_click_attempt}次点击后确认弹窗已出现")
            break
        except Exception:
            if _click_attempt < 3:
                logger.warning(f"⚠️ 全部提交审核：第{_click_attempt}次点击后未见确认弹窗，重试")
            else:
                # 最后一次失败时打印按钮当前 DOM 状态，便于排查
                try:
                    _btn_html = sub.evaluate("el => el.outerHTML")
                    logger.warning(f"⚠️ 全部提交审核：3次点击均未见确认弹窗；按钮 DOM: {_btn_html[:300]}")
                except Exception:
                    logger.warning("⚠️ 全部提交审核：3次点击均未见确认弹窗，继续等待后续流程")

    logger.info("➡️ 最终提交4/5：确认提交弹窗")
    dlg_sel = "div.el-dialog__wrapper:visible, div.el-dialog:visible, div[role='dialog']:visible"
    # 90s：部分场景服务器响应较慢，60s 偶发超时；弹窗缺席时后续仍可进行「转为后台提交」
    _CONFIRM_DLG_TIMEOUT = 90_000
    for _dlg_round in range(5):
        final_dlg = popup.locator(dlg_sel).last
        try:
            final_dlg.wait_for(state="visible", timeout=_CONFIRM_DLG_TIMEOUT)
        except Exception as e:
            logger.warning(f"step_submit_and_close 等待确认弹窗超时: {e}")
            break
        ok_btn = final_dlg.locator("button.el-button--primary:visible").filter(has_text="确 定").first
        if ok_btn.count() == 0:
            ok_btn = final_dlg.locator("button.el-button--primary:visible").filter(has_text="确定").first
        if ok_btn.count() == 0:
            ok_btn = final_dlg.locator("button:visible").filter(has_text="确定").first
        if ok_btn.count() == 0:
            break
        safe_click(popup, ok_btn, desc=f"确定按钮(弹窗{_dlg_round+1})", logger=logger, W=W)
        # 等待弹窗隐藏：优先检查"转为后台提交"是否已出现（更可靠的完成信号），
        # 再 fallback 到检查确定按钮是否消失，避免并行模式下 .last 跳到其他 Tab 弹窗
        _dlg_closed = False
        try:
            # 先快速检查：确定按钮是否已消失（说明弹窗已处理）
            ok_btn.wait_for(state="hidden", timeout=3_000)
            _dlg_closed = True
        except Exception:
            # 确定按钮仍可见，再检查"转为后台提交"按钮是否已出现
            try:
                _bg_check = popup.locator("button:has-text('转为后台提交')").first
                _bg_check.wait_for(state="visible", timeout=3_000)
                _dlg_closed = True
            except Exception:
                pass
        if not _dlg_closed:
            # 最后 fallback：短暂等待后继续（不再用 .last 等隐藏，避免并行干扰）
            wait_small(popup, 2000)
        wait_small(popup, 1500)
    wait_small(popup, 1000)

    logger.info("➡️ 最终提交5/5：转为后台提交并关闭页面")
    bg_btn = popup.locator("button:has-text('转为后台提交')").first
    try:
        bg_btn.wait_for(state="visible", timeout=60_000)
    except Exception:
        logger.error('❌ 未确认提交（未出现"转为后台提交"按钮），本剧搭建失败')
        try:
            popup.close()
        except Exception:
            pass
        raise BuildSubmitError('未出现"转为后台提交"按钮，提交结果不确定，视为搭建失败')
    safe_click(popup, bg_btn, desc="转为后台提交", logger=logger, W=W)
    wait_small(popup, W.LOAD)
    popup.close()
    # popup.close() 已同步关闭页面，无需再等 "close" 事件；
    # 旧的 wait_for_event("close") 在页面已关闭时必然超时，产生误导性告警，直接移除。
    wait_idle(page, mask_timeout=3_000, network=True, network_timeout=3_000)
    return estimated_ads


# ═══════════════════════════════════════════════════════════════
#  主运行函数（参数化）
# ═══════════════════════════════════════════════════════════════

def run_build(profile_key: str, log_callback=None, stop_event=None):
    """
    执行搭建流程。
    profile_key: PROFILES 中的 key
    log_callback: 可选，接收 (str) 的回调，用于 GUI 日志显示
    stop_event: threading.Event，外部可设置以中止
    """
    app_cfg = load_config()
    cfg = build_runtime_profile_config(profile_key, app_cfg)
    cdp_endpoint = (app_cfg.get("common") or {}).get("cdp_endpoint") or "http://localhost:9222"
    # 将 common 层的 operator_name 注入到运行时 cfg，供命名步骤使用
    cfg.setdefault("operator_name", (app_cfg.get("common") or {}).get("operator_name") or "lzp")

    W = WaitTimes(cfg["wait_scale"])
    logger = setup_logger(cfg["log_dir"])

    # 包装 logger 使其同时回调 GUI
    if log_callback:
        class _GUIHandler(logging.Handler):
            def emit(self, record):
                try: log_callback(self.format(record))
                except Exception as e:
                    import logging as _logging
                    _logging.getLogger(__name__).warning(f"run_build GUI日志回调失败: {e}")
        gh = _GUIHandler()
        gh.setLevel(logging.INFO)
        gh.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
        logger.addHandler(gh)

    logger.info(f"🚀 开始搭建: {profile_key}")
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
        logger.info("📄 内置配置为空，回退读取 ids.txt")
        groups = read_data(cfg["ids_file"], logger)
    if not groups:
        logger.error("❌ 没有读取到任何数据（请打开「⚙ 设置」录入账号 ID / 链接 / 素材 ID）"); return

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(cdp_endpoint)
            if not browser.contexts:
                raise RuntimeError("已连接浏览器，但没有可用的浏览器上下文")
            context = browser.contexts[0]
            page = select_build_page(context, logger)
            logger.info("✅ 已连接浏览器")

            for g_idx, (ids, dramas) in enumerate(groups, 1):
                check_stop(stop_event)
                logger.info(
                    f"\n╔{'═'*52}╗\n"
                    f"║  📦 第 {g_idx}/{len(groups)} 组  |  账号数: {len(ids)}  |  剧数: {len(dramas)}\n"
                    f"╚{'═'*52}╝"
                )
                g_completed = 0

                group_t0 = time.time()

                for d_idx, drama in enumerate(dramas, 1):
                    check_stop(stop_event)
                    drama_name = drama["name"]
                    drama_t0 = time.time()
                    logger.info(
                        f"\n┌{'─'*50}┐\n"
                        f"│  🎬 [组 {g_idx}/{len(groups)} · 剧 {d_idx}/{len(dramas)}]  {drama_name}\n"
                        f"└{'─'*50}┘"
                    )

                    popup = None
                    try:
                        check_stop(stop_event)
                        if page.is_closed():
                            page = select_build_page(context, logger)
                        # bring_to_front 已移除：CDP 自动化无需页面置前，频繁弹前台会干扰用户
                        logger.info(f"📍 当前操作页面：{_safe_page_title(page) or '无标题'} | {_safe_page_url(page) or '无URL'}")
                        batch_btns = page.locator("button:has-text('批量新建')")
                        batch_count = 0
                        try:
                            batch_count = batch_btns.count()
                        except Exception as e:
                            logger.warning(f"run_build 获取批量新建按钮数量失败: {e}")
                        logger.info(f'🔘 页面匹配到"批量新建"按钮：{batch_count} 个')
                        if batch_count == 0:
                            page = select_build_page(context, logger)
                            batch_btns = page.locator("button:has-text('批量新建')")
                            try:
                                batch_count = batch_btns.count()
                            except Exception as e:
                                logger.warning(f"run_build 重新获取批量新建按钮数量失败: {e}")
                                batch_count = 0
                            logger.info(f'🔁 重新选择页面后匹配到"批量新建"按钮：{batch_count} 个')
                        if batch_count == 0:
                            raise RuntimeError('当前连接的页面没有找到"批量新建"按钮，请把浏览器切到媒体账户-巨量广告-广告管理页后重试')
                        batch_btn = batch_btns.first
                        batch_btn.wait_for(state="visible", timeout=TIMEOUT)
                        batch_btn.scroll_into_view_if_needed()
                        try:
                            expect(batch_btn).to_be_enabled(timeout=5_000)
                        except Exception as e:
                            logger.warning(f"run_build 等待批量新建按钮可用失败: {e}")
                        wait_idle(page, mask_timeout=3_000)
                        logger.info('🖱️ 准备点击"批量新建"')
                        # popup 打开会让 Chrome 抢前台焦点，提前抓住当前前台窗口待会儿还回去
                        _prev_fg_hwnd = capture_foreground()
                        with page.expect_popup() as popup_info:
                            batch_btn.click(force=True)
                        logger.info('✅ 已点击"批量新建"，等待批量新建页面打开')
                        popup = popup_info.value
                        popup.set_default_timeout(15_000)
                        # 立刻把焦点还给用户原本在用的软件
                        restore_foreground(_prev_fg_hwnd)
                        try:
                            popup.wait_for_load_state("networkidle", timeout=60_000)
                            logger.info("✅ 批量新建页面网络已空闲")
                        except PlaywrightTimeout:
                            logger.warning("⚠️ 批量新建页面等待 networkidle 超时，按参考流程继续尝试")

                        check_stop(stop_event)
                        logger.info("➡️ 步骤1/8：选择策略")
                        step_select_strategy(popup, cfg, logger, W)
                        check_stop(stop_event)
                        logger.info("➡️ 步骤2/8：选择媒体账户")
                        step_select_media_accounts(popup, ids, cfg, logger, W)
                        check_stop(stop_event)
                        logger.info("➡️ 步骤3/8：关联产品")
                        step_link_product(popup, drama_name, cfg, logger, W)
                        check_stop(stop_event)
                        logger.info("➡️ 步骤4/8：填写监测链接")
                        step_fill_monitor_links(popup, drama, cfg, logger, W)
                        check_stop(stop_event)
                        logger.info("➡️ 步骤5/8：选择定向包")
                        step_select_audience_package(popup, cfg, logger, W)
                        check_stop(stop_event)
                        logger.info("➡️ 步骤6/8：填写项目名称")
                        step_fill_project_name(popup, drama_name, cfg, logger, W)
                        check_stop(stop_event)
                        logger.info("➡️ 步骤7/8：填写广告名称")
                        step_fill_ad_name(popup, drama_name, cfg, logger, W)
                        check_stop(stop_event)
                        logger.info("➡️ 步骤8/8：选择素材并提交")
                        step_pick_media_materials(popup, drama_name, drama.get("material_ids", []), cfg, logger, W)
                        check_stop(stop_event)
                        ad_count = step_submit_and_close(popup, page, logger, W)
                        completed_dramas.append(drama_name)
                        success_account_ids.update(ids)
                        g_completed += 1
                        drama_elapsed = time.time() - drama_t0
                        if ad_count:
                            logger.info(f"✅ {drama_name} 搭建完成（预估 {ad_count} 条广告），用时 {fmt_duration(drama_elapsed)}")
                        else:
                            logger.info(f"✅ {drama_name} 搭建完成，用时 {fmt_duration(drama_elapsed)}")

                    except AccountsMissingError as e:
                        # 账户缺失 → 归入"跳过组"，用 warning 而非 error，不打 ❌ 失败行
                        skipped_groups.append(f"第{g_idx}组")
                        logger.warning(
                            f"⏭️ [跳过] 第 {g_idx} 组 · 剧『{drama_name}』— 账户缺失/数量不足，跳过本组剩余剧"
                            f"（缺失账户: {e}）"
                        )
                        try:
                            if popup:
                                popup.close()
                        except Exception as e:
                            logger.warning(f"run_build 关闭弹窗失败(AccountsMissingError): {e}")
                        break
                    except StopRequested:
                        logger.info("⏹ 用户中止")
                        try:
                            if popup:
                                popup.close()
                        except Exception as e:
                            logger.warning(f"run_build 关闭弹窗失败(StopRequested): {e}")
                        raise
                    except Exception as e:
                        failed_dramas.append(drama_name)
                        logger.error(f"❌ {drama_name} 搭建失败: {e}")
                        try:
                            if popup:
                                popup.close()
                        except Exception as e:
                            logger.warning(f"run_build 关闭弹窗失败: {e}")
                # 本组 dramas 循环结束，按"成功剧数 × 媒体账号数"累加项目数
                total_projects += len(ids) * g_completed
                group_elapsed = time.time() - group_t0
                logger.info(f"📦 第 {g_idx}/{len(groups)} 组完成，成功 {g_completed}/{len(dramas)} 部剧，用时 {fmt_duration(group_elapsed)}")
    except StopRequested:
        logger.info("⏹ 已停止")
        return

    elapsed = time.time() - t0
    logger.info(f"\n📊 搭建结果：成功 {len(completed_dramas)} 个，失败/异常/未完成 {len(failed_dramas)} 个，账户缺失跳过 {len(skipped_groups)} 组")
    if skipped_groups:
        logger.warning(f"⏭️ 账户缺失/不足跳过的组：{', '.join(skipped_groups)}（已排除在失败统计外）")
    if failed_dramas:
        logger.error("\n❌ 未搭建完成剧名汇总：")
        for name in failed_dramas:
            logger.error(f"  {name}")
    else:
        logger.info("✅ 本次没有未搭建完成的剧")
    logger.info(f"\n🎉 全部完成! 总耗时: {fmt_duration(elapsed)}")

    if completed_dramas:
        record_build_success(len(success_account_ids), total_projects, session_id)
        logger.info(f"📝 基建记录已更新：账户 {len(success_account_ids)} 个，项目 {total_projects} 个")
        logger.info(f"📝 本次账户ID: {', '.join(sorted(success_account_ids))}")
