"""
backend/core/incentive_tools.py
激励工具函数：推广链生成 & 素材推送。
"""
import threading
from datetime import datetime

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

from backend.core.constants import (
    INCENTIVE_PROMO_DRAWER_SEL,
    INCENTIVE_PROMO_NAME_INPUT,
    INCENTIVE_PROMO_CONFIRM_BTN,
    INCENTIVE_PROMO_TIMEOUT,
    INCENTIVE_PROMO_DRAWER_TIMEOUT,
    INCENTIVE_PUSH_TIMEOUT,
    INCENTIVE_PUSH_WAIT_AFTER,
    INCENTIVE_PUSH_BETWEEN,
    INCENTIVE_PUSH_DIALOG_SEL,
    INCENTIVE_PUSH_OPTION_SEL,
    INCENTIVE_PUSH_NEXT_BTN,
)
from backend.utils.interruptible import (
    StopRequested,
    sleep_ms,
    wait_for_visible,
    wait_for_hidden,
    check_stop,
)


# ═══════════════════════════════════════════════════════════════
#  激励推广链生成（sync）
# ═══════════════════════════════════════════════════════════════

def _incentive_promo_run_once(page, index: int, date_str: str, suffix: str, log_func, stop_event) -> bool:
    """执行一次激励推广链创建，返回是否成功"""
    promotion_name = f"{date_str}-组{index}-{suffix}"
    log_func(f"\n[{index}] 开始创建推广链：{promotion_name}\n")
    try:
        activity_item = page.locator(
            "h3:has-text('短剧激励活动')"
        ).locator("xpath=ancestor::div[contains(@class, 'AmDBjA8pHU8hRXib')]")
        wait_for_visible(activity_item, INCENTIVE_PROMO_TIMEOUT, stop_event)

        get_link_btn = activity_item.locator("text=获取推广链接")
        wait_for_visible(get_link_btn, INCENTIVE_PROMO_TIMEOUT, stop_event)
        get_link_btn.click()
        log_func(f"[{index}] 已点击「获取推广链接」\n")

        drawer = page.locator(INCENTIVE_PROMO_DRAWER_SEL)
        wait_for_visible(drawer, INCENTIVE_PROMO_DRAWER_TIMEOUT, stop_event)

        name_input = page.locator(INCENTIVE_PROMO_NAME_INPUT)
        wait_for_visible(name_input, INCENTIVE_PROMO_TIMEOUT, stop_event)
        name_input.click(click_count=3)
        name_input.fill("")
        name_input.fill(promotion_name)
        log_func(f"[{index}] 名称已填入：{promotion_name}\n")

        confirm_btn = page.locator(INCENTIVE_PROMO_CONFIRM_BTN)
        wait_for_visible(confirm_btn, INCENTIVE_PROMO_TIMEOUT, stop_event)
        confirm_btn.click()

        wait_for_hidden(drawer, INCENTIVE_PROMO_DRAWER_TIMEOUT, stop_event)
        log_func(f"[{index}] ✅ 成功：{promotion_name}\n")

        sleep_ms(page, 500, stop_event)
        page.mouse.click(10, 10)
        sleep_ms(page, 500, stop_event)
        return True
    except StopRequested:
        raise
    except Exception as e:
        log_func(f"[{index}] ❌ 失败：{e}\n")
        try:
            close_icon = page.locator(".arco-drawer:visible .arco-drawer-close-icon")
            if close_icon.count() > 0:
                close_icon.click()
                sleep_ms(page, 500, stop_event)
        except StopRequested:
            raise
        except Exception:
            pass
        return False


def run_incentive_promo_chain(count: int, suffix: str, log_func, stop_event: threading.Event):
    """
    批量创建激励推广链。
    count: 要创建的条数
    suffix: 推广链名称后缀（如 "激励每留"）
    """
    from playwright.sync_api import sync_playwright as _sync_pw
    cdp_url = "http://127.0.0.1:9222"
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_func(f"日期：{date_str}，计划执行 {count} 次，后缀：{suffix}\n")
    log_func("=" * 50 + "\n")

    success_count = 0
    fail_count = 0
    failed_names = []

    try:
        with _sync_pw() as p:
            browser = p.chromium.connect_over_cdp(cdp_url)
            ctx = browser.contexts[0]
            page = None
            for pg in ctx.pages:
                if "changdupingtai" in pg.url or "hongguo" in pg.url or "promote" in pg.url or "buyin" in pg.url:
                    page = pg
                    break
            if not page:
                page = ctx.pages[0]
            # bring_to_front 已移除：推广链生成无需置前
            page.set_default_timeout(INCENTIVE_PROMO_TIMEOUT)

            for i in range(1, count + 1):
                check_stop(stop_event)
                if _incentive_promo_run_once(page, i, date_str, suffix, log_func, stop_event):
                    success_count += 1
                else:
                    fail_count += 1
                    failed_names.append(f"{date_str}-组{i}-{suffix}")
    except StopRequested:
        log_func("\n⏹ 已停止\n")

    log_func(f"\n{'='*40}\n")
    log_func(f"🎉 完成！成功：{success_count}，失败：{fail_count}\n")
    if failed_names:
        log_func("失败列表：\n")
        for name in failed_names:
            log_func(f"  {name}\n")


# ═══════════════════════════════════════════════════════════════
#  激励素材推送（sync）
# ═══════════════════════════════════════════════════════════════

