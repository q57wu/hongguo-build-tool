"""
backend/core/playwright_utils.py
Playwright 操作的基础工具。
"""
import re
import time
import logging
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from backend.core.constants import TIMEOUT, RE_CONFIRM, WaitTimes

_logger = logging.getLogger(__name__)


def safe_click(popup, locator, *, timeout=TIMEOUT, retries=3, desc="", logger=None, W=None):
    """点击元素。首次尝试 force=False 让 Playwright 校验可点性；
    若因元素不可交互失败，再降级 force=True 最多重试 retries-1 次。
    这样可避免按钮处于 disabled/is-disabled 状态时点击被静默丢弃。
    """
    for attempt in range(1, retries + 1):
        # 首次用 force=False，失败后降级 force=True
        use_force = (attempt > 1)
        try:
            locator.wait_for(state="visible", timeout=timeout)
            locator.scroll_into_view_if_needed()
            popup.wait_for_timeout(W.TINY if W else 200)
            locator.click(force=use_force)
            if attempt > 1 and logger:
                logger.info(f"🔁 点击在第{attempt}次重试后成功(force={use_force}, {desc})")
            return
        except PlaywrightTimeout:
            if logger: logger.warning(f"⏰ 点击超时({desc}) 第{attempt}/{retries}次")
        except Exception as e:
            if logger: logger.warning(f"⚠️ 点击失败({desc}) 第{attempt}/{retries}次(force={use_force}): {e}")
        if attempt < retries:
            popup.wait_for_timeout(W.LONG if W else 1000)
    raise Exception(f"❌ 点击最终失败({desc})，已重试{retries}次")


def _locator_count(locator):
    try: return locator.count()
    except Exception as e:
        _logger.debug(f"_locator_count 失败: {e}")
        return 0


def wait_loading_gone(popup, container, *, timeout=30_000):
    mask = container.locator(".el-loading-mask").first
    if mask.count() > 0:
        try: mask.wait_for(state="hidden", timeout=timeout)
        except PlaywrightTimeout as e:
            _logger.debug(f"wait_loading_gone: loading mask 超时未消失: {e}")


def wait_idle(target, *, mask_timeout=8_000, network=False, network_timeout=3_000):
    try:
        mask = target.locator(".el-loading-mask:visible")
        if mask.count() > 0:
            mask.first.wait_for(state="hidden", timeout=mask_timeout)
    except Exception as e:
        _logger.debug(f"wait_idle: mask 等待异常(容错，忽略): {e}")
    if network:
        try: target.wait_for_load_state("networkidle", timeout=network_timeout)
        except Exception as e:
            _logger.debug(f"wait_idle: networkidle 超时(容错，忽略): {e}")


