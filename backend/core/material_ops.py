"""
素材对话框操作封装模块

包含素材弹窗的分页控制、素材扫描收集、素材选择提交等操作。

依赖：
  - backend.core.playwright_utils 中的基础操作函数
  - 调用方需传入 is_valid_material_name, extract_mmdd, fmt_duration
"""

import re
import time

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
except Exception:  # playwright 未安装时允许部分导入
    PlaywrightTimeout = Exception  # type: ignore

from backend.core.playwright_utils import (
    TIMEOUT,
    _locator_count,
    safe_click,
    wait_small,
    wait_loading_gone,
    wait_idle,
    click_optional_confirm,
    safe_select_option,
)

# ───────────────────────────────────────────────────────────────
#  常量
# ───────────────────────────────────────────────────────────────
RE_MMDD = re.compile(r'(?<!\d)(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)')


# ═══════════════════════════════════════════════════════════════
#  素材分页工具
# ═══════════════════════════════════════════════════════════════

def _get_material_pager(pane):
    """获取素材弹窗内的分页组件（最后一个），不存在则返回 None。"""
    pagers = pane.locator("div.el-pagination")
    if pagers.count() == 0:
        return None
    return pagers.last


def _get_material_total(pane):
    """获取素材分页总条数，解析"共 N 条"文本；无法获取则返回 None。"""
    total_el = pane.locator("span.el-pagination__total").last
    if total_el.count() == 0:
        return None
    try:
        text = total_el.inner_text().strip()
    except Exception:
        return None
    m = re.search(r"共\s*(\d+)\s*条", text)
    return int(m.group(1)) if m else None


def _get_active_material_page(pane):
    """获取当前激活的页码，无法判断时返回 1。"""
    pager = _get_material_pager(pane)
    if pager is None:
        return 1
    active = pager.locator("li.number.active").first
    if active.count() == 0:
        return 1
    try:
        return int(active.inner_text().strip())
    except Exception:
        return 1


def _has_next_material_page(pane):
    """判断素材列表是否还有下一页。"""
    pager = _get_material_pager(pane)
    if pager is None:
        return False
    next_btn = pager.locator("button.btn-next").first
    if next_btn.count() == 0:
        return False
    disabled = next_btn.get_attribute("disabled")
    cls = next_btn.get_attribute("class") or ""
    return disabled is None and "disabled" not in cls


def _go_to_next_material_page(popup, pane, logger, W):
    """
    点击素材列表的"下一页"按钮，等待页码切换。
    返回 True 表示翻页成功，False 表示失败或已是最后一页。
    """
    pager = _get_material_pager(pane)
    if pager is None:
        return False
    next_btn = pager.locator("button.btn-next").first
    if next_btn.count() == 0:
        return False
    disabled = next_btn.get_attribute("disabled")
    cls = next_btn.get_attribute("class") or ""
    if disabled is not None or "disabled" in cls:
        return False
    old_page = _get_active_material_page(pane)
    try:
        next_btn.scroll_into_view_if_needed()
        popup.wait_for_timeout(W.TINY if W else 200)
        next_btn.click(force=True)
    except Exception as e:
        if logger:
            logger.warning(f"⚠️ 点击素材下一页失败: {e}")
        return False
    popup.wait_for_timeout(W.LOAD if W else 1500)
    material_wrapper = pane.locator("div.material-wrapper").first
    if material_wrapper.count() > 0:
        wait_loading_gone(popup, material_wrapper, timeout=10_000)
    for _ in range(10):
        new_page = _get_active_material_page(pane)
        if new_page != old_page:
            return True
        popup.wait_for_timeout(500)
    return False


