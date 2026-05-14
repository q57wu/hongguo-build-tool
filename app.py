"""
红果搭建工具 - pywebview 启动入口
"""
import logging
import os
import sys
import subprocess
import shutil
from pathlib import Path

_logger = logging.getLogger(__name__)

import webview

from backend.api import Api
from backend.bridge import bridge

# ═══════════════════════════════════════════════════════════════
#  运行目录与首次运行初始化
# ═══════════════════════════════════════════════════════════════
def _get_app_dir() -> Path:
    """exe 所在目录（打包后）或项目根目录（源码运行）"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _first_run_init():
    """首次运行时自动生成必要的目录和文件。

    在 exe 旁边创建：
    - frontend/dist/  （从打包资源释放）
    - backend/selectors/oceanengine.json （从打包资源释放）
    - data/           （账户池数据库目录）
    - config_backups/ （配置备份目录）
    - diagnostics/    （诊断文件目录）
    - config.json     （默认配置）
    - 数据/           （各模式的 ids.txt 模板）
    """
    app_dir = _get_app_dir()

    # 1. 打包模式：释放 frontend/dist 到 exe 旁边
    if getattr(sys, "frozen", False):
        meipass = Path(sys._MEIPASS)

        # 释放 frontend/dist
        src_dist = meipass / "frontend" / "dist"
        dst_dist = app_dir / "frontend" / "dist"
        if src_dist.exists() and not dst_dist.exists():
            _logger.info("首次运行：释放前端资源...")
            shutil.copytree(src_dist, dst_dist)

        # 释放 selectors
        src_sel = meipass / "backend" / "selectors" / "oceanengine.json"
        dst_sel = app_dir / "backend" / "selectors" / "oceanengine.json"
        if src_sel.exists() and not dst_sel.exists():
            dst_sel.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_sel, dst_sel)

        # 释放 assets
        src_assets = meipass / "assets"
        dst_assets = app_dir / "assets"
        if src_assets.exists() and not dst_assets.exists():
            shutil.copytree(src_assets, dst_assets)

    # 2. 创建运行时数据目录
    for d in ["data", "config_backups", "diagnostics"]:
        (app_dir / d).mkdir(parents=True, exist_ok=True)

    # 3. 初始化数据目录（ids.txt 模板等）
    try:
        from backend.core.config_io import init_data_dirs
        created = init_data_dirs()
        if created:
            _logger.info(f"首次运行：已创建模板文件 {len(created)} 个")
    except Exception as e:
        _logger.warning(f"初始化数据目录失败: {e}")

    # 4. 生成默认 config.json（如不存在）
    config_file = app_dir / "config.json"
    if not config_file.exists():
        try:
            from backend.core.config_io import load_config, save_config
            cfg = load_config()   # 会返回带默认值的完整配置
            save_config(cfg)
            _logger.info("首次运行：已生成默认 config.json")
        except Exception as e:
            _logger.warning(f"生成默认配置失败: {e}")


# 单实例：启动时关闭已有的旧进程
PID_FILE = _get_app_dir() / ".app.pid"


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
        return str(dist_index) + f"?v={int(dist_index.stat().st_mtime)}"

    # 回退：尝试开发服务器
    return "http://localhost:5173"


def main():
    _kill_old_instance()
    _save_pid()
    _first_run_init()

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
    try:
        main()
    except Exception as e:
        import traceback
        err_msg = f"启动失败: {e}\n\n{traceback.format_exc()}"
        _logger.critical(err_msg)
        # 尝试写入错误日志文件
        try:
            Path(__file__).parent.joinpath("crash.log").write_text(
                err_msg, encoding="utf-8"
            )
        except Exception:
            pass
        # 尝试弹窗提示用户
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, f"红果搭建工具启动失败:\n\n{e}\n\n详见 crash.log", "启动错误", 0x10
            )
        except Exception:
            print(err_msg, file=sys.stderr)
        sys.exit(1)
