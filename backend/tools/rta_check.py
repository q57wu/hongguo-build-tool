"""
RTA 检测工具 — 批量检测 RTA 是否处于【启用中】状态
函数签名：do_rta_check(drama_type, aadvids, log_func)
drama_type: "1" / "2" / "3" → 常规剧 / 定制剧 / 激励
aadvids: List[str]
log_func: Callable[[str], None]
"""

from typing import Callable, List

from playwright.sync_api import sync_playwright

from backend.tools._rta_common import (
    RTA_ID_MAP,
    CDP_URL,
    FAST_TIMEOUT,
    STATUS_ENABLED_TEXT,
    wait,
    visible,
    close_known_popups,
    pick_page,
    ensure_rta_page,
    search_target_rta,
    _JS_CHECK_RTA_SWITCH,
    _JS_CHECK_RTA_IN_TABLE,
)


def _check_rta_enabled(page, rta_id: str, log_func: Callable) -> bool:
    """
    检测指定 rta_id 是否为 '启用中' 状态。
    优先用 JS 直接扫描 DOM（免搜索），失败时回退到搜索方式。
    """
    # 快速路径：JS 直接扫描表格
    try:
        result = page.evaluate(_JS_CHECK_RTA_IN_TABLE, rta_id)
        if result == "enabled":
            log_func(f"RTA ID {rta_id} 状态为【启用中】（JS快速检测）")
            return True
        elif result == "disabled":
            log_func(f"RTA ID {rta_id} 未处于【启用中】状态（JS快速检测）")
            return False
        # result == 'not_found' → 回退到搜索
    except Exception:
        pass

    # 回退路径：搜索
    log_func(f"JS未找到 RTA ID {rta_id}，回退到搜索方式")
    row = search_target_rta(page, rta_id, log_func)
    close_known_popups(page, log_func, max_rounds=1)

    # 优先用 JS 检查开关 class
    try:
        result = page.evaluate(_JS_CHECK_RTA_SWITCH, rta_id)
        if result == "enabled":
            log_func(f"RTA ID {rta_id} 状态为【启用中】✓")
            return True
        elif result == "disabled":
            log_func(f"RTA ID {rta_id} 状态为【未启用】✗")
            return False
    except Exception:
        pass

    # 最终兜底：文本解析
    row_text = row.inner_text(timeout=FAST_TIMEOUT).replace(" ", " ").strip()
    normalized = " ".join(row_text.split())

    if rta_id not in normalized:
        raise RuntimeError(f"RTA 行文本中未包含 RTA ID {rta_id}，实际为：{normalized}")

    if STATUS_ENABLED_TEXT in normalized:
        log_func(f"RTA ID {rta_id} 状态为【启用中】")
        return True

    log_func(f"RTA ID {rta_id} 未处于【启用中】状态，当前行文本：{normalized}")
    return False


def _process_one(page, aadvid: str, rta_id: str, log_func: Callable) -> bool:
    """单个 aadvid 检测流程，返回 True=启用中 / False=未启用"""
    log_func(f"\n>>> 开始检测 aadvid: {aadvid}")
    ensure_rta_page(page, aadvid, log_func)
    close_known_popups(page, log_func)

    enabled = _check_rta_enabled(page, rta_id, log_func)
    status = "启用成功" if enabled else "未启用"
    log_func(f"aadvid: {aadvid} 检测完成，RTA {rta_id} {status}")
    return enabled


def do_rta_check(drama_type: str, aadvids: List[str], log_func: Callable) -> None:
    """
    批量检测 RTA 是否处于【启用中】状态。

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

    total = len(aadvids)
    log_func(f"检测到 {total} 个 aadvid，准备串行执行。")
    log_func(f"剧型：{drama_name} | RTA ID：{rta_id}")

    not_enabled_ids: List[str] = []

    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.connect_over_cdp(CDP_URL)
            except Exception as exc:
                log_func(f"❌ 无法连接到 {CDP_URL}，请先用 9222 启动 Chrome。错误：{exc}")
                return

            page = pick_page(browser, log_func)

            for index, aadvid in enumerate(aadvids, start=1):
                log_func(f"\n=== 当前进度：{index}/{total}（aadvid: {aadvid}）===")
                try:
                    if not _process_one(page, aadvid, rta_id, log_func):
                        not_enabled_ids.append(aadvid)
                except Exception as exc:
                    log_func(f"❌ aadvid: {aadvid} 执行中发生异常，视为未检测到启用：{exc}")
                    not_enabled_ids.append(aadvid)

        log_func("\n全部 aadvid 执行结束。\n")
        log_func(
            f"=== 未检测到 RTA {rta_id}（{drama_name}）处于【启用中】的 aadvid"
            f"（包含未启用、异常、超时等）==="
        )
        if not_enabled_ids:
            log_func("\n".join(not_enabled_ids))
        else:
            sep = "=" * 50
            log_func(f"\n{sep}")
            log_func("✅ 检测完成")
            log_func(f"✅ 共 {total} 个 aadvid")
            log_func(f"✅ 全部已设置 RTA {rta_id}（{drama_name}）")
            log_func("✅ 无需额外操作")
            log_func(f"{sep}")

    except Exception as exc:
        import traceback
        log_func(f"❌ 执行异常：{exc}")
        log_func(traceback.format_exc())
