"""
backend/core/data_parsers.py
纯数据解析函数（无 Playwright 依赖）。
"""
import re
import functools
import logging
from pathlib import Path

from backend.core.constants import (
    APP_DIR,
    RE_MMDD,
    ALL_PROFILES,
)

# ═══════════════════════════════════════════════════════════════
#  数据解析工具
# ═══════════════════════════════════════════════════════════════
def is_separator_line(text: str) -> bool:
    value = (text or "").strip()
    if not value:
        return False
    if re.fullmatch(r"[=═\-—＿_\s]{3,}", value):
        return True
    if re.fullmatch(r"[=═\-—＿_\s]*第\s*\d+\s*组.*[=═\-—＿_\s]*", value):
        return True
    if re.fullmatch(r"[=═\-—＿_\s]*链接分配之后.*[=═\-—＿_\s]*", value):
        return True
    return False


def sanitize_link_text(text: str) -> str:
    value = (text or "").replace("\r", "").replace("\n", "").strip()
    value = value.strip("`'\" ")
    value = re.split(r"\s*(?:={3,}|═{3,})", value, maxsplit=1)[0].strip()
    value = value.strip("`'\" ")
    return value


def normalize_link(text: str) -> str:
    return sanitize_link_text(text)


def classify_link(url: str) -> str:
    u = normalize_link(url).lower()
    if "action_type=effective_play" in u: return "video"
    if "action_type=click" in u: return "click"
    if "action_type=view" in u: return "show"
    if "effective_play" in u: return "video"
    if "/display/" in u: return "click"
    if "impression" in u: return "show"
    return "unknown"


@functools.lru_cache(maxsize=64)
def _compile_sequel_pattern(drama_name: str):
    return re.compile(
        rf"{re.escape(drama_name)}\s*("
        rf"[0-9一二三四五六七八九十]+|"
        rf"第[一二三四五六七八九十]+(部|季)|"
        rf"[二三四五六七八九十]+(部|季)|"
        rf"之)"
    )


def _normalize_material_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _material_name_has_exact_drama_segment(drama_name: str, material_name: str) -> bool:
    drama = _normalize_material_text(drama_name)
    if not drama:
        return False
    stem = Path(material_name or "").stem
    parts = [p for p in re.split(r"[-－—–_＿]+", stem) if p.strip()]
    for part in parts:
        cleaned = re.sub(r"[(\（]\d+[)\）]$", "", part.strip())
        if _normalize_material_text(cleaned) == drama:
            return True
    return False


def is_valid_material_name(drama_name: str, material_name: str) -> bool:
    if not _material_name_has_exact_drama_segment(drama_name, material_name):
        return False
    if _compile_sequel_pattern(drama_name).search(material_name):
        return False
    return True


def extract_mmdd(name: str):
    m = RE_MMDD.search(name or "")
    if not m:
        return None
    return f"{m.group(1)}{m.group(2)}"


def _is_url_line(line: str) -> bool:
    return bool(re.match(r"^`?\s*https?://", (line or "").strip(), re.I))


def _clean_plain_line(line: str) -> str:
    return (line or "").strip().strip("`'\" ")


def _is_material_ids_line(line: str) -> bool:
    parts = (line or "").split()
    return bool(parts) and len(parts) > 1 and all(p.isdigit() for p in parts)


