"""
每日任务持久化管理服务
数据存储在项目根目录的 daily_tasks.json 中，按日期分组管理任务。
"""

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

DATA_FILE = Path(__file__).resolve().parents[2] / "daily_tasks.json"


def _read_data() -> dict:
    """读取 JSON 数据文件，不存在则返回空 dict"""
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _write_data(data: dict):
    """将数据写入 JSON 文件"""
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _short_id() -> str:
    """生成 8 位短 UUID"""
    return uuid.uuid4().hex[:8]


# ──────────────────────────── 公开接口 ────────────────────────────


def get_tasks(date: str) -> list:
    """
    获取某天的任务列表。
    :param date: 日期字符串，格式 YYYY-MM-DD
    :return: 任务列表，无数据时返回空列表
    """
    data = _read_data()
    return data.get(date, [])


def save_tasks(date: str, tasks: list):
    """
    保存（覆盖）某天的任务列表。
    :param date: 日期字符串，格式 YYYY-MM-DD
    :param tasks: 完整的任务列表
    """
    data = _read_data()
    data[date] = tasks
    _write_data(data)


def add_tasks(date: str, tasks: list):
    """
    向某天追加任务。
    :param date: 日期字符串，格式 YYYY-MM-DD
    :param tasks: 要追加的任务列表（无需包含 id/created_at 等，会自动补全）
    """
    data = _read_data()
    existing = data.get(date, [])
    now = datetime.now().isoformat()
    for t in tasks:
        task = {
            "id": t.get("id") or _short_id(),
            "person": t.get("person", ""),
            "title": t.get("title", ""),
            "detail": t.get("detail", ""),
            "done": t.get("done", False),
            "created_at": t.get("created_at") or now,
            "done_at": t.get("done_at"),
            "params": t.get("params", {}),
            "profile_key": t.get("profile_key", ""),
            "build_count": t.get("build_count", 0),
            "build_total": t.get("build_total", 0),
        }
        existing.append(task)
    data[date] = existing
    _write_data(data)


def toggle_task(date: str, task_id: str) -> bool:
    """
    切换某任务的完成状态。
    :param date: 日期字符串
    :param task_id: 任务 ID
    :return: 切换后的 done 状态；未找到任务时返回 False
    """
    data = _read_data()
    tasks = data.get(date, [])
    for task in tasks:
        if task["id"] == task_id:
            task["done"] = not task["done"]
            task["done_at"] = datetime.now().isoformat() if task["done"] else None
            _write_data(data)
            return task["done"]
    return False


def delete_task(date: str, task_id: str):
    """
    删除某天的指定任务。
    :param date: 日期字符串
    :param task_id: 任务 ID
    """
    data = _read_data()
    tasks = data.get(date, [])
    data[date] = [t for t in tasks if t["id"] != task_id]
    _write_data(data)


def increment_build_count(date: str, profile_key: str) -> dict:
    """
    搭建成功一部剧时，给对应 profile 的任务 build_count +1。
    :param date: 日期字符串
    :param profile_key: 搭建配置 key，如 "安卓-每留"
    :return: {"task_id": ..., "build_count": ...} 或空 dict
    """
    data = _read_data()
    tasks = data.get(date, [])
    for task in tasks:
        if task.get("profile_key") == profile_key and not task.get("done"):
            task["build_count"] = task.get("build_count", 0) + 1
            # 如果有 drama_count 参数且已达到目标，自动标记完成
            params = task.get("params", {})
            target = params.get("drama_count", 0)
            if target > 0 and task["build_count"] >= target:
                task["done"] = True
                task["done_at"] = datetime.now().isoformat()
            _write_data(data)
            return {"task_id": task["id"], "build_count": task["build_count"]}
    return {}


def _match_profile(title: str) -> str:
    """
    根据任务标题自动匹配软件的搭建 profile key。

    映射规则：
    - "安卓-短剧-每留" / "安卓-每留" → "安卓-每留"
    - "安卓-短剧-七留" → "安卓-七留"
    - "IOS-短剧-每留" / "I0S-短剧-每留" → "IOS-每留"
    - "IOS-短剧-七留" → "IOS-七留"
    - "安卓-激励-每留" → "安卓-激励每留"
    - "安卓-激励-七留" → "安卓-激励七留"

    :return: profile key 或空字符串（无法匹配时）
    """
    t = title.upper().replace("0", "O")  # I0S → IOS 兼容

    # 判断平台
    if "IOS" in t:
        platform = "IOS"
    elif "安卓" in title:
        platform = "安卓"
    else:
        return ""

    # 判断激励
    is_incentive = "激励" in title

    # 判断留存
    if "七留" in title:
        retention = "七留"
    elif "每留" in title:
        retention = "每留"
    else:
        return ""

    if is_incentive:
        return f"{platform}-激励{retention}"
    return f"{platform}-{retention}"


