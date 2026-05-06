"""
backend/core/logging_utils.py
日志和格式化工具。
"""
import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logger(log_dir: Path):
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"搭建_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    lg = logging.getLogger("build")
    lg.setLevel(logging.DEBUG)
    lg.handlers.clear()
    lg.propagate = False

    console_fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    file_fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(funcName)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(console_fmt)
    lg.addHandler(ch)

    try:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(file_fmt)
        lg.addHandler(fh)
        lg.info(f"📝 日志文件: {log_file}")
    except Exception as e:
        lg.warning(f"⚠️ 日志文件初始化失败: {e}")

    return lg


def fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}秒"
    m, s = divmod(int(seconds), 60)
    if m < 60:
        return f"{m}分{s}秒"
    h, m = divmod(m, 60)
    return f"{h}时{m}分{s}秒"


