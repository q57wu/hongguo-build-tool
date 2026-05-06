"""
红果搭建工具 - pywebview 启动入口
"""
import logging
import os
import sys
import subprocess
from pathlib import Path

_logger = logging.getLogger(__name__)

import webview

from backend.api import Api
from backend.bridge import bridge

# 单实例：启动时关闭已有的旧进程
PID_FILE = Path(__file__).parent / ".app.pid"


def _kill_old_instance():
    """如果有旧进程在运行，用 PowerShell 强制关闭它"""
    old_pid = None
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            my_pid = os.getpid()
            if old_pid != my_pid:
                subprocess.run(
                    ["powershell", "-Command",
                     f"Stop-Process -Id {old_pid} -Force -ErrorAction SilentlyContinue"],
                    capture_output=True, timeout=5
                )
        except Exception as e:
            _logger.warning(f"_kill_old_instance 终止旧进程失败 (pid={old_pid if old_pid is not None else '?'}): {e}")
        try:
            PID_FILE.unlink()
        except Exception as e:
            _logger.warning(f"_kill_old_instance 删除 PID 文件失败: {e}")


def _save_pid():
    """保存当前进程 PID"""
    pid_str = str(os.getpid())
    for attempt in range(2):
        try:
            PID_FILE.write_text(pid_str)
            return
        except Exception as e:
            if attempt == 0:
                _logger.warning(f"_save_pid 写入失败，尝试重试: {e}")
            else:
                _logger.error(f"_save_pid 写入重试失败，PID 文件未能保存: {e}")


def get_frontend_url():
    """获取前端资源路径/URL"""
    dev_mode = os.environ.get("DEV", "0") == "1"

    if dev_mode:
        # 开发模式：连接 Vite dev server（支持热更新）
        return "http://localhost:5173"

    # 生产模式：加载构建后的 HTML 文件
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent

    dist_index = base / "frontend" / "dist" / "index.html"
    if dist_index.exists():
        return str(dist_index)

    # 回退：尝试开发服务器
    return "http://localhost:5173"


def main():
    _kill_old_instance()
    _save_pid()

    api = Api()

    window = webview.create_window(
        title="红果搭建工具",
        url=get_frontend_url(),
        width=1100,
        height=750,
        min_size=(900, 600),
        js_api=api,
        background_color="#f7f8fa",
    )

    # 窗口加载完成后设置事件桥接
    def on_loaded():
        bridge.set_window(window)

    window.events.loaded += on_loaded

    # 启动 webview（关闭私有模式，确保 localStorage 跨会话持久化）
    webview.start(debug=("--debug" in sys.argv), private_mode=False)


if __name__ == "__main__":
    main()
