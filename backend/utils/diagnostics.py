"""
网页结构诊断：打印当前 Playwright 页面/弹窗/素材列表状态。
"""
from __future__ import annotations

import time
from pathlib import Path

from backend.core.constants import APP_DIR
from backend.core.playwright_utils import _safe_page_title, _safe_page_url


_DIAG_DIR = APP_DIR / "diagnostics"


_LAYER_SELECTORS = [
    "div.el-dialog__wrapper:visible",
    "div.el-dialog:visible",
    "div.mg-dialog-wrapper:visible",
    "div.cl-drawer:visible",
    "div.drawer-content:visible",
    "div[role='dialog']:visible",
    ".arco-modal:visible",
    ".arco-drawer:visible",
]


def _safe_count(page, selector):
    try:
        return page.locator(selector).count()
    except Exception as e:
        return f"ERR:{e}"


def _safe_text(locator, limit=120):
    try:
        text = locator.inner_text(timeout=1_000).strip()
    except Exception:
        return ""
    text = " ".join(text.split())
    return text[:limit]


def _safe_attr(locator, attr, limit=160):
    try:
        value = (locator.get_attribute(attr, timeout=1_000) or "").strip()
    except Exception:
        return ""
    return value[:limit]


def _collect_items(page, selector, *, limit=30, label_attr=None):
    items = []
    loc = page.locator(selector)
    try:
        count = loc.count()
    except Exception as e:
        return [f"count error: {e}"]
    for i in range(min(count, limit)):
        item = loc.nth(i)
        text = _safe_text(item)
        extra = ""
        if label_attr:
            extra = _safe_attr(item, label_attr)
        if text or extra:
            if extra and extra != text:
                items.append(f"{i + 1}. {text} [{label_attr}={extra}]")
            else:
                items.append(f"{i + 1}. {text or extra}")
    if count > limit:
        items.append(f"... 共 {count} 个，仅显示前 {limit} 个")
    return items


def _collect_material_state(page):
    lines = []
    wrappers = page.locator("div.material-wrapper")
    try:
        wrapper_count = wrappers.count()
    except Exception:
        wrapper_count = 0
    lines.append(f"material-wrapper 数量: {wrapper_count}")
    for idx in range(min(wrapper_count, 12)):
        wrapper = wrappers.nth(idx)
        prefix = f"material-wrapper[{idx}]"
        try:
            box = wrapper.bounding_box()
        except Exception:
            box = None
        try:
            scroll = wrapper.evaluate(
                "el => ({scrollTop: el.scrollTop, scrollHeight: el.scrollHeight, clientHeight: el.clientHeight, className: el.className})"
            )
        except Exception as e:
            scroll = f"ERR:{e}"
        try:
            item_count = wrapper.locator("div.material-item").count()
        except Exception:
            item_count = "?"
        try:
            all_name_count = wrapper.locator(".material-name").count()
        except Exception:
            all_name_count = "?"
        lines.append(f"{prefix} box={box} scroll={scroll} material-item={item_count} material-name={all_name_count}")
        names = wrapper.locator(".material-name:visible")
        try:
            name_count = names.count()
        except Exception as e:
            lines.append(f"{prefix} 可见素材名计数失败: {e}")
            continue
        lines.append(f"{prefix} 可见素材名数量: {name_count}")
        for i in range(min(name_count, 20)):
            name_el = names.nth(i)
            name = _safe_attr(name_el, "title") or _safe_text(name_el)
            if name:
                lines.append(f"  素材{i + 1}: {name}")
    return lines


def _collect_dom_snapshot(page):
    script = r"""
    () => {
      const nodes = Array.from(document.querySelectorAll('body *'));
      const visible = nodes.filter(el => {
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
      }).slice(0, 180);
      return visible.map(el => {
        const r = el.getBoundingClientRect();
        const cls = typeof el.className === 'string' ? el.className : '';
        const id = el.id ? '#' + el.id : '';
        const text = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 80);
        return `${el.tagName.toLowerCase()}${id}${cls ? '.' + cls.trim().replace(/\s+/g, '.') : ''} ` +
          `[${Math.round(r.x)},${Math.round(r.y)},${Math.round(r.width)}x${Math.round(r.height)}] ${text}`;
      });
    }
    """
    try:
        return page.evaluate(script)
    except Exception as e:
        return [f"DOM snapshot error: {e}"]


