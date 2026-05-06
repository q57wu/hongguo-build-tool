"""
backend/core/config_io.py
配置/记录文件 I/O 函数。
使用 file_utils.save_json_atomic / load_json_safe。
"""
import re
import json
from datetime import datetime
from pathlib import Path

from backend.core.constants import (
    APP_DIR,
    ALL_PROFILES,
    PROFILES,
    CONFIG_FILE,
    BUILD_RECORD_FILE,
    MATERIAL_HISTORY_FILE,
    PROFILE_EDITABLE_FIELDS,
)
from backend.utils.file_utils import save_json_atomic, load_json_safe


# ═══════════════════════════════════════════════════════════════
#  内置配置默认值
# ═══════════════════════════════════════════════════════════════
def _profile_defaults(key: str) -> dict:
    p = ALL_PROFILES[key]
    return {
        "strategy": p["strategy"],
        "material_account_id": p["material_account_id"],
        "audience_keyword": p["audience_keyword"],
        "monitor_btn_text": p["monitor_btn_text"],
        "name_prefix": p["name_prefix"],
        "wait_scale": p["wait_scale"],
        "groups": [],
    }


def _default_config() -> dict:
    return {
        "common": {
            "cdp_endpoint": "http://localhost:9222",
            "chrome_path": "",
            "download_dir": "",
            "operator_name": "",
            "drama_titles": [],
        },
        "profiles": {key: _profile_defaults(key) for key in ALL_PROFILES},
    }


def _empty_drama() -> dict:
    return {"name": "", "click": "", "show": "", "video": "", "material_ids": []}


def _empty_group() -> dict:
    return {"account_ids": [], "dramas": [_empty_drama()]}


# ═══════════════════════════════════════════════════════════════
#  config.json 读写
# ═══════════════════════════════════════════════════════════════
def load_config() -> dict:
    """读取 config.json，缺失字段用默认值兜底。"""
    cfg = _default_config()
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            import logging as _logging
            _logging.getLogger(__name__).warning(f"config.json 解析失败，使用默认配置: {e}")
            data = {}
        if isinstance(data, dict):
            common = data.get("common") or {}
            if isinstance(common, dict):
                if isinstance(common.get("cdp_endpoint"), str):
                    cfg["common"]["cdp_endpoint"] = common.get("cdp_endpoint")
                # 字符串类型的公共配置字段直通
                for _str_key in ("chrome_path", "download_dir", "operator_name"):
                    if isinstance(common.get(_str_key), str):
                        cfg["common"][_str_key] = common[_str_key]
                titles = common.get("drama_titles") or []
                if isinstance(titles, str):
                    titles = [x.strip() for x in titles.splitlines() if x.strip()]
                if isinstance(titles, list):
                    seen_titles = set()
                    norm_titles = []
                    for title in titles:
                        title = str(title).strip()
                        key = re.sub(r"\W+", "", title, flags=re.UNICODE).lower()
                        if title and key and key not in seen_titles:
                            seen_titles.add(key)
                            norm_titles.append(title)
                    cfg["common"]["drama_titles"] = norm_titles
            profiles = data.get("profiles") or {}
            if isinstance(profiles, dict):
                for key in ALL_PROFILES:
                    src = profiles.get(key) or {}
                    if not isinstance(src, dict):
                        continue
                    dst = cfg["profiles"][key]
                    for f in PROFILE_EDITABLE_FIELDS:
                        if f in src and src[f] not in (None, ""):
                            dst[f] = src[f]
                    groups = src.get("groups")
                    if isinstance(groups, list):
                        norm_groups = []
                        for g in groups:
                            if not isinstance(g, dict):
                                continue
                            acc = g.get("account_ids") or []
                            if isinstance(acc, str):
                                acc = [x.strip() for x in re.split(r"[\s,]+", acc) if x.strip()]
                            acc = [str(x).strip() for x in acc if str(x).strip()]
                            dramas = g.get("dramas") or []
                            norm_dramas = []
                            if isinstance(dramas, list):
                                for d in dramas:
                                    if not isinstance(d, dict):
                                        continue
                                    mids = d.get("material_ids") or []
                                    if isinstance(mids, str):
                                        mids = [x.strip() for x in re.split(r"[\s,]+", mids) if x.strip()]
                                    mids = [str(x).strip() for x in mids if str(x).strip()]
                                    norm_dramas.append({
                                        "name": str(d.get("name", "")).strip(),
                                        "click": str(d.get("click", "")).strip(),
                                        "show": str(d.get("show", "")).strip(),
                                        "video": str(d.get("video", "")).strip(),
                                        "material_ids": mids,
                                    })
                            norm_groups.append({
                                "id": g["id"] if "id" in g else None,  # 保留稳定 id，None 表示旧数据待补全
                                "account_ids": acc,
                                "dramas": norm_dramas,
                                "group_name": str(g.get("group_name", "")).strip(),
                                "click_url": str(g.get("click_url", "")).strip(),
                                "show_url": str(g.get("show_url", "")).strip(),
                                "play_url": str(g.get("play_url", "")).strip(),
                            })
                        # 兼容旧数据：为缺少 id 的 group 按数组顺序补 id
                        existing_ids = [g["id"] for g in norm_groups if g.get("id") is not None]
                        next_id = (max(existing_ids) + 1) if existing_ids else 1
                        for g in norm_groups:
                            if g["id"] is None:
                                g["id"] = next_id
                                next_id += 1
                        dst["groups"] = norm_groups
    try:
        wait_scale = cfg["profiles"][next(iter(PROFILES))]["wait_scale"]
        float(wait_scale)
    except Exception:
        pass
    return cfg


