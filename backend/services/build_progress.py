"""搭建进度持久化：支持断点续传"""
import json
import logging
from pathlib import Path
from datetime import datetime
from backend.utils.file_utils import save_json_atomic, load_json_safe

_logger = logging.getLogger(__name__)

# 进度文件路径
import sys
if getattr(sys, "frozen", False):
    _BASE = Path(sys.executable).resolve().parent
else:
    # 非打包运行：本文件在 backend/services/，向上三级到项目根目录
    _BASE = Path(__file__).resolve().parent.parent.parent

PROGRESS_FILE = _BASE / "build_progress.json"


def save_progress(task_id: str, profile_key: str, total_accounts: list,
                  completed: list, failed: list, pending: list,
                  extra: dict = None):
    """保存搭建进度"""
    data = {
        "task_id": task_id,
        "profile": profile_key,
        "total_accounts": total_accounts,
        "completed": completed,
        "failed": failed,
        "pending": pending,
        "updated_at": datetime.now().isoformat(),
        "extra": extra or {},
    }
    save_json_atomic(PROGRESS_FILE, data)
    _logger.debug(f"进度已保存: {len(completed)}/{len(total_accounts)} 完成")


def load_progress() -> dict | None:
    """加载未完成的进度，无则返回 None"""
    data = load_json_safe(PROGRESS_FILE, default=None)
    if data is None:
        return None
    # 检查是否有未完成的
    pending = data.get("pending", [])
    if not pending:
        return None  # 已全部完成
    return data


def clear_progress():
    """清除进度文件（搭建完成或用户选择忽略时）"""
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
        _logger.info("进度文件已清除")


def create_task_id(profile_key: str) -> str:
    """生成任务ID"""
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    return f"build-{profile_key}-{ts}"
