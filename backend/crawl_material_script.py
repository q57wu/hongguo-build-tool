import logging
import re
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except ImportError as e:
    raise ImportError(
        f"缺少依赖 playwright，请先执行：pip install playwright && playwright install chromium\n原始错误: {e}"
    ) from e

try:
    from backend.selectors.loader import get_selector
except ImportError as e:
    raise ImportError(
        f"无法导入 backend.selectors.loader，请确认以项目根目录运行，且 backend/selectors 目录存在\n原始错误: {e}"
    ) from e
from backend.utils.interruptible import (
    StopRequested,
    sleep_ms,
    wait_for_visible,
    check_stop,
)

_logger = logging.getLogger(__name__)


def _sel(section: str, key: str, default: str = "") -> str:
    """获取选择器，配置缺失时返回默认值"""
    s = get_selector(section, key)
    return s if s else default


def safe_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", name).strip()


def normalize_text(text: str) -> str:
    if not text:
        return ""
    return (
        text.replace("：", "")
            .replace(":", "")
            .replace("-", "")
            .replace("_", "")
            .replace(" ", "")
            .replace(".mp4", "")
            .replace(".MP4", "")
            .strip()
            .lower()
    )


def parse_cost(text: str) -> float:
    if not text:
        return 0.0

    text = text.replace(",", "").replace("￥", "").replace("元", "").strip()
    m = re.search(r"\d+(?:\.\d+)?", text)
    return float(m.group(0)) if m else 0.0


def extract_episode_number(title: str):
    if not title:
        return None

    m = re.search(r"[（(]\s*(\d+)\s*[)）]", title)
    if m:
        return m.group(1)

    return None


def get_target_page(browser):
    keywords = [
        "business.oceanengine.com",
        "material_center",
        "management/video",
    ]

    for context in browser.contexts:
        for page in context.pages:
            url = page.url or ""
            if any(k in url for k in keywords):
                return page

    for context in browser.contexts:
        if context.pages:
            return context.pages[0]

    raise RuntimeError("没有找到目标页面，请确认9222浏览器已打开，并且停留在素材管理页面。")


def wait_table_loaded(page, stop_event=None):
    selectors = [
        _sel("material_page", "loading_indicator_primary", ".video-name-content"),
        _sel("material_page", "loading_indicator_fallback1", "tbody tr"),
        _sel("material_page", "loading_indicator_fallback2", ".ovui-table-row"),
    ]

    for selector in selectors:
        try:
            wait_for_visible(page.locator(selector).first, 10000, stop_event)
            return
        except StopRequested:
            raise
        except Exception:
            continue


def clear_and_search(page, drama_name: str, stop_event=None):
    input_selector = _sel("material_page", "search_input", "input[placeholder='请输入视频名称/ID']")
    wait_for_visible(page.locator(input_selector), 15000, stop_event)
    search_input = page.locator(input_selector)

    search_input.click()
    search_input.fill("")
    sleep_ms(page, 300, stop_event)
    search_input.fill(drama_name)
    search_input.press("Enter")

    search_button_selectors = [
        _sel("material_page", "search_button_primary", "span.i-icon-search.filter-search-input-icon"),
        _sel("material_page", "search_button_fallback1", ".filter-search-input-icon"),
        _sel("material_page", "search_button_fallback2", ".ovui-input__suffix .i-icon-search"),
        _sel("material_page", "search_button_fallback3", ".ovui-input__suffix"),
    ]

    clicked = False
    for selector in search_button_selectors:
        check_stop(stop_event)
        try:
            btn = page.locator(selector).first
            if btn.count() > 0:
                btn.click(timeout=3000)
                clicked = True
                break
        except StopRequested:
            raise
        except Exception as e:
            _logger.debug(f"点击搜索按钮 '{selector}' 失败: {e}")

    if not clicked:
        print("未点击到搜索按钮，但已执行回车搜索。")

    sleep_ms(page, 2000, stop_event)
    wait_table_loaded(page, stop_event)


