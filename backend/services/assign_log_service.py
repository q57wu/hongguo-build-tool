"""
链接分配操作日志服务 — 记录每次"写入配置"时的账户分配详情
JSON 文件存储，按日期查询
"""
import json
import os
import threading
from datetime import datetime
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_LOG_FILE = _LOG_DIR / "assign_logs.json"
_lock = threading.Lock()
_MAX_RECORDS = 500  # 最多保留500条记录


def _load() -> list:
    if not _LOG_FILE.exists():
        return []
    try:
        return json.loads(_LOG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []


def _save(records: list):
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _LOG_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(_LOG_FILE))


def add_assign_log(profile_key: str, assign_type: str, groups: list, source: str = ""):
    """
    记录一次链接分配操作。

    Args:
        profile_key: 配置键（如 "安卓-每留"）
        assign_type: "normal" 或 "incentive"
        groups: 分配的组数据列表，每组包含:
            - account_ids: 账户ID列表
            - dramas: 剧名列表（普通模式）
            - group_name: 组名（激励模式）
            - click/show/video: 监测链接（可选）
            - material_ids: 素材ID列表（可选）
        source: 来源说明（可选）
    """
    now = datetime.now()

    # 汇总信息
    total_accounts = 0
    all_account_ids = []
    group_summaries = []

    for i, g in enumerate(groups):
        aids = g.get("account_ids", [])
        total_accounts += len(aids)
        all_account_ids.extend(aids)

        summary = {
            "group_index": i + 1,
            "account_ids": aids,
            "account_count": len(aids),
        }

        # 普通模式：记录剧名
        if assign_type == "normal":
            dramas = g.get("dramas", [])
            summary["drama_names"] = [d.get("name", d) if isinstance(d, dict) else str(d) for d in dramas]
            summary["drama_count"] = len(dramas)

        # 激励模式：记录组名和链接
        if assign_type == "incentive":
            summary["group_name"] = g.get("group_name", g.get("label", f"组{i+1}"))
            for key in ("click_url", "show_url", "play_url"):
                if g.get(key):
                    summary[key] = g[key]
            if g.get("material_ids"):
                summary["material_ids"] = g["material_ids"]

        group_summaries.append(summary)

    record = {
        "id": f"assign-{profile_key}-{now.strftime('%Y%m%d-%H%M%S')}",
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "profile_key": profile_key,
        "type": assign_type,
        "group_count": len(group_summaries),
        "total_accounts": total_accounts,
        "all_account_ids": all_account_ids,
        "groups": group_summaries,
        "source": source,
    }

    with _lock:
        records = _load()
        records.insert(0, record)  # 最新的在前面
        if len(records) > _MAX_RECORDS:
            records = records[:_MAX_RECORDS]
        _save(records)

    return record


def get_assign_logs(date: str = "", profile_key: str = "") -> list:
    """
    查询分配日志。

    Args:
        date: 按日期筛选（格式 YYYY-MM-DD），空则返回全部
        profile_key: 按配置筛选，空则返回全部

    Returns:
        日志列表（最新在前）
    """
    with _lock:
        records = _load()

    if date:
        records = [r for r in records if r.get("date") == date]
    if profile_key:
        records = [r for r in records if r.get("profile_key") == profile_key]

    return records


def get_assign_log_dates() -> list:
    """获取所有有日志的日期列表（最新在前）"""
    with _lock:
        records = _load()
    dates = sorted(set(r.get("date", "") for r in records if r.get("date")), reverse=True)
    return dates