def _go_to_material_page(popup, pane, page_no, logger, W):
    """
    跳转到素材列表的指定页码。
    支持直接点击页码按钮或逐步翻页。
    返回 True 表示成功到达目标页。
    """
    pager = _get_material_pager(pane)
    if pager is None:
        return _get_active_material_page(pane) == page_no
    for _ in range(20):
        current_page = _get_active_material_page(pane)
        if current_page == page_no:
            return True
        visible_target = pager.locator("li.number").filter(has_text=str(page_no)).first
        if visible_target.count() > 0:
            safe_click(popup, visible_target, desc=f"素材页码{page_no}", logger=logger, W=W)
            wait_small(popup, W.LOAD)
            wait_loading_gone(popup, pane)
            continue
        if current_page < page_no and _has_next_material_page(pane):
            _go_to_next_material_page(popup, pane, logger, W)
            continue
        prev_btn = pager.locator("button.btn-prev").first
        if current_page > page_no and prev_btn.count() > 0:
            disabled = prev_btn.get_attribute("disabled")
            cls = prev_btn.get_attribute("class") or ""
            if disabled is None and "disabled" not in cls:
                safe_click(popup, prev_btn, desc="素材上一页", logger=logger, W=W)
                wait_small(popup, W.LOAD)
                wait_loading_gone(popup, pane)
                continue
        break
    return _get_active_material_page(pane) == page_no


# ═══════════════════════════════════════════════════════════════
#  素材卡片查找
# ═══════════════════════════════════════════════════════════════

def _find_material_card_on_current_page(popup, material_dlg, pane, material_name, W):
    """
    在当前页的素材列表中通过滚动查找指定名称的素材卡片。
    返回对应 material-item 的 locator，未找到则返回 None。
    """
    material_wrapper = pane.locator("div.material-wrapper").first
    seen_rounds = 0
    try:
        material_wrapper.evaluate("el => el.scrollTop = 0")
    except Exception:
        pass
    wait_small(popup, W.SHORT)
    for _ in range(80):
        names = material_wrapper.locator("div.material-name")
        count = names.count()
        for i in range(count):
            name_el = names.nth(i)
            try:
                current_name = name_el.inner_text().strip()
            except Exception:
                continue
            if current_name == material_name:
                return name_el.locator("xpath=ancestor::div[contains(@class,'material-item')]").first
        try:
            before = material_wrapper.evaluate("el => el.scrollTop")
            material_wrapper.evaluate("""el => {
                el.scrollTop = Math.min(el.scrollTop + el.clientHeight, el.scrollHeight);
            }""")
            after = material_wrapper.evaluate("el => el.scrollTop")
            if after == before:
                seen_rounds += 1
            else:
                seen_rounds = 0
        except Exception:
            seen_rounds += 1
        if seen_rounds >= 3:
            break
        wait_small(popup, W.MEDIUM)
    return None


# ═══════════════════════════════════════════════════════════════
#  素材对话框打开与过滤配置
# ═══════════════════════════════════════════════════════════════

def _open_material_dialog(popup, drama_name, cfg, logger, W, use_keyword):
    """
    打开素材选择弹窗并切换到账号素材 Tab，填入账号 ID 后搜索。
    use_keyword=True 时同时填入剧名关键词。
    返回 (material_dlg, pane) 两个 locator。
    """
    clear_btn = popup.locator("div.table-header:has(span:has-text('创意素材')) button:has-text('清空')").first
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
    if use_keyword:
        search_input = pane.locator("input[placeholder*='关键词查询']").first
        search_input.fill(drama_name)
        wait_small(popup, 600)
        logger.info(f"🔎 素材关键词已填入: {drama_name}")
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
    return material_dlg, pane


def _configure_material_filters(popup, pane, material_dlg, logger, W):
    """
    配置素材过滤条件：将类型切换为"视频"，将分页大小切换为 100 条/页。
    过滤配置失败时记录警告并继续（不中断流程）。
    """
    material_wrapper = pane.locator("div.material-wrapper").first
    try:
        type_area = pane.locator("div.select-area:has(label:has-text('类型'))").first
        if type_area.count() > 0:
            type_input = type_area.locator("div.el-select input.el-input__inner").first
            if type_input.count() > 0:
                if safe_select_option(popup, type_input, "视频", desc="素材类型", logger=logger, W=W):
                    logger.info("🎥 已将素材类型切换为【视频】")
                    wait_loading_gone(popup, material_wrapper, timeout=15_000)
                    wait_small(popup, W.LONG)
        else:
            logger.warning('⚠️ 未找到"类型："选择区域，无法强制切为视频')
    except Exception as e:
        logger.warning(f"⚠️ 切换素材类型为视频时出错(忽略继续): {e}")
    try:
        size_input = pane.locator("span.el-pagination__sizes input.el-input__inner").first
        if size_input.count() > 0:
            size_input.click(force=True)
            wait_small(popup, W.NORMAL)
            option_100 = popup.locator("ul.el-select-dropdown__list:visible li.el-select-dropdown__item").filter(has_text="100").last
            if option_100.count() > 0:
                option_100.click(force=True)
                wait_loading_gone(popup, material_wrapper, timeout=30_000)
                wait_small(popup, W.LONG)
                logger.info("📄 已切换分页为100条/页")
            else:
                logger.warning("⚠️ 未找到100条/页选项")
    except Exception as e:
        logger.warning(f"⚠️ 分页切换失败(忽略继续): {e}")


