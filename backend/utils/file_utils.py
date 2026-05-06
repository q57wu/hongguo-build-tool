"""原子写入 + 自动备份轮转"""
import json
import shutil
import filelock
from pathlib import Path
from datetime import datetime

MAX_BACKUPS = 5


def save_json_atomic(filepath: Path, data, backup_dir: Path = None):
    """原子写入JSON文件 + 自动备份
    - 写入前先备份当前文件到 backup_dir（默认同级 config_backups/）
    - 写临时文件再 replace，保证原子性
    - 用 filelock 防止并发写入
    """
    filepath = Path(filepath)
    if backup_dir is None:
        backup_dir = filepath.parent / "config_backups"

    lock = filelock.FileLock(str(filepath) + ".lock", timeout=10)
    try:
        with lock:
            # 备份
            if filepath.exists():
                backup_dir.mkdir(parents=True, exist_ok=True)
                stem = filepath.stem
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_path = backup_dir / f"{stem}_{ts}.json"
                shutil.copy2(filepath, backup_path)
                # 清理旧备份，只保留最近 MAX_BACKUPS 个
                backups = sorted(backup_dir.glob(f"{stem}_*.json"))
                for old in backups[:-MAX_BACKUPS]:
                    old.unlink(missing_ok=True)

            # 原子写入
            filepath.parent.mkdir(parents=True, exist_ok=True)
            tmp = filepath.with_suffix('.tmp')
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            tmp.replace(filepath)  # 原子操作
    except filelock.Timeout:
        import logging
        logging.getLogger(__name__).error(
            f"save_json_atomic: 获取文件锁超时（10秒），文件可能被其他进程占用: {filepath}"
        )
        raise


def load_json_safe(filepath: Path, default=None, backup_dir: Path = None):
    """安全加载JSON，损坏时从备份恢复"""
    filepath = Path(filepath)
    if backup_dir is None:
        backup_dir = filepath.parent / "config_backups"

    if filepath.exists():
        try:
            return json.loads(filepath.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass  # 文件损坏，尝试从备份恢复

    # 尝试从备份恢复
    stem = filepath.stem
    if backup_dir.exists():
        backups = sorted(backup_dir.glob(f"{stem}_*.json"), reverse=True)
        for backup in backups:
            try:
                data = json.loads(backup.read_text(encoding='utf-8'))
                # 恢复成功，写回主文件
                filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
                return data
            except Exception:
                continue

    return default if default is not None else {}
