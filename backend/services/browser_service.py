"""浏览器管理服务：自动启动 Chrome CDP + 健康检查"""
import subprocess
import threading
import time
import logging
import urllib.request
import json
from pathlib import Path

_logger = logging.getLogger(__name__)

# Chrome 常见安装路径（Windows）
CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "Application" / "chrome.exe",
]

DEFAULT_CDP_PORT = 9222
CDP_ENDPOINT = f"http://127.0.0.1:{DEFAULT_CDP_PORT}"


def find_chrome() -> str | None:
    """查找 Chrome 可执行文件路径"""
    # 优先从配置读取
    try:
        from backend.config_manager import load_config
        cfg = load_config()
        custom_path = cfg.get("common", {}).get("chrome_path", "")
        if custom_path and Path(custom_path).exists():
            return custom_path
    except Exception:
        pass

    # 搜索常见路径
    for p in CHROME_PATHS:
        p = Path(p)
        if p.exists():
            return str(p)

    # 尝试 where 命令
    try:
        result = subprocess.run(["where", "chrome"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            candidates = [
                line.strip()
                for line in result.stdout.strip().splitlines()
                if line.strip().lower().endswith("chrome.exe")
            ]
            for candidate in candidates:
                if Path(candidate).exists():
                    return candidate
    except Exception:
        pass

    return None


def is_cdp_available(port: int = DEFAULT_CDP_PORT, timeout: float = 2.0) -> bool:
    """检查 CDP 端口是否可用（Chrome 是否已以调试模式运行）"""
    try:
        url = f"http://127.0.0.1:{port}/json/version"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            return "Browser" in data or "webSocketDebuggerUrl" in data
    except Exception:
        return False


def launch_chrome(port: int = DEFAULT_CDP_PORT) -> dict:
    """启动 Chrome 调试模式（同步版，内部使用）
    Returns: {"ok": bool, "message": str, "already_running": bool}
    """
    # 1. 先检查是否已在运行
    if is_cdp_available(port):
        return {"ok": True, "message": "Chrome 调试模式已在运行", "already_running": True}

    # 2. 查找 Chrome
    chrome_path = find_chrome()
    if not chrome_path:
        return {"ok": False, "message": "未找到 Chrome，请在设置中配置 Chrome 路径", "already_running": False}

    # 3. 启动 Chrome（参数与 启动浏览器.bat 保持一致）
    try:
        user_data = r"C:\ChromeProfile"
        Path(user_data).mkdir(parents=True, exist_ok=True)

        cmd = [
            chrome_path,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_data}",
            "--disable-backgrounding-occluded-windows",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--silent-debugger-extension-api",
            "--no-first-run",
            "--disable-blink-features=AutomationControlled",
        ]

        subprocess.Popen(cmd, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        _logger.info(f"Chrome 已启动，端口: {port}")

        # 4. 等待 CDP 就绪
        for i in range(10):
            time.sleep(1)
            if is_cdp_available(port):
                return {"ok": True, "message": f"Chrome 已启动并连接（端口 {port}）", "already_running": False}

        return {"ok": False, "message": "Chrome 已启动但 CDP 连接超时，请稍后重试", "already_running": False}

    except Exception as e:
        _logger.error(f"启动 Chrome 失败: {e}")
        return {"ok": False, "message": f"启动失败: {e}", "already_running": False}


def launch_chrome_async(port: int = DEFAULT_CDP_PORT) -> None:
    """在后台线程启动 Chrome，完成后通过 EventBridge 推送结果。

    前端监听事件：
      - ``honguo:browser_ready``  → {"ok": True, "message": ..., "already_running": bool}
      - ``honguo:browser_error``  → {"ok": False, "message": ...}
    调用方立即返回，UI 不阻塞。
    """
    def _worker():
        from backend.bridge import bridge
        result = launch_chrome(port)
        if result["ok"]:
            bridge.emit("browser_ready", result)
        else:
            bridge.emit("browser_error", result)

    t = threading.Thread(target=_worker, daemon=True, name="launch-chrome")
    t.start()


def get_cdp_info(port: int = DEFAULT_CDP_PORT) -> dict:
    """获取 CDP 连接信息"""
    try:
        url = f"http://127.0.0.1:{port}/json/version"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read())
    except Exception:
        return {}