def _incentive_push_read_pages(page) -> int:
    """读取当前页面的分页总数"""
    items = page.locator(
        ".arco-pagination-item"
        ":not(.arco-pagination-item-prev)"
        ":not(.arco-pagination-item-next)"
        ":not(.arco-pagination-item-jumper)"
    )
    count = items.count()
    if count == 0:
        return 1
    for idx in range(count - 1, -1, -1):
        text = items.nth(idx).inner_text().strip()
        if text.isdigit():
            return int(text)
    return 1


def run_incentive_push(account_id: str, log_func, stop_event: threading.Event):
    """
    激励素材批量推送。
    account_id: 要推送到的广告账户ID
    """
    from playwright.sync_api import sync_playwright as _sync_pw
    cdp_url = "http://127.0.0.1:9222"

    success_count = 0
    fail_count = 0

    try:
        with _sync_pw() as p:
            browser = p.chromium.connect_over_cdp(cdp_url)
            ctx = browser.contexts[0]
            page = next((pg for pg in ctx.pages if "material" in pg.url), ctx.pages[0])
            # bring_to_front 已移除：素材推送无需置前
            page.set_default_timeout(INCENTIVE_PUSH_TIMEOUT)

            total_pages = _incentive_push_read_pages(page)
            log_func(f"📄 共 {total_pages} 页\n")
            log_func(f"🚀 将从第 1 页逐页推送到第 {total_pages} 页\n\n")

            for i in range(total_pages):
                check_stop(stop_event)
                page_num = i + 1
                log_func(f"\n🔄 正在推送第 {page_num}/{total_pages} 页...\n")
                try:
                    checkbox = page.locator("table thead .arco-checkbox-mask")
                    wait_for_visible(checkbox, INCENTIVE_PUSH_TIMEOUT, stop_event)
                    checkbox.click()

                    batch_btn = page.get_by_role("button", name="批量操作")
                    wait_for_visible(batch_btn, INCENTIVE_PUSH_TIMEOUT, stop_event)
                    batch_btn.click()

                    push_btn = page.get_by_text("批量推送", exact=True)
                    wait_for_visible(push_btn, INCENTIVE_PUSH_TIMEOUT, stop_event)
                    push_btn.click()

                    dialog = page.locator(INCENTIVE_PUSH_DIALOG_SEL).filter(has_text="批量素材推送")
                    wait_for_visible(dialog, INCENTIVE_PUSH_TIMEOUT, stop_event)

                    dialog.locator(".arco-select", has=page.get_by_placeholder("请选择媒体渠道")).click()
                    engine_opt = page.locator(INCENTIVE_PUSH_OPTION_SEL, has_text="巨量引擎")
                    wait_for_visible(engine_opt, INCENTIVE_PUSH_TIMEOUT, stop_event)
                    engine_opt.click()

                    dialog.locator(".arco-select", has=page.get_by_placeholder("请选择投放产品")).click()
                    product_opt = page.locator(INCENTIVE_PUSH_OPTION_SEL, has_text="红果免费短剧")
                    wait_for_visible(product_opt, INCENTIVE_PUSH_TIMEOUT, stop_event)
                    product_opt.click()

                    page.keyboard.press("Escape")

                    account_input = dialog.locator("#ad_account_ids_input")
                    wait_for_visible(account_input, INCENTIVE_PUSH_TIMEOUT, stop_event)
                    account_input.fill(account_id)

                    confirm_btn = dialog.get_by_role("button", name="确定")
                    wait_for_visible(confirm_btn, INCENTIVE_PUSH_TIMEOUT, stop_event)
                    confirm_btn.click()

                    wait_for_hidden(dialog, INCENTIVE_PUSH_WAIT_AFTER, stop_event)
                    log_func(f"  ✅ 第 {page_num} 页推送完成\n")
                    success_count += 1
                    sleep_ms(page, INCENTIVE_PUSH_BETWEEN, stop_event)

                except StopRequested:
                    raise
                except Exception as e:
                    log_func(f"  ❌ 第 {page_num} 页推送失败：{e}\n")
                    fail_count += 1
                    try:
                        page.keyboard.press("Escape")
                    except Exception:
                        pass
                    sleep_ms(page, INCENTIVE_PUSH_BETWEEN, stop_event)
                    try:
                        wait_for_hidden(
                            page.locator(INCENTIVE_PUSH_DIALOG_SEL).filter(has_text="批量素材推送"),
                            INCENTIVE_PUSH_TIMEOUT, stop_event)
                    except StopRequested:
                        raise
                    except Exception:
                        pass

                if page_num < total_pages:
                    try:
                        next_btn = page.locator(INCENTIVE_PUSH_NEXT_BTN)
                        wait_for_visible(next_btn, INCENTIVE_PUSH_TIMEOUT, stop_event)
                        next_btn.click()
                        sleep_ms(page, INCENTIVE_PUSH_BETWEEN, stop_event)
                    except StopRequested:
                        raise
                    except Exception as e:
                        log_func(f"  ⚠️ 翻页失败：{e}，停止执行\n")
                        break
    except StopRequested:
        log_func("\n⏹ 已停止\n")

    log_func(f"\n{'='*40}\n")
    log_func(f"🎉 全部完成！成功：{success_count} 页，失败：{fail_count} 页\n")