def _parse_single_group(raw_text, logger):
    raw_text = re.sub(r"(?:={3,}|═{3,})", "\n", raw_text or "")
    lines = []
    for line in raw_text.splitlines():
        clean = _clean_plain_line(line)
        if not clean or is_separator_line(clean):
            continue
        lines.append(clean)
    if not lines:
        return [], []

    ids = []
    idx = 0
    while idx < len(lines):
        clean = _clean_plain_line(lines[idx])
        if clean.isdigit():
            ids.append(clean)
            idx += 1
            continue
        break

    drama_list = []
    current = None

    def log_info(msg):
        if logger:
            logger.info(msg)

    def log_warning(msg):
        if logger:
            logger.warning(msg)

    def flush_current():
        nonlocal current
        if not current:
            return
        missing_types = [k for k in ("click", "show", "video") if not current[k]]
        if missing_types:
            log_warning(f"⚠️ 链接类型缺失: {current['name']} | 缺少: {', '.join(missing_types)}")
        log_info(f"📘 剧名解析: {current['name']}")
        drama_list.append(current)
        current = None

    while idx < len(lines):
        clean = _clean_plain_line(lines[idx])
        if not clean or is_separator_line(clean):
            idx += 1
            continue

        if _is_url_line(clean):
            if not current:
                log_warning(f"⚠️ 遇到无剧名链接，已跳过: {sanitize_link_text(clean)[:80]}")
                idx += 1
                continue
            link = sanitize_link_text(clean)
            link_type = classify_link(link)
            if link_type == "unknown":
                log_warning(f"⚠️ 未识别链接类型，已跳过: {link[:80]}")
            elif current[link_type]:
                log_warning(f"⚠️ 重复{link_type}链接: {current['name']}")
            else:
                current[link_type] = link
            idx += 1
            continue

        if current and _is_material_ids_line(clean):
            current["material_ids"] = clean.split()
            log_info(f"📦 {current['name']} 素材ID数量: {len(current['material_ids'])}")
            idx += 1
            continue

        if clean.isdigit():
            if current:
                current["material_ids"].append(clean)
            idx += 1
            continue

        flush_current()
        current = {"name": clean, "click": "", "show": "", "video": "", "material_ids": []}
        idx += 1

    flush_current()
    return ids, drama_list


def read_data(id_file: Path, logger):
    if not id_file.exists():
        raise FileNotFoundError(f"找不到文件: {id_file}")
    raw_text = id_file.read_text(encoding="utf-8")
    # 过滤掉以 # 开头的注释行（保留空行用于段落分隔）
    raw_text = "\n".join(
        line for line in raw_text.splitlines()
        if not line.lstrip().startswith("#")
    )
    chunks = re.split(r'\s*\n\s*={3,}\s*\n\s*', raw_text.strip())
    groups = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk: continue
        ids, dramas = _parse_single_group(chunk, logger)
        if ids or dramas:
            groups.append((ids, dramas))
    total_ids = sum(len(g[0]) for g in groups)
    total_drama = sum(len(g[1]) for g in groups)
    logger.info(f"✅ 读取到 {len(groups)} 组数据，共 {total_ids} 个账号, {total_drama} 部剧")
    return groups


# ═══════════════════════════════════════════════════════════════
#  IDS.txt 解析
# ═══════════════════════════════════════════════════════════════
def _parse_ids_txt_groups(ids_file: Path):
    """解析 ids.txt → [(account_ids, [drama_dict])]。失败则返回空列表。"""
    if not ids_file.exists():
        return []
    try:
        raw_text = ids_file.read_text(encoding="utf-8")
    except Exception:
        return []
    raw_text = "\n".join(
        line for line in raw_text.splitlines()
        if not line.lstrip().startswith("#")
    )
    chunks = re.split(r"(?:═{3,}[^\n]*═{3,}|={3,})", raw_text.strip())
    _silent = logging.getLogger("_silent_migrate")
    _silent.addHandler(logging.NullHandler())
    _silent.propagate = False
    groups = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        ids, dramas = _parse_single_group(chunk, _silent)
        if ids or dramas:
            groups.append((ids, dramas))
    return groups


def _parse_incentive_ids_txt(ids_file: Path):
    if not ids_file.exists():
        return []
    try:
        raw_text = ids_file.read_text(encoding="utf-8")
    except Exception:
        return []
    lines = [l.rstrip() for l in raw_text.splitlines()]
    groups = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not re.match(r"^组\d+", line):
            i += 1
            continue
        group_name = line
        i += 1
        account_ids = []
        while i < len(lines) and lines[i].strip():
            val = lines[i].strip()
            if val.isdigit() and len(val) > 10:
                account_ids.append(val)
            i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        track_urls = []
        while i < len(lines) and lines[i].strip().startswith("http"):
            track_urls.append(lines[i].strip())
            i += 1
        click_url = ""
        show_url = ""
        play_url = ""
        for url in track_urls:
            if "action_type=click" in url:
                click_url = url
            elif "action_type=view" in url:
                show_url = url
            elif "action_type=effective_play" in url:
                play_url = url
        if account_ids:
            groups.append({
                "group_name": group_name,
                "account_ids": account_ids,
                "click_url": click_url,
                "show_url": show_url,
                "play_url": play_url,
            })
    return groups