def collect_from_current_page(page, drama_name: str):
    page_items = []

    row_selectors = [
        _sel("material_page", "video_card_row_primary", "tbody tr"),
        _sel("material_page", "video_card_row_fallback", ".ovui-table-row"),
    ]

    rows = None
    for selector in row_selectors:
        loc = page.locator(selector)
        if loc.count() > 0:
            rows = loc
            break

    if rows is None or rows.count() == 0:
        print("没有找到表格行。")
        return []

    row_count = rows.count()
    print(f"当前页行数: {row_count}")

    normalized_drama_name = normalize_text(drama_name)

    for i in range(row_count):
        row = rows.nth(i)

        try:
            # 获取素材名用于匹配剧名
            name_loc = row.locator(_sel("material_page", "video_name", ".video-name-content")).first
            if name_loc.count() == 0:
                continue

            title = name_loc.inner_text().strip()
            if not title:
                continue

            normalized_title = normalize_text(title)
            if normalized_drama_name not in normalized_title:
                continue

            # 获取素材ID
            id_loc = row.locator(_sel("material_page", "video_id", ".video-id")).first
            if id_loc.count() == 0:
                continue

            id_text = id_loc.inner_text().strip()
            # 从 "ID：7596922909102194729" 中提取纯数字ID
            video_id = re.sub(r"^ID[：:]\s*", "", id_text).strip()
            if not video_id:
                continue

            cost_cells = row.locator(_sel("material_page", "video_cost", "td.ovui-table-cell--right"))
            if cost_cells.count() == 0:
                continue

            cost_text = cost_cells.first.inner_text().strip()
            cost_value = parse_cost(cost_text)

            num = extract_episode_number(title)

            print(f"标题: {title} | 素材ID: {video_id} | 提取数字: {num} | 消耗: {cost_value}")

            if num:
                page_items.append({
                    "num": num,
                    "cost": cost_value,
                    "title": title,
                    "video_id": video_id,
                })

        except Exception as e:
            print(f"第 {i + 1} 行处理失败: {e}")
            continue

    return page_items


def filter_items(all_items, min_cost: float = 500, min_count: int = 6):
    if not all_items:
        return []

    all_items_sorted = sorted(all_items, key=lambda x: x["cost"], reverse=True)

    deduped_items = []
    seen = set()
    for item in all_items_sorted:
        if item["num"] not in seen:
            deduped_items.append(item)
            seen.add(item["num"])

    high_cost_items = [item for item in deduped_items if item["cost"] >= min_cost]

    if len(high_cost_items) >= min_count:
        return [item["video_id"] for item in high_cost_items]

    result_items = high_cost_items[:]
    selected_nums = {item["num"] for item in result_items}

    for item in deduped_items:
        if item["num"] in selected_nums:
            continue
        result_items.append(item)
        selected_nums.add(item["num"])
        if len(result_items) >= min_count:
            break

    return [item["video_id"] for item in result_items]


def get_first_row_signature(page) -> str:
    """获取当前页第一行的签名，用于判断翻页是否真的换页了。"""
    try:
        row_selectors = [
            _sel("material_page", "video_card_row_primary", "tbody tr"),
            _sel("material_page", "video_card_row_fallback", ".ovui-table-row"),
        ]
        for selector in row_selectors:
            loc = page.locator(selector)
            if loc.count() > 0:
                first = loc.first
                try:
                    id_text = first.locator(_sel("material_page", "video_id", ".video-id")).first.inner_text(timeout=2000).strip()
                    if id_text:
                        return id_text
                except Exception as e:
                    _logger.debug(f"获取 .video-id 文本失败: {e}")
                try:
                    return first.inner_text(timeout=2000).strip()[:80]
                except Exception as e:
                    _logger.debug(f"获取 inner_text 失败: {e}")
                    return ""
    except Exception as e:
        _logger.debug(f"get_first_row_signature 失败: {e}")
        return ""
    return ""


def get_active_page_number(page) -> str:
    """获取分页器中当前激活的页码文本。"""
    try:
        active = page.locator(_sel("material_page", "page_active", "li.ovui-page-turner__item--active")).first
        if active.count() > 0:
            return active.inner_text(timeout=2000).strip()
    except Exception as e:
        _logger.debug(f"get_active_page_number 失败: {e}")
    return ""


