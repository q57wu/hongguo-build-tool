"""
RTA 工具共用基础模块
两个脚本（rta_set / rta_check）共用的常量、工具函数、弹窗处理、页面导航。
所有原 print/logging 输出统一改成 log_func(msg) 回调。
"""

import re
from typing import Callable, List, Optional

from playwright.sync_api import (
    Browser,
    Frame,
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  RTA ID 映射（剧型代码 → (RTA_ID, 剧型名)）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RTA_ID_MAP = {
    "1": ("38588", "常规剧"),
    "2": ("39166", "定制剧"),
    "3": ("34475", "激励"),
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  常量 ─ 连接 & URL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CDP_URL = "http://localhost:9222"
TARGET_URL = (
    "https://ad.oceanengine.com/pages/toolbox/rta_management.html?aadvid={aadvid}"
)
TOOL_OVERVIEW_URL = (
    "https://ad.oceanengine.com/pages/overview.html?from=tool&aadvid={aadvid}"
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  常量 ─ 选择器
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INPUT_SELECTOR = 'input[placeholder="请输入RTA ID或者备注内容"]'
SEARCH_SELECTOR = "button.search"
TOOL_SELECTOR = "#firstTitle_tool"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  常量 ─ 等待时间（ms）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WAIT_TINY = 120
WAIT_SHORT = 250
WAIT_MEDIUM = 500
WAIT_PAGE = 1200
FAST_TIMEOUT = 2000
SEARCH_TIMEOUT = 12000

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  常量 ─ 界面文案 & 正则
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RTA_TEXT = "RTA策略管理"
SET_RANGE_TEXT = "设置生效范围"
ACCOUNT_TEXT = "投放账户"
CONFIRM_TEXT = "确定"
SKIP_TEXT = "跳过"
STATUS_ENABLED_TEXT = "启用中"

SUCCESS_RE = re.compile(r"设置生效范围成功|操作成功")
AGREE_RE = re.compile(r"我已阅读并同意")
NO_DATA_RE = re.compile(r"暂无数据|共 0 条记录")

_GUIDE_TEXTS = [SKIP_TEXT, "知道了", "我知道了"]
_CLOSE_TEXTS = ["关闭", "知道了", "我知道了"]

_IMG_POPUP_SELECTORS = [
    ".de-custom-wrapper-modal .absolute.cursor-pointer",
    ".de-custom-wrapper-modal img.absolute.cursor-pointer",
]

_AGREEMENT_SELECTORS = [
    "#ad-agreement-background",
    ".ad_fe_reuse_sdk-iframe-background.sdk-display-block",
    "#ad-agreement",
    ".ad_fe_reuse_sdk-iframe.sdk-display-block",
]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  JS 辅助脚本
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_JS_CLICK_VISIBLE = """
() => {
    const isVisible = (el) => {
        if (!el) return false;
        const s = window.getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0
            && s.display !== 'none' && s.visibility !== 'hidden';
    };
    const nodes = Array.from(document.querySelectorAll('body *'));
    const target = nodes.find(el => {
        if (!isVisible(el)) return false;
        const text = (el.innerText || '').replace(/\\s+/g, ' ');
        return MATCH_FN;
    });
    if (!target) return false;
    target.click();
    return true;
}
"""

_JS_CLICK_EXACT_TEXT = """
(text) => {
    const isVisible = (el) => {
        if (!el) return false;
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
    };
    const nodes = Array.from(document.querySelectorAll('body *'));
    const target = nodes.find(el => isVisible(el) && (el.innerText || '').trim() === text);
    if (!target) return false;
    target.click();
    return true;
}
"""

_JS_CHECK_RTA_SWITCH = """
(rtaId) => {
    const rows = document.querySelectorAll('.bui-table-body tr');
    for (const row of rows) {
        const text = (row.innerText || '').replace(/\\s+/g, ' ');
        if (text.includes(rtaId)) {
            const sw = row.querySelector('.bui-switch');
            if (!sw) return 'no_switch';
            if (sw.classList.contains('bui-switch-checked')) return 'enabled';
            return 'disabled';
        }
    }
    return 'not_found';
}
"""

_JS_CHECK_RTA_IN_TABLE = """
(rtaId) => {
    const rows = document.querySelectorAll('.bui-table-body tr');
    for (const row of rows) {
        const cells = row.querySelectorAll('td');
        if (cells.length < 5) continue;
        const idText = (cells[2] && cells[2].innerText || '').trim();
        if (idText === rtaId) {
            const sw = row.querySelector('.bui-switch');
            if (sw && sw.classList.contains('bui-switch-checked')) return 'enabled';
            const statusText = (cells[4] && cells[4].innerText || '').trim();
            if (statusText === '启用中') return 'enabled';
            return 'disabled';
        }
    }
    return 'not_found';
}
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  基础工具函数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def wait(page: Page, ms: int) -> None:
    page.wait_for_timeout(ms)


def visible(locator: Locator, timeout: int = 300) -> bool:
    try:
        locator.first.wait_for(state="visible", timeout=timeout)
        return True
    except Exception:
        return False


def click_if_visible(locator: Locator, timeout: int = 300, force: bool = True) -> bool:
    try:
        target = locator.first
        target.wait_for(state="visible", timeout=timeout)
        target.click(timeout=timeout, force=force)
        return True
    except Exception:
        return False


def fill_input(locator: Locator, value: str, timeout: int = 3000) -> None:
    target = locator.first
    target.wait_for(state="visible", timeout=timeout)
    target.click(timeout=timeout)
    target.fill(value, timeout=timeout)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  页面 / 浏览器初始化
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _install_dialog_handler(page: Page, log_func: Callable) -> None:
    def _on_dialog(dialog):
        try:
            log_func(f"检测到原生弹窗，已自动关闭：{dialog.message}")
            dialog.dismiss()
        except Exception:
            pass

    page.on("dialog", _on_dialog)


def pick_page(browser: Browser, log_func: Callable) -> Page:
    """优先复用已打开的巨量引擎页签，否则新建。"""
    for context in browser.contexts:
        for page in reversed(context.pages):
            try:
                if "ad.oceanengine.com" in page.url:
                    page.bring_to_front()
                    _install_dialog_handler(page, log_func)
                    return page
            except Exception:
                continue

    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.new_page()
    page.bring_to_front()
    _install_dialog_handler(page, log_func)
    return page


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  弹窗处理
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _get_agreement_frame(page: Page) -> Optional[Frame]:
    for frame in page.frames:
        try:
            if "ad-agreement-modal" in frame.url:
                return frame
        except Exception:
            continue
    return None


def _close_image_popup(page: Page, log_func: Callable) -> bool:
    for selector in _IMG_POPUP_SELECTORS:
        if click_if_visible(page.locator(selector), timeout=250, force=True):
            log_func("已关闭图片弹窗")
            wait(page, WAIT_SHORT)
            return True
    return False


def _close_top_banner(page: Page, log_func: Callable) -> bool:
    if click_if_visible(page.locator(".oc-banner-close"), timeout=200, force=True):
        log_func("已关闭顶部提示")
        wait(page, WAIT_TINY)
        return True
    return False


def _close_guide_popup(page: Page, log_func: Callable) -> bool:
    locators = [
        page.get_by_text(SKIP_TEXT, exact=True),
        page.get_by_role("button", name=SKIP_TEXT, exact=True),
    ]
    locators += [page.get_by_text(t, exact=True) for t in _GUIDE_TEXTS[1:]]
    for loc in locators:
        if click_if_visible(loc, timeout=250, force=True):
            log_func("已关闭引导弹窗")
            wait(page, WAIT_SHORT)
            return True
    return False


def _handle_agreement_popup(page: Page, log_func: Callable) -> bool:
    """处理协议弹窗：滚动 → 勾选 → 确认。"""
    if not any(visible(page.locator(s), 150) for s in _AGREEMENT_SELECTORS):
        return False

    frame = _get_agreement_frame(page)
    if not frame:
        return False

    log_func("检测到协议弹窗，开始处理")

    try:
        body = frame.locator(".body")
        if visible(body, 500):
            body.first.evaluate("el => { el.scrollTop = el.scrollHeight; }")
            wait(page, WAIT_TINY)
    except Exception:
        pass

    try:
        click_if_visible(frame.get_by_text(AGREE_RE), timeout=600, force=True)
    except Exception:
        pass

    try:
        checkbox = frame.locator('input[type="checkbox"]')
        if checkbox.count() > 0 and not checkbox.first.is_checked():
            checkbox.first.check(force=True)
            wait(page, WAIT_TINY)
    except Exception:
        pass

    try:
        confirm = frame.get_by_role("button", name=CONFIRM_TEXT, exact=True).first
        confirm.wait_for(state="visible", timeout=1000)
        for _ in range(8):
            try:
                if confirm.is_enabled():
                    confirm.click(force=True)
                    log_func("已确认协议弹窗")
                    wait(page, WAIT_MEDIUM)
                    return True
            except Exception:
                pass
            wait(page, 100)
    except Exception:
        pass

    return False


def _close_text_popup(page: Page, log_func: Callable) -> bool:
    for text in _CLOSE_TEXTS:
        if click_if_visible(page.get_by_text(text, exact=True), timeout=200, force=True):
            log_func(f"已关闭文本弹窗：{text}")
            wait(page, WAIT_SHORT)
            return True
    return False


def close_known_popups(page: Page, log_func: Callable, max_rounds: int = 3) -> bool:
    """循环尝试关闭所有已知弹窗，最多 max_rounds 轮。"""
    handlers = [
        _close_image_popup,
        _close_top_banner,
        _close_guide_popup,
        _handle_agreement_popup,
        _close_text_popup,
    ]
    acted_any = False
    for _ in range(max_rounds):
        acted = any(h(page, log_func) for h in handlers)
        if not acted:
            break
        acted_any = True
        wait(page, WAIT_SHORT)
    return acted_any


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  页面导航 ─ 进入 RTA 管理页
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _is_rta_page(page: Page) -> bool:
    return "rta_management" in page.url


def _js_click_card() -> str:
    return _JS_CLICK_VISIBLE.replace(
        "MATCH_FN",
        "text.includes('RTA策略管理') && text.includes('通过API对RTA策略进行管理')",
    )


def _js_click_menu_item() -> str:
    return _JS_CLICK_VISIBLE.replace(
        "MATCH_FN",
        "(el.innerText || '').trim() === 'RTA策略管理'",
    )


def _navigate_via_menu(page: Page, aadvid: str, log_func: Callable) -> bool:
    """兜底方案：通过菜单点击进入 RTA 页面。"""
    log_func("🔧 尝试通过菜单手动导航进入 RTA 策略管理...")

    if "ad.oceanengine.com" not in page.url or f"aadvid={aadvid}" not in page.url:
        fallback_url = f"https://ad.oceanengine.com/overture/index?aadvid={aadvid}"
        log_func(f"    先导航到广告平台首页：{fallback_url}")
        try:
            page.goto(fallback_url, wait_until="domcontentloaded", timeout=30000)
            wait(page, WAIT_PAGE)
            close_known_popups(page, log_func)
        except Exception as exc:
            log_func(f"    导航到广告平台首页失败：{exc}")
            return False

    # 点击工具菜单
    tool_clicked = False
    tool_locators = [
        page.get_by_text("工具", exact=True),
        page.locator('a:has-text("工具"), span:has-text("工具")'),
        page.locator('[class*="nav"] :text-is("工具")'),
    ]
    for loc in tool_locators:
        try:
            if click_if_visible(loc, timeout=2000, force=False):
                log_func("    已点击「工具」菜单")
                tool_clicked = True
                wait(page, WAIT_MEDIUM)
                break
        except Exception:
            continue

    if not tool_clicked:
        try:
            tool_clicked = page.evaluate(_JS_CLICK_EXACT_TEXT, "工具")
            if tool_clicked:
                log_func("    已通过 JS 点击「工具」菜单")
                wait(page, WAIT_MEDIUM)
        except Exception:
            pass

    if not tool_clicked:
        log_func("    ❌ 未找到「工具」菜单入口")
        return False

    # 点击 RTA 策略管理
    rta_clicked = False
    rta_locators = [
        page.get_by_text("RTA策略管理", exact=True),
        page.get_by_text("RTA策略管理"),
        page.locator('a:has-text("RTA策略管理"), span:has-text("RTA策略管理")'),
        page.get_by_text("RTA设置"),
        page.get_by_text("RTA 策略管理"),
    ]
    for loc in rta_locators:
        try:
            if click_if_visible(loc, timeout=2000, force=False):
                log_func("    已点击「RTA策略管理」")
                rta_clicked = True
                wait(page, 1500)
                break
        except Exception:
            continue

    if not rta_clicked:
        for text in ["RTA策略管理", "RTA设置", "RTA 策略管理"]:
            try:
                rta_clicked = page.evaluate(_JS_CLICK_EXACT_TEXT, text)
                if rta_clicked:
                    log_func(f"    已通过 JS 点击「{text}」")
                    wait(page, 1500)
                    break
            except Exception:
                continue

    if not rta_clicked:
        log_func("    ❌ 未找到「RTA策略管理」菜单项")
        return False

    wait(page, WAIT_PAGE)
    if _is_rta_page(page):
        log_func("    ✅ 通过菜单成功进入 RTA 策略管理页面")
        return True

    wait(page, 2000)
    if _is_rta_page(page):
        log_func("    ✅ 通过菜单成功进入 RTA 策略管理页面")
        return True

    log_func(f"    ❌ 菜单点击后仍未进入 RTA 页面，当前 URL：{page.url}")
    return False


def ensure_rta_page(page: Page, aadvid: str, log_func: Callable, _retry: int = 0) -> None:
    """确保当前页面已进入 RTA 策略管理，搜索框可见。"""
    MAX_GOTO_RETRY = 2
    RETRY_DELAY = 3000
    url = TARGET_URL.format(aadvid=aadvid)
    search_input = page.locator(INPUT_SELECTOR)

    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    log_func(f"打开目标页：{url}")
    wait(page, WAIT_PAGE)

    if not _is_rta_page(page):
        actual = page.url
        log_func(f"⚠️  被重定向到非 RTA 页面：{actual}")
        if _retry < MAX_GOTO_RETRY:
            log_func(f"    等待 {RETRY_DELAY}ms 后第 {_retry + 1} 次重试 goto...")
            wait(page, RETRY_DELAY)
            return ensure_rta_page(page, aadvid, log_func, _retry + 1)
        log_func(f"⚠️  goto 已重试 {MAX_GOTO_RETRY} 次仍被重定向，改用菜单导航...")
        if not _navigate_via_menu(page, aadvid, log_func):
            raise RuntimeError(
                f"无法进入 RTA 页面，aadvid: {aadvid}。"
                f"goto 被重定向且菜单导航也失败，最终 URL: {page.url}"
            )

    close_known_popups(page, log_func)

    if visible(search_input, 3000):
        return

    close_known_popups(page, log_func)
    wait(page, WAIT_SHORT)
    if visible(search_input, 2000):
        return

    log_func("搜索框未出现，reload 重试")
    page.reload(wait_until="domcontentloaded", timeout=30000)
    wait(page, WAIT_PAGE)
    close_known_popups(page, log_func)

    try:
        search_input.first.wait_for(state="visible", timeout=8000)
    except PlaywrightTimeoutError:
        raise RuntimeError(f"进入 RTA策略管理 页失败，aadvid: {aadvid}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  搜索与结果等待
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _wait_search_result(
    page: Page, rta_id: str, search_button: Locator, log_func: Callable
) -> Locator:
    """轮询等待搜索结果出现，返回匹配行 Locator。"""
    cell = page.get_by_text(re.compile(rf"^\s*{re.escape(rta_id)}\s*$")).first
    row = page.locator("tr").filter(has_text=rta_id).first

    elapsed = 0
    retried = False
    while elapsed < SEARCH_TIMEOUT:
        close_known_popups(page, log_func)

        if visible(cell, 150):
            log_func(f"已识别到 RTA ID：{rta_id}")
            return row

        if visible(page.get_by_text(NO_DATA_RE), 150):
            raise RuntimeError(f"搜索后未找到 RTA ID {rta_id}")

        if not retried and elapsed >= 1500:
            log_func("搜索结果未及时出现，重试点击搜索")
            search_button.first.click(force=True, timeout=FAST_TIMEOUT)
            retried = True

        wait(page, 250)
        elapsed += 250

    raise RuntimeError(f"等待 RTA ID {rta_id} 的搜索结果超时")


def search_target_rta(page: Page, rta_id: str, log_func: Callable) -> Locator:
    """在搜索框中输入 RTA ID 并返回结果行。"""
    fill_input(page.locator(INPUT_SELECTOR), rta_id)
    search_button = page.locator(SEARCH_SELECTOR)
    search_button.first.click(force=True, timeout=FAST_TIMEOUT)
    log_func(f"已搜索 RTA ID：{rta_id}")
    close_known_popups(page, log_func)
    return _wait_search_result(page, rta_id, search_button, log_func)
