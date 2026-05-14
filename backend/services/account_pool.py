"""
账户池服务 — SQLite 存储，支持投放账户和素材账户的统一管理
"""
import sqlite3
import threading
import time
import uuid
from pathlib import Path

# DB paths: dual pool — normal (单本) and incentive (激励)
_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH_NORMAL = _DB_DIR / "account_pool.db"
DB_PATH_INCENTIVE = _DB_DIR / "account_pool_incentive.db"

_local = threading.local()


def _get_conn(pool: str = "normal") -> sqlite3.Connection:
    """Get a thread-local SQLite connection for the specified pool."""
    if pool == "incentive":
        attr = "conn_incentive"
        db_path = DB_PATH_INCENTIVE
    else:
        attr = "conn_normal"
        db_path = DB_PATH_NORMAL

    conn = getattr(_local, attr, None)
    if conn is None:
        _DB_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        setattr(_local, attr, conn)
    return conn


_TABLE_SCHEMA = """
    CREATE TABLE IF NOT EXISTS accounts (
        id          TEXT PRIMARY KEY,
        account_id  TEXT NOT NULL,
        name        TEXT DEFAULT '',
        type        TEXT NOT NULL CHECK(type IN ('media', 'material')),
        platform    TEXT DEFAULT '',
        group_name  TEXT DEFAULT '',
        status      TEXT DEFAULT '',
        strategy    TEXT DEFAULT '',
        tags        TEXT DEFAULT '',
        remark      TEXT DEFAULT '',
        created_at  TEXT NOT NULL,
        updated_at  TEXT NOT NULL,
        last_used   TEXT DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_accounts_type ON accounts(type);
    CREATE INDEX IF NOT EXISTS idx_accounts_account_id ON accounts(account_id);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_unique ON accounts(account_id, type);
    CREATE INDEX IF NOT EXISTS idx_accounts_updated_at ON accounts(updated_at DESC);
    CREATE INDEX IF NOT EXISTS idx_accounts_platform ON accounts(platform);
    CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status);
"""


def _init_single_db(pool: str):
    """Initialize tables for a single pool database."""
    conn = _get_conn(pool)
    conn.executescript(_TABLE_SCHEMA)
    conn.commit()


def init_db():
    """Initialize both normal and incentive database tables."""
    _init_single_db("normal")
    _init_single_db("incentive")
    _migrate_incentive_accounts()


def _row_to_dict(row) -> dict:
    """Convert a sqlite3.Row to a plain dict with tags as list."""
    d = dict(row)
    d["tags"] = [t.strip() for t in d.get("tags", "").split(",") if t.strip()] if d.get("tags") else []
    return d


def _now() -> str:
    """ISO format timestamp."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ═══ CRUD Operations ═══

def get_accounts(account_type: str = "", keyword: str = "", tag: str = "",
                 platform: str = "", strategy: str = "", status: str = "",
                 limit=50, offset=0, pool: str = "normal") -> dict:
    """
    Query accounts with optional filters. Returns {items, total}.
    - account_type: 'media' or 'material' or '' (all)
    - keyword: search in account_id, name, owner, group_name, remark
    - tag: filter by tag (partial match)
    - platform: 'IOS' or '安卓' or '' (all)
    - strategy: '每留' or '七留' or '' (all)
    - status: '已设置' or '' (all)
    - limit: max rows to return (default 50)
    - offset: number of rows to skip (default 0)
    - pool: 'normal' or 'incentive' (default 'normal')
    """
    conn = _get_conn(pool=pool)
    where = "WHERE 1=1"
    params = []

    if account_type:
        where += " AND type = ?"
        params.append(account_type)

    if platform:
        where += " AND platform = ?"
        params.append(platform)

    if strategy:
        where += " AND strategy = ?"
        params.append(strategy)

    if status:
        where += " AND status = ?"
        params.append(status)

    if keyword:
        where += " AND (account_id LIKE ? OR name LIKE ? OR group_name LIKE ? OR remark LIKE ?)"
        kw = f"%{keyword}%"
        params.extend([kw, kw, kw, kw])

    if tag:
        where += " AND tags LIKE ?"
        params.append(f"%{tag}%")

    limit = int(limit) if limit else 50
    offset = int(offset) if offset else 0

    total_count = conn.execute(f"SELECT COUNT(*) FROM accounts {where}", params).fetchone()[0]

    rows = conn.execute(
        f"SELECT * FROM accounts {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        params + [limit, offset]
    ).fetchall()

    return {"items": [_row_to_dict(r) for r in rows], "total": total_count}


def get_account_by_id(row_id: str) -> dict | None:
    """Get a single account by its internal row ID."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM accounts WHERE id = ?", (row_id,)).fetchone()
    return _row_to_dict(row) if row else None


