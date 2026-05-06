"""
backend/core/promo_chain.py
推广链相关函数。
"""
import re
import threading
from datetime import datetime
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

from backend.core.constants import (
    PROMOTION_CHAIN_CDP,
    PROMOTION_CHAIN_TIMEOUT,
    PROMOTION_CHAIN_NAV_TIMEOUT,
    PROMOTION_CHAIN_ELEMENT_TIMEOUT,
    PROMOTION_CHAIN_SEARCH_DELAY,
    PROMOTION_CHAIN_CLICK_DELAY,
    PROMOTION_CHAIN_LIST_URL_PATTERN,
    PROMOTION_CHAIN_DETAIL_URL_PATTERN,
    PROMOTION_CHAIN_LIST_FRAG,
    PROMOTION_CHAIN_DETAIL_FRAG,
    PROMOTION_CHAIN_MENU_SEL,
    PROMOTION_CHAIN_QUERY_SEL,
    PROMOTION_CHAIN_SEARCH_BTN,
    PROMOTION_CHAIN_ROW_SEL,
    PROMOTION_CHAIN_BOOK_NAME_SEL,
    PROMOTION_CHAIN_VIEW_DETAIL_SEL,
    PROMOTION_CHAIN_GET_LINK_BTN,
    PROMOTION_CHAIN_PROMO_INPUT_SEL,
    PROMOTION_CHAIN_IOS_RADIO_SEL,
    PROMOTION_CHAIN_CONFIRM_SEL,
    PROMOTION_CHAIN_CONFIRM_FALLBACK,
    PROMOTION_CHAIN_TASKS,
    _PC_CLEAN_NAME_RE,
    _PC_CHINESE_ONLY_RE,
)
from backend.utils.interruptible import (
    StopRequested,
    sleep_ms,
    wait_for_visible,
    wait_for_hidden,
    check_stop,
)


# ═══════════════════════════════════════════════════════════════
#  推广链工具函数
# ═══════════════════════════════════════════════════════════════

def _pc_clean_name(name: str) -> str:
    """清洗剧名：只保留中文、字母、数字"""
    return _PC_CLEAN_NAME_RE.sub("", name)


def _pc_extract_chinese(text: str) -> str:
    """提取纯汉字"""
    return _PC_CHINESE_ONLY_RE.sub("", text)


def _pc_build_promotion_name(name: str, prefix: str) -> str:
    """构建推广链名称：{今日日期}-{prefix}-{纯净剧名}"""
    pure = _pc_clean_name(name)
    return f"{datetime.now().strftime('%Y-%m-%d')}-{prefix}-{pure}"


def _pc_dismiss_overlay(page, stop_event=None) -> None:
    """点击左上角关闭浮层"""
    page.mouse.click(10, 10)
    sleep_ms(page, PROMOTION_CHAIN_CLICK_DELAY, stop_event)


def _pc_goto_list(page, stop_event=None) -> None:
    """导航到剧单列表页"""
    if PROMOTION_CHAIN_LIST_FRAG in page.url and PROMOTION_CHAIN_DETAIL_FRAG not in page.url:
        return
    _pc_dismiss_overlay(page, stop_event)
    menu = page.locator(PROMOTION_CHAIN_MENU_SEL).first
    if menu.is_visible():
        menu.click()
    try:
        # 用短轮询代替单次长 wait_for_url，让停止可中断
        import time as _time
        _deadline = _time.monotonic() + PROMOTION_CHAIN_NAV_TIMEOUT / 1000.0
        while True:
            check_stop(stop_event)
            _remaining = _deadline - _time.monotonic()
            if _remaining <= 0:
                break
            try:
                page.wait_for_url(PROMOTION_CHAIN_LIST_URL_PATTERN, timeout=min(200, int(_remaining * 1000)))
                break
            except Exception:
                continue
    except StopRequested:
        raise
    except Exception:
        pass


def _pc_safe_goto_list(page, stop_event=None) -> None:
    """安全导航到剧单列表（忽略异常，但保留 StopRequested）"""
    try:
        _pc_goto_list(page, stop_event)
    except StopRequested:
        raise
    except Exception:
        pass


def _pc_search_and_find_row(page, name: str, log, stop_event=None):
    """搜索剧名并按汉字匹配目标行，返回 (row_locator | None, reason_str)"""
    inp = page.locator(PROMOTION_CHAIN_QUERY_SEL)
    inp.click(click_count=3)
    inp.fill(name)
    page.locator(PROMOTION_CHAIN_SEARCH_BTN).click()
    sleep_ms(page, PROMOTION_CHAIN_SEARCH_DELAY, stop_event)

    rows = page.locator(PROMOTION_CHAIN_ROW_SEL)
    try:
        wait_for_visible(rows.first, PROMOTION_CHAIN_NAV_TIMEOUT, stop_event)
    except StopRequested:
        raise
    except Exception:
        return None, "搜索无任何结果"

    count = rows.count()
    target_chinese = _pc_extract_chinese(name)
    candidates = []
    for i in range(count):
        check_stop(stop_event)
        row = rows.nth(i)
        row_name = row.locator(PROMOTION_CHAIN_BOOK_NAME_SEL).inner_text().strip()
        candidates.append(row_name)
        log(f"  第 {i + 1} 行：{row_name}\n")
        if _pc_extract_chinese(row_name) == target_chinese:
            log(f"  匹配第 {i + 1} 行（汉字一致）\n")
            return row, ""

    clist = "\n".join(f"        {j + 1}. {c}" for j, c in enumerate(candidates))
    return None, f"第一页共 {count} 条结果，汉字均不匹配\n      搜索到的结果：\n{clist}"