# ═══════════════════════════════════════════════════════════════
#  素材候选收集与提交
# ═══════════════════════════════════════════════════════════════

def _collect_material_candidates(popup, material_dlg, pane, drama_name, logger, W,
                                  is_valid_material_name, extract_mmdd, fmt_duration, TODAY_STR):
    """
    扫描所有页面的素材，收集符合条件的候选素材列表。

    参数：
        is_valid_material_name  — 素材名校验函数
        extract_mmdd            — 从素材名提取 MMDD 日期
        fmt_duration            — 时长格式化
        TODAY_STR               — 当前日期字符串 "%m%d"

    返回：候选素材列表，每项为 {"name": str, "page": int, "date": str|None}
    """
    material_wrapper = pane.locator("div.material-wrapper").first
    material_wrapper.wait_for(state="visible", timeout=TIMEOUT)
    wait_loading_gone(popup, material_wrapper, timeout=30_000)
    load_start = time.time()
    load_deadline = load_start + 60
    stable_count = -1
    stable_since = 0.0
    STABLE_THRESHOLD = 3.0
    name_confirmed = False
    while time.time() < load_deadline:
        loading_mask = material_wrapper.locator(".el-loading-mask").first
        if loading_mask.count() > 0:
            try:
                style = loading_mask.get_attribute("style") or ""
            except Exception:
                style = ""
            if "display: none" not in style:
                stable_count = -1
                name_confirmed = False
                wait_small(popup, W.LONG)
                continue
        current = material_dlg.locator("div.material-name").count()
        if current > 0:
            if not name_confirmed:
                try:
                    first_name = material_dlg.locator("div.material-name").first.inner_text().strip()
                except Exception:
                    first_name = ""
                if first_name and drama_name in first_name:
                    name_confirmed = True
                    logger.info(f"🔎 首条素材名匹配剧名，确认搜索结果已加载: {first_name}")
            if name_confirmed:
                if current != stable_count:
                    stable_count = current
                    stable_since = time.time()
                    wait_small(popup, W.LONG)
                    continue
                if time.time() - stable_since >= STABLE_THRESHOLD:
                    logger.info(f"✅ 素材列表已加载: {drama_name} | {current} 个素材名 (耗时 {fmt_duration(time.time() - load_start)})")
                    break
            else:
                stable_count = -1
                wait_small(popup, W.LONG)
                continue
        wait_small(popup, W.EXTRA)
    else:
        if stable_count > 0:
            logger.info(f"⏳ 素材列表加载超时但已有 {stable_count} 个素材名，继续扫描: {drama_name}")
        elif name_confirmed:
            logger.info(f"⏳ 素材数量未完全稳定但已确认搜索结果，继续扫描: {drama_name}")
        else:
            logger.error(f"❌ 素材加载超时(60s): {drama_name}")
            return []
    wait_loading_gone(popup, material_wrapper)
    processed_names = set()
    available_candidates = []
    skipped_by_name = skipped_by_tag = skipped_by_future = 0
    scanned_pages = set()
    bad_keywords = ("低质", "巨量广告建议", "拒审")
    total_count = _get_material_total(pane)
    total_poll_rounds = 0
    logger.info(f"📄 素材分页总数: {total_count if total_count is not None else '未知'} 条 | 当前页: {_get_active_material_page(pane)}")
    consecutive_no_progress = 0
    while True:
        current_page = _get_active_material_page(pane)
        scanned_pages.add(current_page)
        no_new_rounds = 0
        page_start_count = len(processed_names)
        try:
            material_wrapper.evaluate("el => el.scrollTop = 0")
        except Exception:
            pass
        wait_small(popup, W.SHORT)
        for scroll_round in range(90):
            names = material_wrapper.locator("div.material-name")
            count = names.count()
            found_new_this_round = 0
            for i in range(count):
                name_el = names.nth(i)
                try:
                    material_name = name_el.inner_text().strip()
                except Exception:
                    continue
                if not material_name or material_name in processed_names:
                    continue
                processed_names.add(material_name)
                found_new_this_round += 1
                if not is_valid_material_name(drama_name, material_name):
                    skipped_by_name += 1
                    continue
                card = name_el.locator("xpath=ancestor::div[contains(@class,'material-item')]").first
                try:
                    tag_text = card.locator("div.tag-wrapper").inner_text().strip()
                except Exception:
                    tag_text = ""
                if any(keyword in tag_text for keyword in bad_keywords):
                    skipped_by_tag += 1
                    logger.info(f"⏭️ 跳过素材: {material_name} | 标签: {tag_text}")
                    continue
                mmdd = extract_mmdd(material_name)
                if mmdd and int(mmdd) > int(TODAY_STR):
                    skipped_by_future += 1
                    continue
                available_candidates.append({"name": material_name, "page": current_page, "date": mmdd})
            if found_new_this_round > 0:
                no_new_rounds = 0
            else:
                no_new_rounds += 1
            if no_new_rounds >= 6:
                break
            try:
                has_more_before_scroll = material_wrapper.evaluate("el => el.scrollTop + el.clientHeight < el.scrollHeight - 2")
                if total_count is not None and len(processed_names) < total_count and not has_more_before_scroll:
                    total_poll_rounds += 1
                    if total_poll_rounds <= 30:
                        wait_small(popup, W.LONG)
                        material_wrapper.evaluate("el => el.scrollTop = 0")
                        wait_small(popup, W.SHORT)
                        continue
                    else:
                        break
                material_wrapper.evaluate("""el => {
                    el.scrollTop = Math.min(el.scrollTop + el.clientHeight, el.scrollHeight);
                }""")
                if not has_more_before_scroll:
                    material_wrapper.evaluate("el => el.scrollTop = el.scrollHeight")
            except Exception as e:
                logger.warning(f"⚠️ 素材列表滚动失败(忽略继续): {e}")
            wait_small(popup, W.LOAD if no_new_rounds > 0 else W.LONGER)
        page_new_count = len(processed_names) - page_start_count
        logger.info(f"📄 第{current_page}页扫描完成，本页新增 {page_new_count} 个素材名，累计 {len(processed_names)}/{total_count if total_count is not None else '未知'}")
        if page_new_count == 0:
            consecutive_no_progress += 1
        else:
            consecutive_no_progress = 0
        if consecutive_no_progress >= 2:
            logger.info(f"📄 连续 {consecutive_no_progress} 页无新素材，停止翻页")
            break
        if total_count is not None and len(processed_names) >= total_count:
            logger.info(f"✅ 已扫描素材数 {len(processed_names)}/{total_count}，达到分页总数")
            break
        if not _has_next_material_page(pane):
            logger.info(f"📄 已到素材最后一页，扫描素材数 {len(processed_names)}/{total_count if total_count is not None else '未知'}")
            break
        logger.info(f"➡️ 当前已扫描素材 {len(processed_names)}/{total_count if total_count is not None else '未知'}，继续翻到下一页")
        total_poll_rounds = 0
        old_page = _get_active_material_page(pane)
        if not _go_to_next_material_page(popup, pane, logger, W):
            logger.warning("⚠️ 素材下一页切换失败，停止继续翻页")
            break
        new_page = _get_active_material_page(pane)
        if new_page == old_page:
            logger.warning("⚠️ 翻页后页码未变化，停止继续翻页")
            break
        logger.info(f"📄 已翻到第{new_page}页，等待内容加载...")
        wait_small(popup, W.NORMAL)
        wait_loading_gone(popup, material_wrapper, timeout=10_000)
        logger.info(f"📄 第{new_page}页加载完成，开始扫描")
    logger.info(
        f"🔎 候选素材收集完成: {drama_name} | 共 {len(available_candidates)} 个可用 | "
        f"扫描素材名 {len(processed_names)} 个/{total_count if total_count is not None else '未知'} | "
        f"扫描页数 {len(scanned_pages)} | "
        f"跳过: 剧名不符 {skipped_by_name}, 质量标签 {skipped_by_tag}, 未来日期 {skipped_by_future}"
    )
    return available_candidates