def go_next_page(page, stop_event=None) -> bool:
    """点击下一页。成功翻页返回 True，否则返回 False。"""
    # 实际页面结构：ul.ovui-page-turner > li.ovui-page-turner__item
    # 下一页按钮 = 包含 .ovui-page-turner__next-icon 的那个 li
    # 禁用状态 = li 上带 .ovui-page-turner__item--disabled
    next_locator = page.locator(
        _sel("material_page", "next_page", "li.ovui-page-turner__item:has(.ovui-page-turner__next-icon)")
    ).first

    if next_locator.count() == 0:
        print("未找到下一页按钮，停止翻页。")
        return False

    try:
        class_attr = next_locator.get_attribute("class") or ""
        disabled_class = _sel("material_page", "next_page_disabled_class", "ovui-page-turner__item--disabled")
        if disabled_class in class_attr:
            print("下一页按钮已禁用，已是最后一页。")
            return False
    except Exception as e:
        _logger.debug(f"检查下一页按钮禁用状态失败: {e}")

    before_active = get_active_page_number(page)
    before_signature = get_first_row_signature(page)

    try:
        next_locator.scroll_into_view_if_needed(timeout=2000)
    except Exception as e:
        _logger.debug(f"scroll_into_view_if_needed 失败: {e}")

    try:
        next_locator.click(timeout=3000)
    except Exception as e:
        print(f"点击下一页失败: {e}")
        return False

    # 等待翻页完成：active 页码变化 或 首行签名变化
    for _ in range(30):
        check_stop(stop_event)
        sleep_ms(page, 500, stop_event)
        after_active = get_active_page_number(page)
        after_signature = get_first_row_signature(page)

        active_changed = bool(after_active) and after_active != before_active
        signature_changed = bool(after_signature) and after_signature != before_signature

        if active_changed or signature_changed:
            wait_table_loaded(page, stop_event)
            sleep_ms(page, 500, stop_event)
            return True

    print("翻页后内容未发生变化，可能已是最后一页。")
    return False


def read_drama_names():
    print("请输入剧名，一行一个，输完后直接回车空行结束：")
    names = []

    while True:
        line = input().strip()
        if not line:
            break
        if line not in names:
            names.append(line)

    return names


def save_all_results(results):
    py_dir = Path(__file__).resolve().parent
    output_name = "批量抓取结果.txt"
    output_path = py_dir / output_name

    # 排序规则：
    # 1. 集数不少于6个的排前面，不足6个的排后面
    # 2. 同组内按集数数量从多到少
    sorted_results = sorted(
        results,
        key=lambda x: (len(x["numbers"]) < 6, -len(x["numbers"]))
    )

    all_lines = []
    for item in sorted_results:
        line = f'{item["drama_name"]} {" ".join(item["numbers"])}'.strip()
        all_lines.append(line)

    content = "\n".join(all_lines)
    output_path.write_text(content, encoding="utf-8")

    print("全部抓取完成。")
    print(f"结果文件: {output_path}")
    print("写入内容：")
    print(content)


def main():
    drama_names = read_drama_names()
    if not drama_names:
        print("没有输入剧名。")
        return

    results = []

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        page = get_target_page(browser)
        # bring_to_front 已移除：force=True 点击不依赖窗口焦点，弹前台会干扰用户
        print(f"已连接页面: {page.url}")
        print(f"共 {len(drama_names)} 个剧名，开始循环执行...")

        for index, drama_name in enumerate(drama_names, start=1):
            try:
                print("\n" + "=" * 60)
                print(f"正在处理第 {index}/{len(drama_names)} 个剧名: {drama_name}")

                clear_and_search(page, drama_name)

                all_items = []
                max_pages = 50  # 安全上限，防止意外死循环
                page_index = 1

                while page_index <= max_pages:
                    print(f"正在抓取第 {page_index} 页...")
                    page_items = collect_from_current_page(page, drama_name)
                    all_items.extend(page_items)

                    if not go_next_page(page):
                        print(f"已抓取 {page_index} 页，结束翻页。")
                        break

                    page_index += 1

                all_numbers = filter_items(all_items, min_cost=1000, min_count=6)

                results.append({
                    "drama_name": drama_name,
                    "numbers": all_numbers
                })

                line = f"{drama_name} {' '.join(all_numbers)}".strip()
                print(f"本剧结果: {line}")

            except Exception as e:
                print(f"剧名【{drama_name}】处理失败: {e}")
                results.append({
                    "drama_name": drama_name,
                    "numbers": []
                })
                continue

        browser.close()

    save_all_results(results)


if __name__ == "__main__":
    main()