def _extract_params(text: str) -> dict:
    """
    从任务标题+详情文本中提取结构化运营参数。

    示例输入: "安卓-短剧-每留每天12部剧目测试，每3部为1组，对应1组5个账户"
    示例输出: {"drama_count": 12, "dramas_per_group": 3, "accounts_per_group": 5}
    """
    params = {}

    # 剧数量: "12部剧" / "12部" / "12 部剧"
    m = re.search(r'(\d+)\s*部(?:剧|短剧)?', text)
    if m:
        params['drama_count'] = int(m.group(1))

    # 每组剧数: "每3部为1组" / "3部一组" / "每3部1组"
    m = re.search(r'(?:每)?(\d+)\s*部\s*(?:为|一|1)?\s*(?:1|一)?\s*组', text)
    if m:
        params['dramas_per_group'] = int(m.group(1))

    # 每组账户数: "1组5个账户" / "一组5账户" / "每组5个账户" / "对应1组5个账户"
    m = re.search(r'(?:1|一|每)\s*组\s*(\d+)\s*(?:个)?账户', text)
    if m:
        params['accounts_per_group'] = int(m.group(1))

    # 素材数量: "6条素材" / "素材6条"
    m = re.search(r'(\d+)\s*条素材|素材\s*(\d+)\s*条', text)
    if m:
        params['material_count'] = int(m.group(1) or m.group(2))

    # 每条素材对应广告数: "1条素材2个广告" / "每条素材对应2个广告"
    m = re.search(r'(?:1|一|每)\s*条素材\s*(?:对应)?\s*(\d+)\s*(?:个)?广告', text)
    if m:
        params['ads_per_material'] = int(m.group(1))

    # 测试天数: "测试3天" / "跑3天"
    m = re.search(r'(?:测试|跑)\s*(\d+)\s*天', text)
    if m:
        params['test_days'] = int(m.group(1))

    # 每天预算: "每天预算500" / "日预算500"
    m = re.search(r'(?:每天|日)\s*预算\s*(\d+)', text)
    if m:
        params['daily_budget'] = int(m.group(1))

    return params


def parse_raw_input(raw_text: str) -> list:
    """
    解析用户输入的原始文本为结构化任务列表。

    支持的格式示例：
    ────────────────────────────
    吴琪
    1) 安卓-短剧-每留
    对应基建CID: xxx
    2) 安卓-短剧-次留
    对应基建CID: yyy
    3) iOS-短剧-每留
    详细说明...
    4) iOS-短剧-次留

    备注: 所有任务需在下午 5 点前完成
    ────────────────────────────

    解析规则：
    - 第一行（非空、非编号、非"备注"）视为当前人名
    - 遇到新的人名行时切换人名
    - 编号行（如 1) 2) 3)）的内容为任务标题
    - 编号之间的非编号行为上一个任务的详细描述
    - "备注:" 开头的内容作为所有任务的公共备注，追加到每个任务的 detail 中
    - 自动根据标题匹配软件的搭建 profile（存入 profile_key 字段）

    :param raw_text: 原始文本
    :return: 结构化任务列表
    """
    if not raw_text or not raw_text.strip():
        return []

    lines = raw_text.strip().splitlines()
    tasks: list[dict] = []
    current_person: str = ""
    current_task: Optional[dict] = None
    global_note: str = ""
    in_note = False

    # 编号模式: 1) 2) 3)  或  1. 2. 3.  或  1、2、3、
    num_pattern = re.compile(r"^\s*\d+[)）.、]\s*(.+)")
    # 备注模式
    note_pattern = re.compile(r"^\s*备注[:：]\s*(.*)", re.IGNORECASE)
    # 人名行判定：非空、非编号、非备注、长度 ≤ 10（中文人名通常很短）
    def is_person_line(line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        if num_pattern.match(stripped):
            return False
        if note_pattern.match(stripped):
            return False
        # 人名通常 ≤ 10 字符，且不含常见标点
        if len(stripped) <= 10 and not re.search(r"[,，;；。!！?？:\-]", stripped):
            return True
        return False

    for line in lines:
        stripped = line.strip()

        # 空行跳过
        if not stripped:
            continue

        # 备注段落
        note_match = note_pattern.match(stripped)
        if note_match:
            in_note = True
            global_note = note_match.group(1).strip()
            continue

        if in_note:
            # 备注可能跨行
            global_note += "\n" + stripped
            continue

        # 编号行 → 新任务
        num_match = num_pattern.match(stripped)
        if num_match:
            # 保存上一个任务
            if current_task is not None:
                tasks.append(current_task)
            title = num_match.group(1).strip()
            now = datetime.now().isoformat()
            current_task = {
                "id": _short_id(),
                "person": current_person,
                "title": title,
                "detail": "",
                "done": False,
                "created_at": now,
                "done_at": None,
                "profile_key": _match_profile(title),
                "build_count": 0,
                "build_total": 0,
            }
            continue

        # 如果还没有当前任务，判断是否为人名行
        if current_task is None:
            if is_person_line(stripped):
                current_person = stripped
            continue

        # 否则是上一个任务的详细描述
        if current_task["detail"]:
            current_task["detail"] += "\n" + stripped
        else:
            current_task["detail"] = stripped

    # 收尾：保存最后一个任务
    if current_task is not None:
        tasks.append(current_task)

    # 从标题+详情中提取结构化参数
    for task in tasks:
        combined = task["title"] + " " + task.get("detail", "")
        task["params"] = _extract_params(combined)
        # 将 drama_count 同步到 build_total 方便前端展示
        if task["params"].get("drama_count"):
            task["build_total"] = task["params"]["drama_count"]

    # 将公共备注追加到每个任务的 detail
    if global_note:
        for task in tasks:
            if task["detail"]:
                task["detail"] += "\n备注: " + global_note
            else:
                task["detail"] = "备注: " + global_note

    return tasks