def _select_and_submit_materials(popup, material_dlg, pane, available_candidates, drama_name, logger, W,
                                  fmt_duration):
    """
    从候选素材中按日期分组选择，依次点击素材卡片，最后提交。

    参数：
        fmt_duration  — 时长格式化函数

    返回：成功选中并提交的素材数量（int）。
    """
    def _cancel_dialog():
        """尝试点击取消按钮关闭素材弹窗（保证资源释放）。"""
        try:
            cancel_btn = material_dlg.locator("button:visible").filter(has_text="取消").last
            if cancel_btn.count() > 0:
                cancel_btn.click(force=True)
                wait_small(popup, W.NORMAL)
        except Exception:
            pass

    def _cancel_and_return():
        _cancel_dialog()

    dated_candidates = [x for x in available_candidates if x["date"]]
    undated_candidates = [x for x in available_candidates if not x["date"]]
    selected_candidates = []
    if dated_candidates:
        date_groups = {}
        for item in dated_candidates:
            date_groups.setdefault(item["date"], []).append(item)
        valid_dates = sorted(date_groups.keys(), reverse=True)
        logger.info(f"📅 今天日期: {_get_today_str()} | 可用历史日期(近到远): {', '.join(valid_dates)}")
        for d in valid_dates:
            group = date_groups[d]
            selected_candidates.extend(group)
            logger.info(f"📅 日期 {d} 可用 {len(group)} 个，当前累计 {len(selected_candidates)} 个")
    if undated_candidates:
        selected_candidates.extend(undated_candidates)
        logger.info(f"📅 无日期素材 {len(undated_candidates)} 个，当前累计 {len(selected_candidates)} 个")
    if not selected_candidates:
        logger.warning(f"⚠️ 没有可提交素材: {drama_name}")
        _cancel_and_return()
        return 0
    logger.info(f"✅ 可用素材: 带日期 {len(dated_candidates)} 个 + 无日期 {len(undated_candidates)} 个 = 共 {len(selected_candidates)} 个")
    selected_candidates.sort(key=lambda x: (x.get("page", 1), x.get("date", ""), x.get("name", "")))
    picked_count = 0
    pick_start = time.time()
    try:
        current_pick_page = _get_active_material_page(pane)
        if current_pick_page != 1:
            if _go_to_material_page(popup, pane, 1, logger, W):
                current_pick_page = 1
        for item in selected_candidates:
            material_name = item["name"]
            target_page = item.get("page", 1)
            try:
                if current_pick_page != target_page:
                    if not _go_to_material_page(popup, pane, target_page, logger, W):
                        logger.warning(f"⚠️ 跳转素材第{target_page}页失败: {material_name}")
                        continue
                    current_pick_page = target_page
                card = _find_material_card_on_current_page(popup, material_dlg, pane, material_name, W)
                if card is None or card.count() == 0:
                    logger.warning(f"⚠️ 当前页未重新定位到素材: {material_name}")
                    continue
                safe_click(popup, card, desc=f"素材卡片:{material_name[:15]}", logger=logger, W=W)
                wait_small(popup, W.SHORT)
                picked_count += 1
                logger.info(f"✅ 已选择素材 ({picked_count}/{len(selected_candidates)}): {material_name}")
            except Exception as e:
                logger.warning(f"⚠️ 选择素材失败: {material_name} | {e}")
        logger.info(f"🎞️ 素材选择完成: 成功 {picked_count}/{len(selected_candidates)} 个，耗时 {fmt_duration(time.time() - pick_start)}")
        if picked_count == 0:
            logger.warning(f"⚠️ 没有成功选中任何素材: {drama_name}")
            _cancel_and_return()
            return 0
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
        return picked_count
    except Exception:
        logger.warning(f"⚠️ 素材选择/提交过程中发生异常，尝试关闭弹窗: {drama_name}")
        _cancel_dialog()
        raise


def _get_today_str():
    """获取当前日期字符串（%m%d 格式）。"""
    from datetime import datetime
    return datetime.now().strftime("%m%d")