def wait_small(popup, ms=300):
    try:
        mask = popup.locator(".el-loading-mask:visible")
        if mask.count() > 0:
            mask.first.wait_for(state="hidden", timeout=max(ms, 1500))
            return
    except Exception as e:
        _logger.debug(f"wait_small: mask 等待异常(容错，忽略): {e}")
    popup.wait_for_timeout(min(ms, max(80, ms // 2)))


def _safe_page_title(page):
    try:
        return page.title()
    except Exception as e:
        _logger.debug(f"_safe_page_title 失败: {e}")
        return ""


def _safe_page_url(page):
    try:
        return page.url
    except Exception as e:
        _logger.debug(f"_safe_page_url 失败: {e}")
        return ""


def _is_browser_internal_page(url):
    value = (url or "").lower()
    return value.startswith(("about:", "chrome:", "devtools:", "edge:", "trae:"))


def select_build_page(context, logger):
    pages = list(context.pages)
    logger.info(f"🔎 当前 CDP 连接到 {len(pages)} 个页面")
    usable_pages = []
    for idx, pg in enumerate(pages, 1):
        url = _safe_page_url(pg)
        title = _safe_page_title(pg)
        logger.info(f"  页面{idx}: {title or '无标题'} | {url or '无URL'}")
        if not _is_browser_internal_page(url):
            usable_pages.append(pg)

    candidates = []
    for pg in usable_pages:
        url = _safe_page_url(pg).lower()
        title = _safe_page_title(pg).lower()
        score = 0
        if "qianchuan" in url or "ad.oceanengine" in url or "巨量" in title or "千川" in title:
            score += 80
        if "promotion" in url or "campaign" in url or "project" in url or "广告" in title or "计划" in title or "推广" in title:
            score += 30
        try:
            if pg.locator("button:has-text('批量新建')").count() > 0:
                score += 70
            elif pg.locator("button:has-text('新建')").count() > 0:
                score += 30
        except Exception as e:
            _logger.debug(f"select_build_page: 评分时按钮检查失败: {e}")
        candidates.append((score, pg))

    candidates.sort(key=lambda item: item[0], reverse=True)
    if candidates and candidates[0][0] > 0:
        page = candidates[0][1]
    elif usable_pages:
        page = usable_pages[-1]
    elif pages:
        page = pages[-1]
    else:
        raise RuntimeError("没有检测到可控制的浏览器页面，请确认浏览器已用 9222 调试端口启动")

    page.set_default_timeout(15_000)
    # bring_to_front 已移除：select_build_page 选页时不弹前台，避免干扰用户
    logger.info(f"🎯 已选择操作页面：{_safe_page_title(page) or '无标题'} | {_safe_page_url(page) or '无URL'}")
    return page


def get_visible_layer(popup, *, desc="弹窗", timeout=15_000, logger=None, W=None):
    selectors = [
        "div.el-dialog__wrapper:visible",
        "div.el-dialog:visible",
        "div.mg-dialog-wrapper:visible",
        "div.cl-drawer:visible",
        "div.drawer-content:visible",
        "div[role='dialog']:visible",
        ".arco-modal:visible",
        ".arco-drawer:visible",
    ]
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        for sel in selectors:
            layers = popup.locator(sel)
            n = _locator_count(layers)
            if n > 0:
                if logger:
                    logger.info(f"✅ 已识别{desc}：{sel}，数量 {n}")
                return layers.nth(n - 1)
        wait_small(popup, W.TINY if W else 200)
    details = []
    for sel in selectors:
        try:
            details.append(f"{sel}={popup.locator(sel).count()}")
        except Exception as e:
            details.append(f"{sel}=?(err:{e})")
    raise PlaywrightTimeout(f"等待{desc}超时，未匹配到可见弹层；{' | '.join(details)}")


def get_visible_drawer(popup):
    drawer = popup.locator("div.drawer-content:visible").last
    wrap = drawer.locator("div.el-scrollbar__wrap").first
    return drawer, wrap


def scroll_wrap_to_bottom(popup, wrap, W):
    if wrap.count() > 0:
        try: wrap.evaluate("wrap => wrap.scrollTop = wrap.scrollHeight")
        except Exception as e:
            _logger.debug(f"scroll_wrap_to_bottom: 滚动失败(容错，忽略): {e}")
    wait_small(popup, W.SHORT)


def scroll_to_module(popup, wrap, module_id, W):
    if wrap.count() > 0:
        wrap.evaluate(
            """(wrap, id) => {
                const el = wrap.querySelector('#' + id);
                if (el) wrap.scrollTop = el.offsetTop - 80;
            }""", module_id)
    else:
        popup.locator(f"#{module_id}").scroll_into_view_if_needed()
    wait_small(popup, 250)


def click_top_confirm(popup, scope=None, *, desc="确认按钮", timeout=TIMEOUT, wait_close=False, logger=None, W=None):
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        scopes = []
        if scope is not None:
            scopes.append(scope)
            pd = scope.locator("xpath=ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' cl-drawer ')][1]")
            if _locator_count(pd) > 0: scopes.append(pd.first)
            pw2 = scope.locator("xpath=ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' mg-dialog-wrapper ')][1]")
            if _locator_count(pw2) > 0: scopes.append(pw2.first)
        else:
            for sel in ["div.el-dialog__wrapper:visible", "div.mg-dialog-wrapper:visible",
                        "div.cl-drawer:visible", "div.el-dialog:visible"]:
                layers = popup.locator(sel)
                n = _locator_count(layers)
                if n > 0: scopes.append(layers.nth(n - 1))

        for sc in scopes:
            for candidates in [
                sc.locator("button.el-button--primary:not(.is-disabled):visible").filter(has_text=RE_CONFIRM),
                sc.locator("button:not(.is-disabled):visible").filter(has_text=RE_CONFIRM),
            ]:
                if _locator_count(candidates) > 0:
                    btn = candidates.last
                    safe_click(popup, btn, desc=desc, logger=logger, W=W)
                    if wait_close:
                        try: sc.wait_for(state="hidden", timeout=4_000)
                        except Exception as e:
                            _logger.debug(f"click_top_confirm: 等待弹层关闭超时(容错): {e}")
                    return
        wait_small(popup, W.TINY if W else 200)
    raise Exception(f"❌ 当前范围内未找到可点击的确认按钮: {desc}")


def _visible_confirm_count(popup):
    selectors = [
        "div.operate-button:visible button.el-button--primary:visible",
        "div.operate-button:visible button:visible",
        "button.el-button--primary.el-button--small:visible",
        "button.el-button--primary:visible",
        "button:visible",
    ]
    total = 0
    for sel in selectors:
        total += _locator_count(popup.locator(sel).filter(has_text=RE_CONFIRM))
    return total


def _click_confirm_button_hard(popup, button, *, desc, logger=None, W=None):
    # 前置检查：如果按钮已不可见或已 detached，直接返回成功
    try:
        if not button.is_visible():
            return True
    except Exception:
        # is_visible 异常通常意味着元素已 detached，视为弹窗已关闭
        return True
    try:
        button.wait_for(state="visible", timeout=2_000)
    except Exception as e:
        _logger.debug(f"_click_confirm_button_hard: wait_for visible 超时({desc}): {e}")
        # 等不到可见说明按钮已消失，视为成功
        return _visible_confirm_count(popup) == 0
    try:
        button.scroll_into_view_if_needed()
    except Exception as e:
        _logger.debug(f"_click_confirm_button_hard: scroll_into_view 失败({desc}): {e}")
    wait_small(popup, W.TINY if W else 200)
    methods = ["普通点击", "强制点击", "JS点击", "坐标点击"]
    last_error = None
    for method in methods:
        # 每次尝试前检查按钮是否仍然可见（并行模式下可能已被其他操作关闭）
        try:
            if not button.is_visible():
                return True
        except Exception:
            return True
        try:
            if method == "普通点击":
                button.click(timeout=3_000)
            elif method == "强制点击":
                button.click(force=True, timeout=3_000)
            elif method == "JS点击":
                button.evaluate("el => el.click()")
            else:
                box = button.bounding_box()
                if not box:
                    continue
                popup.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            if logger:
                logger.info(f"🖱️ {desc}已执行{method}")
            wait_small(popup, W.NORMAL if W else 500)
            if _visible_confirm_count(popup) == 0:
                return True
        except Exception as e:
            last_error = e
            if logger:
                logger.warning(f"⚠️ {desc}{method}失败: {e}")
    if logger and last_error:
        logger.warning(f"⚠️ {desc}所有点击方式后仍未关闭: {last_error}")
    return _visible_confirm_count(popup) == 0


def wait_locator_ready(popup, locator, *, timeout=TIMEOUT, desc="元素", W=None):
    locator.wait_for(state="visible", timeout=timeout)
    try: locator.scroll_into_view_if_needed()
    except Exception as e:
        _logger.debug(f"wait_locator_ready: scroll_into_view 失败({desc}): {e}")
    wait_small(popup, W.TINY if W else 200)
    return locator


def safe_select_option(popup, trigger_locator, option_text, *, desc="", logger=None, W=None):
    try:
        safe_click(popup, trigger_locator, desc=f"{desc}下拉触发", logger=logger, W=W)
        dropdown = popup.locator("ul.el-select-dropdown__list:visible").last
        dropdown.wait_for(state="visible", timeout=TIMEOUT)
        option = dropdown.locator("li.el-select-dropdown__item").filter(has_text=option_text).first
        if option.count() > 0:
            safe_click(popup, option, desc=f"{desc}选择'{option_text}'", logger=logger, W=W)
            return True
        return False
    except Exception as e:
        _logger.debug(f"safe_select_option: 选择失败({desc}): {e}")
        return False


def click_optional_confirm(popup, *, desc="可选确认按钮", timeout=6_000, logger=None, W=None):
    deadline = time.time() + timeout / 1000
    direct_selectors = [
        "div.operate-button:visible button.el-button--primary:visible",
        "div.operate-button:visible button:visible",
        "button.el-button--primary.el-button--small:visible",
        "button.el-button--primary:visible",
        "button:visible",
    ]
    while time.time() < deadline:
        # 前置检查：如果页面上已无可见确认按钮，直接返回成功
        # （并行模式下弹窗可能已被页面自动关闭或被其他操作处理）
        if _visible_confirm_count(popup) == 0:
            if logger:
                logger.info(f"✅ 已点击{desc}并确认弹层消失")
            return True
        for sel in direct_selectors:
            candidates = popup.locator(sel).filter(has_text=RE_CONFIRM)
            count = _locator_count(candidates)
            if count > 0:
                btn = candidates.last
                ok = _click_confirm_button_hard(popup, btn, desc=desc, logger=logger, W=W)
                wait_idle(popup, mask_timeout=5_000)
                if ok:
                    if logger:
                        logger.info(f"✅ 已点击{desc}并确认弹层消失")
                    wait_small(popup, W.NORMAL if W else 500)
                    return True
                if logger:
                    logger.warning(f"⚠️ 已尝试点击{desc}，但按钮仍可见，继续重试")
        try:
            click_top_confirm(popup, desc=desc, timeout=500, wait_close=True, logger=logger, W=W)
            wait_idle(popup, mask_timeout=5_000)
            if _visible_confirm_count(popup) == 0:
                if logger:
                    logger.info(f"✅ 已点击{desc}并确认弹层消失")
                wait_small(popup, W.NORMAL if W else 500)
                return True
        except Exception as e:
            _logger.debug(f"click_optional_confirm: click_top_confirm 内部失败(容错): {e}")
        wait_small(popup, W.TINY if W else 200)
    if logger:
        logger.warning(f"⚠️ {desc}点击后仍未消失，后续会继续等待素材弹窗关闭")
    return False
