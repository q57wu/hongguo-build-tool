"""
RTA 设置工具 — 批量设置 RTA 生效范围
函数签名：do_rta_set(drama_type, aadvids, log_func)
drama_type: "1" / "2" / "3" → 常规剧 / 定制剧 / 激励
aadvids: List[str]
log_func: Callable[[str], None]
"""

from typing import Callable, List

from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from backend.tools._rta_common import (
    RTA_ID_MAP,
    CDP_URL,
    WAIT_TINY,
    WAIT_SHORT,
    WAIT_MEDIUM,
    FAST_TIMEOUT,
    SET_RANGE_TEXT,
    ACCOUNT_TEXT,
    CONFIRM_TEXT,
    SUCCESS_RE,
    wait,
    visible,
    click_if_visible,
    close_known_popups,
    pick_page,
    ensure_rta_page,
    search_target_rta,
)


def _click_set_range(page, aadvid: str, rta_id: str, log_func: Callable) -> None:
    """定位目标行并点击【设置生效范围】。"""
    close_known_popups(page, log_func)
    row = search_target_rta(page, rta_id, log_func)
    close_known_popups(page, log_func)

    button = row.get_by_text(SET_RANGE_TEXT, exact=True).first
    try:
        button.click(force=True, timeout=FAST_TIMEOUT)
        log_func("已点击【设置生效范围】")
        return
    except Exception:
        log_func("点击【设置生效范围】被拦截，准备重试")

    close_known_popups(page, log_func)
    wait(page, WAIT_TINY)

    row = search_target_rta(page, rta_id, log_func)
    row.get_by_text(SET_RANGE_TEXT, exact=True).first.click(
        force=True, timeout=FAST_TIMEOUT
    )
    log_func("重试点击【设置生效范围】成功")


def _choose_account_and_confirm(page, log_func: Callable) -> None:
    """选择投放账户并确认。"""
    account_button = page.get_by_role("button", name=ACCOUNT_TEXT, exact=True)
    account_button.first.wait_for(state="visible", timeout=10000)
    account_button.first.click(force=True, timeout=FAST_TIMEOUT)
    log_func("已点击【投放账户】")

    confirm_button = page.get_by_role("button", name=CONFIRM_TEXT, exact=True).last
    confirm_button.wait_for(state="visible", timeout=10000)
    confirm_button.click(force=True, timeout=FAST_TIMEOUT)
    log_func("已点击【确定】")

    try:
        page.get_by_text(SUCCESS_RE).first.wait_for(state="visible", timeout=8000)
        log_func("设置生效范围成功")
    except PlaywrightTimeoutError:
        log_func("未捕捉到成功提示，但已执行点击")


def _process_one(page, aadvid: str, rta_id: str, log_func: Callable) -> None:
    log_func(f"\n>>> 开始处理 aadvid: {aadvid}")
    ensure_rta_page(page, aadvid, log_func)
    _click_set_range(page, aadvid, rta_id, log_func)
    close_known_popups(page, log_func)
    _choose_account_and_confirm(page, log_func)
    log_func(f"aadvid: {aadvid} 处理完成")


def do_rta_set(drama_type: str, aadvids: List[str], log_func: Callable) -> None:
    """
    批量设置 RTA 生效范围。

    :param drama_type: "1"=常规剧  "2"=定制剧  "3"=激励
    :param aadvids: aadvid 列表
    :param log_func: 日志回调函数，接受一个字符串参数
    """
    if drama_type not in RTA_ID_MAP:
        log_func(f"❌ 无效剧型参数：{drama_type}（应为 1/2/3）")
        return

    rta_id, drama_name = RTA_ID_MAP[drama_type]

    if not aadvids:
        log_func("⚠️ 未传入有效 aadvid，已退出")
        return

    log_func(f"\n剧型：{drama_name} | RTA ID：{rta_id}")
    log_func(f"检测到 {len(aadvids)} 个 aadvid，准备串行执行。")

    failed_ids: List[str] = []

    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.connect_over_cdp(CDP_URL)
            except Exception as exc:
                log_func(f"❌ 无法连接到 {CDP_URL}，请先用 9222 启动 Chrome。错误：{exc}")
                return

            page = pick_page(browser, log_func)

            for aadvid in aadvids:
                try:
                    _process_one(page, aadvid, rta_id, log_func)
                except Exception as exc:
                    log_func(f"❌ aadvid: {aadvid} 执行失败：{exc}")
                    failed_ids.append(aadvid)

            log_func("\n全部 aadvid 执行结束。")

            if failed_ids:
                log_func(f"\n=== 以下 {drama_name} aadvid 执行失败（RTA {rta_id}）===")
                for fid in failed_ids:
                    log_func(fid)
            else:
                log_func(f"\n=== ✅ {drama_name} RTA {rta_id} 所有 aadvid 均设置成功 ===")
    except Exception as exc:
        import traceback
        log_func(f"❌ 执行异常：{exc}")
        log_func(traceback.format_exc())