def dump_page_structure(page, logger=None, reason="manual", emit_bridge=True):
    lines = []
    ts = time.strftime("%Y%m%d_%H%M%S")
    title = _safe_page_title(page)
    url = _safe_page_url(page)
    lines.append("═" * 80)
    lines.append(f"网页结构诊断 | reason={reason} | {ts}")
    lines.append(f"title: {title}")
    lines.append(f"url: {url}")
    try:
        viewport = page.viewport_size
    except Exception as e:
        viewport = f"ERR:{e}"
    lines.append(f"viewport: {viewport}")

    lines.append("-- 弹层计数 --")
    for sel in _LAYER_SELECTORS:
        lines.append(f"{sel} = {_safe_count(page, sel)}")

    lines.append("-- loading / 遮罩 --")
    for sel in [".el-loading-mask", ".el-loading-mask:visible", ".arco-spin:visible", ".arco-modal-mask:visible", ".v-modal:visible"]:
        lines.append(f"{sel} = {_safe_count(page, sel)}")

    lines.append("-- 分页 --")
    lines.extend(_collect_items(page, "div.el-pagination:visible", limit=8))
    lines.extend(_collect_items(page, "li.number:visible", limit=20))
    lines.extend(_collect_items(page, "button.btn-prev:visible, button.btn-next:visible", limit=10))

    lines.append("-- 可见按钮 --")
    lines.extend(_collect_items(page, "button:visible", limit=40))

    lines.append("-- 可见输入框 --")
    lines.extend(_collect_items(page, "input:visible, textarea:visible", limit=30, label_attr="placeholder"))

    lines.append("-- 可见 tab / pane --")
    lines.extend(_collect_items(page, "[role='tab']:visible, .el-tabs__item:visible, .arco-tabs-header-title:visible", limit=30))

    lines.append("-- 素材区域 --")
    lines.extend(_collect_material_state(page))

    lines.append("-- 可见 DOM 快照前 180 个 --")
    lines.extend(_collect_dom_snapshot(page))
    lines.append("═" * 80)

    text = "\n".join(str(x) for x in lines)
    try:
        _DIAG_DIR.mkdir(parents=True, exist_ok=True)
        path = _DIAG_DIR / f"page_structure_{ts}.txt"
        path.write_text(text, encoding="utf-8")
    except Exception:
        path = None

    if logger:
        logger.warning(f"[结构诊断] 已生成网页结构诊断: {path or '写入文件失败'} | reason={reason}")
        for line in lines[:80]:
            logger.warning(f"[结构诊断] {line}")
        if len(lines) > 80:
            logger.warning(f"[结构诊断] ... 诊断内容较长，完整内容见: {path}")

    if emit_bridge:
        try:
            from backend.bridge import bridge
            bridge.emit_log(f"[结构诊断] 已生成网页结构诊断: {path or '写入文件失败'} | reason={reason}", "warn")
            for line in lines[:60]:
                bridge.emit_log(f"[结构诊断] {line}", "warn")
            if len(lines) > 60:
                bridge.emit_log(f"[结构诊断] ... 诊断内容较长，完整内容见: {path}", "warn")
        except Exception:
            pass

    return {"ok": True, "path": str(path) if path else "", "line_count": len(lines), "title": title, "url": url}


def dump_browser_structure(cdp_endpoint="http://localhost:9222", reason="manual"):
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return {"ok": False, "error": f"Playwright 不可用: {e}"}

    results = []
    pw = None
    browser = None
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.connect_over_cdp(cdp_endpoint)
        for ctx_idx, context in enumerate(browser.contexts, 1):
            for page_idx, page in enumerate(context.pages, 1):
                url = _safe_page_url(page)
                if url.lower().startswith(("chrome:", "about:", "edge:", "devtools:")):
                    continue
                results.append(dump_page_structure(
                    page,
                    logger=None,
                    reason=f"{reason}/context{ctx_idx}/page{page_idx}",
                    emit_bridge=True,
                ))
        if not results:
            try:
                from backend.bridge import bridge
                bridge.emit_log("[结构诊断] 未找到可诊断的业务网页，请确认浏览器已打开搭建页面", "warn")
            except Exception:
                pass
        return {"ok": True, "pages": len(results), "results": results}
    except Exception as e:
        try:
            from backend.bridge import bridge
            bridge.emit_log(f"❌ 网页结构诊断失败: {e}", "error")
        except Exception:
            pass
        return {"ok": False, "error": str(e)}
    finally:
        try:
            if browser:
                browser.close()
        except Exception:
            pass
        try:
            if pw:
                pw.stop()
        except Exception:
            pass