def add_account(account_id: str, account_type: str, name: str = "", tags: list = None, remark: str = "",
                group_name: str = "", status: str = "", strategy: str = "", platform: str = "",
                pool: str = "normal") -> dict:
    """
    Add a single account. Returns {ok, id} or {ok: False, error}.
    Rejects duplicates (same account_id + type).
    """
    conn = _get_conn(pool=pool)
    row_id = uuid.uuid4().hex[:12]
    now = _now()
    tags_str = ",".join(tags) if tags else ""

    try:
        conn.execute(
            "INSERT INTO accounts (id, account_id, name, type, platform, group_name, status, strategy, tags, remark, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (row_id, account_id.strip(), name.strip(), account_type, platform.strip(), group_name.strip(), status.strip(), strategy.strip(), tags_str, remark.strip(), now, now)
        )
        conn.commit()
        return {"ok": True, "id": row_id}
    except sqlite3.IntegrityError:
        return {"ok": False, "error": f"账户 {account_id} ({account_type}) 已存在"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def add_accounts_batch(accounts: list, pool: str = "normal") -> dict:
    """
    Batch add accounts. Each item in list should be a dict with:
      account_id, type, name (optional), tags (optional list), remark (optional)
    Returns {ok, added: int, skipped: int, errors: list}
    """
    conn = _get_conn(pool=pool)
    added = 0
    skipped = 0
    errors = []
    now = _now()

    for item in accounts:
        account_id = str(item.get("account_id", "")).strip()
        if not account_id:
            errors.append("空的账户ID，已跳过")
            continue

        account_type = item.get("type", "media")
        name = str(item.get("name", "")).strip()
        platform = str(item.get("platform", "")).strip()
        group_name = str(item.get("group_name", "")).strip()
        status = str(item.get("status", "")).strip()
        strategy = str(item.get("strategy", "")).strip()
        tags_str = ",".join(item.get("tags", [])) if item.get("tags") else ""
        remark = str(item.get("remark", "")).strip()
        row_id = uuid.uuid4().hex[:12]

        try:
            conn.execute(
                "INSERT INTO accounts (id, account_id, name, type, platform, group_name, status, strategy, tags, remark, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (row_id, account_id, name, account_type, platform, group_name, status, strategy, tags_str, remark, now, now)
            )
            added += 1
        except sqlite3.IntegrityError:
            skipped += 1
        except Exception as e:
            errors.append(f"{account_id}: {e}")

    conn.commit()
    return {"ok": True, "added": added, "skipped": skipped, "errors": errors}


def update_account(row_id: str, data: dict, pool: str = "normal") -> dict:
    """
    Update account fields. data can contain: name, tags (list), remark.
    Cannot change account_id or type.
    """
    conn = _get_conn(pool=pool)
    sets = []
    params = []

    if "name" in data:
        sets.append("name = ?")
        params.append(str(data["name"]).strip())
    if "platform" in data:
        sets.append("platform = ?")
        params.append(str(data["platform"]).strip())
    if "group_name" in data:
        sets.append("group_name = ?")
        params.append(str(data["group_name"]).strip())
    if "status" in data:
        sets.append("status = ?")
        params.append(str(data["status"]).strip())
    if "strategy" in data:
        sets.append("strategy = ?")
        params.append(str(data["strategy"]).strip())
    if "tags" in data:
        tags_str = ",".join(data["tags"]) if isinstance(data["tags"], list) else str(data["tags"])
        sets.append("tags = ?")
        params.append(tags_str)
    if "remark" in data:
        sets.append("remark = ?")
        params.append(str(data["remark"]).strip())

    if not sets:
        return {"ok": False, "error": "没有可更新的字段"}

    sets.append("updated_at = ?")
    params.append(_now())
    params.append(row_id)

    sql = f"UPDATE accounts SET {', '.join(sets)} WHERE id = ?"
    conn.execute(sql, params)
    conn.commit()
    return {"ok": True}


def delete_accounts(row_ids: list, pool: str = "normal") -> dict:
    """Delete accounts by internal row IDs."""
    conn = _get_conn(pool=pool)
    if not row_ids:
        return {"ok": False, "error": "未指定删除目标"}

    placeholders = ",".join("?" * len(row_ids))
    conn.execute(f"DELETE FROM accounts WHERE id IN ({placeholders})", row_ids)
    conn.commit()
    return {"ok": True, "deleted": len(row_ids)}


def touch_accounts(account_ids: list, account_type: str = "media", pool: str = "normal"):
    """Update last_used timestamp for the given account_ids (called during build)."""
    if not account_ids:
        return
    conn = _get_conn(pool=pool)
    now = _now()
    cleaned = [aid.strip() for aid in account_ids if aid.strip()]
    if not cleaned:
        return
    placeholders = ",".join("?" * len(cleaned))
    conn.execute(
        f"UPDATE accounts SET last_used = ?, updated_at = ? WHERE account_id IN ({placeholders}) AND type = ?",
        [now, now] + cleaned + [account_type]
    )
    conn.commit()


def get_next_accounts(profile_key: str, num_groups: int = 1, group_size: int = 5) -> dict:
    """
    按轮转逻辑从账户池选取下一批账户。
    - 根据 profile_key 自动推断 platform 和 strategy 筛选条件
    - 按 last_used ASC 排序（未使用优先，最久未用次之）
    - 返回 {ok, groups: [[id1,id2,...], [id3,id4,...], ...], total_available: N}
    """
    # 1. 解析 profile_key -> platform, strategy
    #    "安卓-每留"     → platform="安卓", strategy="每留"
    #    "IOS-七留"      → platform="IOS",  strategy="七留"
    #    "安卓-激励每留" → platform="安卓", strategy="激励每留"
    #    "安卓-激励七留" → platform="安卓", strategy="激励七留"
    #    激励账户和非激励账户是完全独立的池，不共享
    parts = profile_key.split("-", 1)
    if len(parts) != 2:
        return {"ok": False, "error": f"无法解析 profile_key: {profile_key}"}

    platform = parts[0]  # "安卓" or "IOS"
    strategy = parts[1]  # "每留", "七留", "激励每留", "激励七留"

    # Auto-detect pool: incentive accounts go to incentive DB
    pool = "incentive" if "激励" in strategy else "normal"

    # 2. Query matching accounts ordered by last_used ASC (NULL/empty first), then created_at ASC
    conn = _get_conn(pool=pool)
    sql = """
        SELECT account_id FROM accounts
        WHERE type = 'media' AND platform = ? AND strategy = ?
        ORDER BY
            CASE WHEN last_used IS NULL OR last_used = '' THEN 0 ELSE 1 END ASC,
            last_used ASC,
            created_at ASC
    """
    rows = conn.execute(sql, (platform, strategy)).fetchall()
    total_available = len(rows)

    # 3. Take the first num_groups * group_size accounts
    needed = num_groups * group_size
    selected = [row["account_id"] for row in rows[:needed]]

    # 4. Split into groups of group_size
    groups = []
    for i in range(0, len(selected), group_size):
        groups.append(selected[i:i + group_size])

    result = {
        "ok": True,
        "groups": groups,
        "total_available": total_available,
    }

    # If not enough accounts, add a warning
    if len(selected) < needed:
        result["warning"] = f"可用账户不足：需要 {needed} 个，实际可用 {total_available} 个"

    return result


# ═══ Import / Export ═══

def parse_batch_text(raw_text: str) -> list:
    """
    Parse tab-separated batch text into account dicts.
    Supports multiple formats:
      Format A (7 cols): 账户名称  账户ID  负责人  组  状态  (空)  策略
      Format B (6 cols): 账户名称  账户ID  (空)    组  状态  策略
      Format C (6 cols): 账户名称  账户ID  负责人  组  状态  策略
    Also supports single-column (just account IDs, one per line).

    Strategy detection: scans trailing columns for known strategy keywords
    (每留, 七留, 激励每留, 激励七留) to reliably extract strategy regardless
    of column position.
    """
    _KNOWN_STRATEGIES = {"每留", "七留", "激励每留", "激励七留"}

    results = []
    for line in raw_text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        parts = line.split('\t')
        if len(parts) >= 2:
            # Tab-separated multi-column format
            name = parts[0].strip() if len(parts) > 0 else ""
            account_id = parts[1].strip() if len(parts) > 1 else ""

            # Smart strategy detection: scan from the end for known strategy values
            strategy = ""
            strategy_idx = -1
            for i in range(len(parts) - 1, 1, -1):  # scan from last to index 2
                val = parts[i].strip()
                if val in _KNOWN_STRATEGIES:
                    strategy = val
                    strategy_idx = i
                    break

            # Parse group_name and status based on column count
            # Common patterns:
            #   7 cols: name, id, owner, group, status, (empty), strategy
            #   6 cols: name, id, (empty/owner), group, status, strategy
            group_name = ""
            status = ""

            if len(parts) >= 7:
                # 7+ columns: standard format with empty column before strategy
                group_name = parts[3].strip()
                status = parts[4].strip()
            elif len(parts) >= 5:
                # 5-6 columns: group at [3], status at [4]
                group_name = parts[3].strip() if len(parts) > 3 else ""
                status = parts[4].strip() if len(parts) > 4 else ""
            elif len(parts) >= 4:
                group_name = parts[3].strip()
            # For 2-3 columns, group_name and status remain empty

            # Auto-detect platform from account name
            platform = ""
            name_upper = name.upper()
            if "IOS" in name_upper:
                platform = "IOS"
            elif "安卓" in name:
                platform = "安卓"

            if account_id:
                results.append({
                    "account_id": account_id,
                    "name": name,
                    "platform": platform,
                    "group_name": group_name,
                    "status": status,
                    "strategy": strategy,
                })
        else:
            # Single column — just account ID
            if line:
                results.append({"account_id": line})
    return results


def import_from_config(config: dict, pool: str = "normal") -> dict:
    """
    Import accounts from existing config.json data.
    Scans profiles matching the target pool, auto-detects platform and strategy.
    - pool="normal": imports from non-incentive profiles (安卓-每留, 安卓-七留, IOS-每留, IOS-七留)
    - pool="incentive": imports from incentive profiles (安卓-激励每留, 安卓-激励七留)
    """
    accounts_to_add = []
    seen = set()

    profiles = config.get("profiles", {})
    for profile_key, profile in profiles.items():
        # Parse profile_key to get platform and strategy
        parts = profile_key.split("-", 1)
        if len(parts) != 2:
            continue
        pf_platform = parts[0]   # "安卓" or "IOS"
        pf_strategy = parts[1]   # "每留", "七留", "激励每留", "激励七留"

        # Filter: only import profiles matching the target pool
        is_incentive = "激励" in pf_strategy
        if pool == "incentive" and not is_incentive:
            continue
        if pool != "incentive" and is_incentive:
            continue

        # Import material_account_id
        mat_id = profile.get("material_account_id", "").strip()
        if mat_id and (mat_id, "material") not in seen:
            seen.add((mat_id, "material"))
            accounts_to_add.append({
                "account_id": mat_id,
                "type": "material",
                "name": "",
                "platform": pf_platform,
                "strategy": pf_strategy,
                "tags": [profile_key],
                "remark": f"从配置导入 ({profile_key})",
            })

        # Import group account_ids
        for group in profile.get("groups", []):
            for aid in group.get("account_ids", []):
                aid = str(aid).strip()
                if aid and (aid, "media") not in seen:
                    seen.add((aid, "media"))
                    accounts_to_add.append({
                        "account_id": aid,
                        "type": "media",
                        "name": "",
                        "platform": pf_platform,
                        "strategy": pf_strategy,
                        "tags": [profile_key],
                        "remark": f"从配置导入 ({profile_key})",
                    })

    return add_accounts_batch(accounts_to_add, pool=pool)


def get_all_tags(pool: str = "normal") -> list:
    """Get all unique tags across all accounts."""
    conn = _get_conn(pool=pool)
    rows = conn.execute("SELECT DISTINCT tags FROM accounts WHERE tags != ''").fetchall()
    tag_set = set()
    for row in rows:
        for t in row["tags"].split(","):
            t = t.strip()
            if t:
                tag_set.add(t)
    return sorted(tag_set)


def get_stats(pool: str = "normal") -> dict:
    """Get account pool statistics."""
    conn = _get_conn(pool=pool)
    rows = conn.execute("""
        SELECT type, platform, status, COUNT(*) as c
        FROM accounts
        GROUP BY type, platform, status
    """).fetchall()

    stats = {"total": 0, "media": 0, "material": 0, "ios": 0, "android": 0, "rta_set": 0}
    for r in rows:
        stats["total"] += r["c"]
        if r["type"] == "media":     stats["media"]    += r["c"]
        if r["type"] == "material":  stats["material"] += r["c"]
        if r["platform"] == "IOS":   stats["ios"]      += r["c"]
        if r["platform"] == "安卓":  stats["android"]  += r["c"]
        if r["status"] == "已设置":  stats["rta_set"]  += r["c"]
    return stats


def get_usage_counts(pool: str = "normal") -> dict:
    """
    统计每个投放账户被分配使用的次数。
    从 assign_logs.json 中扫描 all_account_ids 计数。
    Returns: {account_id: count, ...}
    """
    import json
    log_file = _DB_DIR / "assign_logs.json"
    if not log_file.exists():
        return {}
    try:
        records = json.loads(log_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}

    counts = {}
    for record in records:
        for aid in record.get("all_account_ids", []):
            counts[aid] = counts.get(aid, 0) + 1
    return counts


def _migrate_incentive_accounts():
    """One-time migration: move incentive accounts from normal DB to incentive DB,
    and auto-import incentive accounts from config.json if incentive DB is empty."""
    marker = _DB_DIR / ".incentive_pool_migrated"
    if marker.exists():
        return

    conn_normal = _get_conn("normal")
    # Check if there are any incentive accounts in the normal DB
    rows = conn_normal.execute(
        "SELECT * FROM accounts WHERE strategy LIKE '%激励%'"
    ).fetchall()

    if rows:
        conn_incentive = _get_conn("incentive")
        for row in rows:
            d = dict(row)
            try:
                conn_incentive.execute(
                    "INSERT INTO accounts (id, account_id, name, type, platform, group_name, status, strategy, tags, remark, created_at, updated_at, last_used) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (d["id"], d["account_id"], d["name"], d["type"], d["platform"], d["group_name"], d["status"], d["strategy"], d["tags"], d["remark"], d["created_at"], d["updated_at"], d["last_used"])
                )
            except Exception:
                pass  # skip duplicates
        conn_incentive.commit()

        # Delete from normal DB
        conn_normal.execute("DELETE FROM accounts WHERE strategy LIKE '%激励%'")
        conn_normal.commit()

    # Fix legacy data: incentive DB may have records with non-incentive strategy
    # (e.g. strategy="每留" instead of "激励每留") from old import logic
    conn_incentive = _get_conn("incentive")
    conn_incentive.execute(
        "UPDATE accounts SET strategy = '激励' || strategy WHERE strategy IN ('每留', '七留')"
    )
    conn_incentive.commit()

    # If incentive DB is still empty, auto-import from config.json
    count = conn_incentive.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    if count == 0:
        try:
            import json
            config_path = _DB_DIR.parent / "config.json"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                import_from_config(config, pool="incentive")
        except Exception:
            pass  # non-critical, user can import manually later

    marker.touch()


# Auto-init on import
init_db()
