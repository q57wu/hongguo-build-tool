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
