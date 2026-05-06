# -*- coding: utf-8 -*-
import subprocess, sys, os
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"

# 使用脚本所在目录，而非硬编码路径
gui_dir = str(Path(__file__).resolve().parent)
main_py = str(Path(gui_dir) / "app.py")

p = subprocess.Popen(
    [sys.executable, main_py],
    cwd=gui_dir,
    creationflags=subprocess.CREATE_NEW_CONSOLE,
    env={**os.environ, "PYTHONUTF8": "1"},
)
print(f"Started PID={p.pid}")
