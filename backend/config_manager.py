"""
配置管理：直接调用 backend.core.config_io。
"""
import sys
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)

_gui_dir = Path(__file__).resolve().parent.parent
if str(_gui_dir) not in sys.path:
    sys.path.insert(0, str(_gui_dir))

# 软件运行目录：打包后是 exe 所在目录，否则是 gui 目录
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = _gui_dir
CONFIG_FILE = BASE_DIR / "config.json"
BUILD_RECORD_FILE = BASE_DIR / "build_records.json"
MATERIAL_HISTORY_FILE = BASE_DIR / "material_history.json"

# 路径有效性日志
for _name, _path in [
    ("CONFIG_FILE", CONFIG_FILE),
    ("BUILD_RECORD_FILE", BUILD_RECORD_FILE),
    ("MATERIAL_HISTORY_FILE", MATERIAL_HISTORY_FILE),
]:
    if not _path.parent.exists():
        _logger.warning(f"config_manager: {_name} 父目录不存在，可能导致文件写到错误位置: {_path}")
    else:
        _logger.debug(f"config_manager: {_name} -> {_path}")

# 直接 re-export，外部 import 路径不用改
from backend.core.config_io import (  # noqa: E402
    load_config,
    save_config,
    load_build_records,
    save_build_records,
    load_material_history,
    save_material_history,
)