# ═══════════════════════════════════════════════════════════════
#  配置组清理与处理
# ═══════════════════════════════════════════════════════════════
def sanitize_config_groups(groups):
    cleaned_groups = []
    changed = False
    for group in groups or []:
        ids = [str(x).strip() for x in (group.get("account_ids") or []) if str(x).strip().isdigit()]
        dramas = []
        for d in group.get("dramas") or []:
            name = str(d.get("name") or "").strip()
            if not name or is_separator_line(name):
                changed = True
                continue
            # 严格判断：仅当 name 本身以 http(s):// 开头才视为误入的 URL
            if name.startswith("http://") or name.startswith("https://"):
                _, recovered = _parse_single_group(name, None)
                if recovered:
                    dramas.extend(recovered)
                changed = True
                continue
            item = {
                "name": name.splitlines()[0].strip(),
                "click": sanitize_link_text(d.get("click") or ""),
                "show": sanitize_link_text(d.get("show") or ""),
                "video": sanitize_link_text(d.get("video") or ""),
                "material_ids": [str(x).strip() for x in (d.get("material_ids") or []) if str(x).strip()],
            }
            if item["name"] != name or item["click"] != (d.get("click") or "") or item["show"] != (d.get("show") or "") or item["video"] != (d.get("video") or ""):
                changed = True
            dramas.append(item)
        if ids or dramas:
            entry = {"account_ids": ids, "dramas": dramas}
            for extra_key in ("id", "group_name", "click_url", "show_url", "play_url"):
                if extra_key in group:
                    if extra_key == "id":
                        entry["id"] = group["id"]
                    else:
                        entry[extra_key] = str(group[extra_key]).strip()
            cleaned_groups.append(entry)
    return cleaned_groups, changed


def profile_groups_from_config(cfg: dict, profile_key: str):
    prof = (cfg.get("profiles") or {}).get(profile_key) or {}
    groups = prof.get("groups") or []
    is_incentive = ALL_PROFILES.get(profile_key, {}).get("build_mode") == "incentive"
    groups, _ = sanitize_config_groups(groups)
    out = []
    for g in groups:
        ids = [str(x).strip() for x in (g.get("account_ids") or []) if str(x).strip()]
        if is_incentive:
            meta = {
                "group_name": g.get("group_name", ""),
                "click_url": g.get("click_url", ""),
                "show_url": g.get("show_url", ""),
                "play_url": g.get("play_url", ""),
            }
            if ids:
                out.append((ids, [], meta))
        else:
            dramas = []
            for d in (g.get("dramas") or []):
                name = (d.get("name") or "").strip()
                if not name:
                    continue
                dramas.append({
                    "name": name,
                    "click": (d.get("click") or "").strip(),
                    "show": (d.get("show") or "").strip(),
                    "video": (d.get("video") or "").strip(),
                    "material_ids": [str(x).strip() for x in (d.get("material_ids") or []) if str(x).strip()],
                })
            if ids or dramas:
                out.append((ids, dramas))
    return out


def build_runtime_profile_config(profile_key: str, app_cfg: dict | None = None) -> dict:
    from backend.core.config_io import load_config
    from backend.core.constants import PROFILE_EDITABLE_FIELDS
    app_cfg = app_cfg or load_config()
    cfg = dict(ALL_PROFILES[profile_key])
    user_prof = (app_cfg.get("profiles") or {}).get(profile_key) or {}
    for f in PROFILE_EDITABLE_FIELDS:
        if f in user_prof and user_prof[f] not in (None, ""):
            cfg[f] = user_prof[f]
    try:
        cfg["wait_scale"] = float(cfg["wait_scale"])
    except Exception:
        cfg["wait_scale"] = ALL_PROFILES[profile_key]["wait_scale"]
    return cfg