def _pc_fill_promotion_and_confirm(page, name: str, prefix: str, is_ios: bool, log, stop_event=None):
    """填写推广链名称并确认"""
    btn = page.locator(PROMOTION_CHAIN_GET_LINK_BTN).first
    wait_for_visible(btn, PROMOTION_CHAIN_TIMEOUT, stop_event)
    btn.click()

    promo_input = page.locator(PROMOTION_CHAIN_PROMO_INPUT_SEL).first
    wait_for_visible(promo_input, PROMOTION_CHAIN_ELEMENT_TIMEOUT, stop_event)

    promo_name = _pc_build_promotion_name(name, prefix)
    promo_input.click(click_count=3)
    promo_input.fill("")
    promo_input.fill(promo_name)
    log(f"  推广链名称：{promo_name}\n")

    if is_ios:
        ios_radio = page.locator(PROMOTION_CHAIN_IOS_RADIO_SEL, has_text="IOS").first
        wait_for_visible(ios_radio, PROMOTION_CHAIN_ELEMENT_TIMEOUT, stop_event)
        ios_radio.click()

    confirm = page.locator(PROMOTION_CHAIN_CONFIRM_SEL).first
    try:
        wait_for_visible(confirm, PROMOTION_CHAIN_ELEMENT_TIMEOUT, stop_event)
    except StopRequested:
        raise
    except Exception:
        confirm = page.locator(PROMOTION_CHAIN_CONFIRM_FALLBACK).first
        wait_for_visible(confirm, PROMOTION_CHAIN_ELEMENT_TIMEOUT, stop_event)
    confirm.click()
    wait_for_hidden(confirm, PROMOTION_CHAIN_ELEMENT_TIMEOUT, stop_event)


def _pc_process_drama(page, task_name: str, name: str, prefix: str, is_ios: bool, log, stop_event=None):
    """处理单部剧的推广链生成，返回 (success: bool, reason: str)"""
    log(f"\n[{task_name}] 搜索：{name}\n")
    try:
        _pc_goto_list(page, stop_event)
        matched, reason = _pc_search_and_find_row(page, name, log, stop_event)
        if matched is None:
            _pc_safe_goto_list(page, stop_event)
            return False, reason
        matched.locator(PROMOTION_CHAIN_VIEW_DETAIL_SEL).click()
        # wait_for_url 改为可中断
        import time as _time
        _deadline = _time.monotonic() + PROMOTION_CHAIN_TIMEOUT / 1000.0
        while True:
            check_stop(stop_event)
            _remaining = _deadline - _time.monotonic()
            if _remaining <= 0:
                break
            try:
                page.wait_for_url(PROMOTION_CHAIN_DETAIL_URL_PATTERN, timeout=min(200, int(_remaining * 1000)))
                break
            except Exception:
                continue
        _pc_fill_promotion_and_confirm(page, name, prefix, is_ios, log, stop_event)
        _pc_dismiss_overlay(page, stop_event)
        _pc_goto_list(page, stop_event)
        return True, ""
    except StopRequested:
        raise
    except Exception as e:
        reason = f"程序异常：{type(e).__name__}: {e}"
        log(f"  处理失败：{reason}\n")
        _pc_safe_goto_list(page, stop_event)
        return False, reason


def run_promotion_chain(dramas: list, task_indices: list, log_func, stop_event: threading.Event):
    """
    批量生成推广链主入口。
    dramas: 剧名列表
    task_indices: 要执行的任务下标（对应 PROMOTION_CHAIN_TASKS）
    """
    from playwright.sync_api import sync_playwright as _sync_pw
    _pw_cls = _sync_pw

    tasks = [PROMOTION_CHAIN_TASKS[i] for i in task_indices if 0 <= i < len(PROMOTION_CHAIN_TASKS)]
    if not tasks:
        log_func("未选择有效的执行方向\n")
        return

    log_func("本次输入剧名：\n")
    for d in dramas:
        log_func(f"  {d}\n")
    log_func("\n本次选择执行：\n")
    for tn, _, _ in tasks:
        log_func(f"  {tn}\n")

    failed = []
    try:
        with _pw_cls() as p:
            browser = p.chromium.connect_over_cdp(PROMOTION_CHAIN_CDP)
            ctx = browser.contexts[0]
            pages = ctx.pages
            page = next((pg for pg in pages if PROMOTION_CHAIN_LIST_FRAG in pg.url), pages[0])
            # bring_to_front 已移除：推广链生成无需置前
            page.set_default_timeout(PROMOTION_CHAIN_TIMEOUT)

            for task_name, prefix, is_ios in tasks:
                check_stop(stop_event)
                log_func(f"\n========== 开始执行：{task_name} ==========\n")
                for idx, name in enumerate(dramas, 1):
                    check_stop(stop_event)
                    log_func(f"\n------ {task_name} [{idx}/{len(dramas)}] ------\n")
                    ok, reason = _pc_process_drama(page, task_name, name, prefix, is_ios, log_func, stop_event)
                    if not ok:
                        log_func(f"  失败：{name}，{reason}\n")
                        failed.append((task_name, name, reason))
                log_func(f"\n========== 执行结束：{task_name} ==========\n")
    except StopRequested:
        log_func("\n⏹ 已停止\n")

    if failed:
        log_func("\n失败剧名：\n")
        grouped: dict = {}
        for tn, n, _ in failed:
            grouped.setdefault(tn, []).append(n)
        for tn, _, _ in tasks:
            if tn not in grouped:
                continue
            log_func(f"{tn}\n")
            seen = set()
            for n in grouped[tn]:
                if n in seen:
                    continue
                seen.add(n)
                log_func(f"  {n}\n")
    else:
        log_func("\n选择的推广链已全部执行完成 ✅\n")
