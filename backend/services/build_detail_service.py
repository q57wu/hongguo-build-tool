"""搭建详情记录：逐账户成功/失败"""
import json
import logging
from datetime import datetime
from pathlib import Path
from backend.utils.file_utils import save_json_atomic, load_json_safe

_logger = logging.getLogger(__name__)

import sys
if getattr(sys, "frozen", False):
    _BASE = Path(sys.executable).resolve().parent
else:
    _BASE = Path(__file__).resolve().parent.parent.parent

DETAIL_FILE = _BASE / "build_details.json"


def _load_details() -> list:
    data = load_json_safe(DETAIL_FILE, default=[])
    return data if isinstance(data, list) else []


def _save_details(details: list):
    # 最多保留最近 500 条
    if len(details) > 500:
        details = details[-500:]
    save_json_atomic(DETAIL_FILE, details)


def add_build_detail(session_id: str, profile_key: str, account_id: str,
                     status: str, drama_name: str = "", message: str = ""):
    """添加一条搭建详情
    status: "success" / "failed" / "skipped"
    """
    details = _load_details()
    details.append({
        "session_id": session_id,
        "profile": profile_key,
        "account_id": account_id,
        "drama_name": drama_name,
        "status": status,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    })
    _save_details(details)


def get_details_by_date(date_str: str) -> list:
    """获取指定日期的详情列表"""
    details = _load_details()
    return [d for d in details if d.get("timestamp", "").startswith(date_str)]


def get_details_by_session(session_id: str) -> list:
    """获取指定 session 的详情列表"""
    details = _load_details()
    return [d for d in details if d.get("session_id") == session_id]


def get_all_details() -> list:
    """获取所有详情（前端分页）"""
    return _load_details()


def export_csv(date_str: str = "") -> str:
    """导出 CSV 字符串"""
    details = get_details_by_date(date_str) if date_str else _load_details()
    lines = ["时间,方向,账户ID,剧名,状态,备注"]
    for d in details:
        ts = d.get("timestamp", "")[:19].replace("T", " ")
        profile = d.get("profile", "")
        acc = d.get("account_id", "")
        drama = d.get("drama_name", "").replace(",", "，")
        status_map = {"success": "成功", "failed": "失败", "skipped": "跳过"}
        status = status_map.get(d.get("status", ""), d.get("status", ""))
        msg = d.get("message", "").replace(",", "，").replace("\n", " ")
        lines.append(f"{ts},{profile},{acc},{drama},{status},{msg}")
    return "\n".join(lines)