# ═══════════════════════════════════════════════════════════════
#  剧名/素材文本解析（用于剧单管理工具）
# ═══════════════════════════════════════════════════════════════
def _normalize_title(title):
    """标题归一化：小写、去空格、去标点，仅保留中文+字母+数字。"""
    if not title:
        return ""
    import unicodedata
    t = title.lower().strip()
    t = re.sub(r'\s+', '', t)
    t = re.sub(r'[^一-龥a-z0-9]', '', t)
    return t


def _fuzzy_find(name, mapping):
    """模糊匹配：精确 → 包含关系。"""
    key = _normalize_title(name)
    if not key:
        return None
    if key in mapping:
        return mapping[key]
    for k in mapping:
        if key in k or k in key:
            return mapping[k]
    return None


def _parse_judan_map(text):
    """解析剧单文本 → {normalized_title: original_title}。"""
    m = {}
    if not text:
        return m
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        key = _normalize_title(line)
        if key and key not in m:
            m[key] = line
    return m


def _parse_material_map(text):
    """解析素材文本 → {normalized_title: {"rawTitle": str, "ids": [str]}}。"""
    m = {}
    if not text:
        return m
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r'^(.*?)(\s+\d{10,}(?:\s+\d{10,})*)$', line)
        if match:
            raw_title = match.group(1).strip()
            ids = match.group(2).strip().split()
            key = _normalize_title(raw_title)
            if key and ids:
                m[key] = {"rawTitle": raw_title, "ids": ids}
    return m


def _parse_drama_blocks(text):
    """解析短剧数据文本 → [{"name": str, "links": [str]}]。"""
    if not text:
        return []
    # 先尝试整理好的格式
    dramas = _parse_clean_format(text)
    if dramas:
        return dramas
    return _parse_raw_format(text)


def _parse_clean_format(text):
    """解析整理好的格式：剧名 + 链接，空行分隔。"""
    blocks = re.split(r'\n{2,}', text)
    dramas = []
    current = None
    for block in blocks:
        trimmed = block.strip()
        if not trimmed or is_separator_line(trimmed):
            continue
        if re.match(r'^https?://', trimmed, re.I):
            if current:
                link = sanitize_link_text(trimmed)
                if link:
                    current["links"].append(link)
        elif '://' not in trimmed and not re.match(r'^\d+$', trimmed):
            if current and current["links"]:
                dramas.append(current)
            current = {"name": trimmed, "links": []}
    if current and current["links"]:
        dramas.append(current)
    return dramas


def _parse_raw_format(text):
    """解析原始数据格式（token 解析，支持 '短剧名-xxx' 格式）。"""
    tokens = text.split()
    groups = []
    current = None
    for token in tokens:
        if not token or is_separator_line(token):
            continue
        if re.match(r'^https?://', token, re.I):
            link = sanitize_link_text(token)
            if current and link and link not in current["links"]:
                current["links"].append(link)
        elif '-' in token:
            parts = token.split('-')
            current = {"name": parts[-1].strip(), "links": []}
            groups.append(current)
        else:
            if current and not current["links"] and not re.match(r'^\d+$', token):
                current["name"] += token
    return [g for g in groups if g["links"]]


# ═══════════════════════════════════════════════════════════════
#  推广链名称工具
# ═══════════════════════════════════════════════════════════════
_PC_CLEAN_NAME_RE = re.compile(r"[^一-龥A-Za-z0-9]")
_PC_CHINESE_ONLY_RE = re.compile(r"[^一-龥]")


def _pc_clean_name(name: str) -> str:
    return _PC_CLEAN_NAME_RE.sub("", name)


def _pc_extract_chinese(text: str) -> str:
    return _PC_CHINESE_ONLY_RE.sub("", text)