def save_config(cfg: dict) -> None:
    """保存 config.json（使用原子写入 + 自动备份）。"""
    save_json_atomic(CONFIG_FILE, cfg)


# ═══════════════════════════════════════════════════════════════
#  build_records.json 读写
# ═══════════════════════════════════════════════════════════════
def load_build_records() -> dict:
    data = load_json_safe(BUILD_RECORD_FILE, default={})
    if isinstance(data, dict):
        return data
    return {}


def save_build_records(records: dict) -> None:
    save_json_atomic(BUILD_RECORD_FILE, records)


def record_build_success(account_count: int, project_count: int, session_id: str = "") -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    records = load_build_records()
    day = records.get(today) or {"accounts": 0, "projects": 0}
    # session dedupe：同一次 run_build 调用只计一次，防止中途停止重启后重复累加
    if session_id:
        day_sessions = day.get("sessions", [])
        if session_id in day_sessions:
            return  # 同 session 已记录，忽略
        day_sessions.append(session_id)
        if len(day_sessions) > 50:
            day_sessions = day_sessions[-50:]
        day["sessions"] = day_sessions
    day["accounts"] = day.get("accounts", 0) + account_count
    day["projects"] = day.get("projects", 0) + project_count
    records[today] = day
    save_build_records(records)


# ═══════════════════════════════════════════════════════════════
#  material_history.json 读写
# ═══════════════════════════════════════════════════════════════
def load_material_history() -> list:
    data = load_json_safe(MATERIAL_HISTORY_FILE, default=[])
    if isinstance(data, list):
        return data
    return []


def save_material_history(history: list) -> None:
    save_json_atomic(MATERIAL_HISTORY_FILE, history)


def add_material_history(names: list[str]) -> None:
    if not names:
        return
    history = load_material_history()
    existing = {r["name"] for r in history}
    date_tag = datetime.now().strftime("%m%d")
    for name in names:
        if name and name not in existing:
            history.insert(0, {"date": date_tag, "name": name})
            existing.add(name)
    save_material_history(history)


def get_used_material_names() -> set:
    return {r["name"] for r in load_material_history() if r.get("name")}


# ═══════════════════════════════════════════════════════════════
#  IDS.txt → config 迁移
# ═══════════════════════════════════════════════════════════════
def migrate_ids_txt_to_config() -> bool:
    from backend.core.data_parsers import _parse_ids_txt_groups, _parse_incentive_ids_txt
    cfg = load_config()
    changed = False
    for key, p in ALL_PROFILES.items():
        prof = cfg["profiles"].get(key)
        if not prof:
            continue
        if prof.get("groups"):
            continue
        is_incentive = p.get("build_mode") == "incentive"
        if is_incentive:
            inc_groups = _parse_incentive_ids_txt(p["ids_file"])
            if not inc_groups:
                continue
            new_groups = []
            for g in inc_groups:
                new_groups.append({
                    "account_ids": g["account_ids"],
                    "group_name": g["group_name"],
                    "click_url": g.get("click_url", ""),
                    "show_url": g.get("show_url", ""),
                    "play_url": g.get("play_url", ""),
                    "dramas": [],
                })
            prof["groups"] = new_groups
        else:
            groups = _parse_ids_txt_groups(p["ids_file"])
            if not groups:
                continue
            new_groups = []
            for ids, dramas in groups:
                new_groups.append({
                    "account_ids": [str(x) for x in ids],
                    "dramas": [
                        {
                            "name": d.get("name", ""),
                            "click": d.get("click", ""),
                            "show": d.get("show", ""),
                            "video": d.get("video", ""),
                            "material_ids": list(d.get("material_ids", [])),
                        }
                        for d in dramas
                    ],
                })
            prof["groups"] = new_groups
        changed = True
    if changed:
        save_config(cfg)
    return changed


# ═══════════════════════════════════════════════════════════════
#  数据目录初始化
# ═══════════════════════════════════════════════════════════════
IDS_TEMPLATE = """\
# ════════════════════════════════════════════════════════════
# ids.txt 数据模板
# ════════════════════════════════════════════════════════════
# 使用说明：
#   1. 顶部依次填写媒体账户ID（每行一个纯数字）
#   2. 空行后开始第一组数据：
#        - 剧名
#        - 点击监测链接（含 action_type=click 或 /display/）
#        - 展示监测链接（含 impression 或 action_type=view）
#        - 视频播放监测链接（含 action_type=effective_play）
#        - 素材ID（多个用空格分隔）
#   3. 多组数据之间用 === 分隔
#   4. 以 # 开头的行为注释，会被忽略
# ════════════════════════════════════════════════════════════

# ===== 在下方填写媒体账户ID（每行一个）=====
1234567890123456
1234567890123457

# ===== 第 1 组数据 =====
示例剧名

https://example.com/click?action_type=click&xxx

https://example.com/show?action_type=view&xxx

https://example.com/play?action_type=effective_play&xxx

7000000000001 7000000000002 7000000000003

===

# ===== 第 2 组数据（可继续添加，删除示例后保留格式即可）=====
"""


def init_data_dirs():
    """首次运行时自动创建 4 个方向的文件夹和 ids.txt 模板。

    返回创建的文件列表，便于在 GUI 中提示用户。
    """
    created = []
    for key, cfg in ALL_PROFILES.items():
        ids_file: Path = cfg["ids_file"]
        log_dir: Path = cfg["log_dir"]
        ids_file.parent.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)
        if not ids_file.exists():
            ids_file.write_text(IDS_TEMPLATE, encoding="utf-8")
            created.append(str(ids_file))
    return created
