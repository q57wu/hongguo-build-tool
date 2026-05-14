"""选择器配置加载器"""
import json
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)
_SELECTOR_DIR = Path(__file__).resolve().parent
_cache = {}


def load_selectors(platform: str = "oceanengine") -> dict:
    """加载指定平台的选择器配置"""
    if platform in _cache:
        return _cache[platform]

    path = _SELECTOR_DIR / f"{platform}.json"
    if not path.exists():
        _logger.error(f"选择器配置不存在: {path}")
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not data:
            _logger.warning(f"选择器配置为空 dict: {path}")
            return {}
        _cache[platform] = data
        _logger.info(f"已加载选择器配置: {platform} (版本: {data.get('version', 'unknown')})")
        return data
    except Exception as e:
        _logger.error(f"加载选择器配置失败: {e}")
        return {}


def get_selector(section: str, key: str, platform: str = "oceanengine") -> str:
    """获取单个选择器"""
    data = load_selectors(platform)
    return data.get(section, {}).get(key, "")


def reload_selectors(platform: str = "oceanengine"):
    """重新加载选择器（热更新）"""
    if platform in _cache:
        del _cache[platform]
    return load_selectors(platform)


def get_selectors(platform: str = "oceanengine") -> dict:
    """获取完整选择器配置（load_selectors 的别名，供内部统一调用）"""
    return load_selectors(platform)


def resolve_selector(page_or_locator, key, group=None, timeout=3000, platform="oceanengine"):
    """自动降级选择器：依次尝试 primary → fallback1 → fallback2 → fallback3

    Args:
        page_or_locator: Playwright Page 或 Locator 对象
        key: 选择器基础名（如 'search_button'）
        group: 选择器分组（如 'material_page'），None 时搜索所有分组
        timeout: 每个选择器的等待超时(ms)
        platform: 平台名称，默认 'oceanengine'

    Returns:
        第一个匹配到可见元素的 Locator，或 None
    """
    selectors = get_selectors(platform)

    # 去掉顶层元数据字段，只保留分组 dict
    groups_only = {k: v for k, v in selectors.items() if isinstance(v, dict)}

    if group and group in groups_only:
        src = groups_only[group]
    else:
        src = {}
        for g in groups_only.values():
            src.update(g)

    # 按优先级收集候选选择器：_primary > 无后缀 > _fallback1 > _fallback2 > _fallback3
    # 同时兼容 JSON 中 _fallback（无数字）的写法
    suffixes = ["_primary", "", "_fallback1", "_fallback2", "_fallback3", "_fallback"]
    candidates = []
    seen = set()
    for suffix in suffixes:
        sel_key = f"{key}{suffix}"
        if sel_key in src and src[sel_key] not in seen:
            candidates.append(src[sel_key])
            seen.add(src[sel_key])

    if not candidates:
        _logger.warning(f"resolve_selector: 未找到任何候选选择器 key='{key}' group='{group}'")
        return None

    for selector in candidates:
        try:
            loc = page_or_locator.locator(selector)
            loc.first.wait_for(state="visible", timeout=timeout)
            _logger.debug(f"resolve_selector: 命中选择器 '{selector}' (key='{key}')")
            return loc
        except Exception:
            continue

    _logger.warning(f"resolve_selector: 所有候选选择器均不可见 key='{key}' candidates={candidates}")
    return None
