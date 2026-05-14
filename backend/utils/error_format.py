"""
错误信息友好化翻译工具。
将 Playwright 等技术框架抛出的英文异常翻译为用户可理解的中文提示。
"""
import re


# 错误模式 → 友好提示 映射表
_ERROR_PATTERNS = [
    # Playwright 超时
    (r'Timeout \d+ms exceeded', '页面操作超时，可能是网络慢或页面未加载完成'),
    (r'TimeoutError', '操作超时，请检查网络连接'),
    # 元素定位
    (r'waiting for locator', '等待页面元素出现超时，页面可能已变化'),
    (r'locator resolved to .* elements', '页面元素匹配异常，可能是平台界面更新'),
    (r'Element is not visible', '页面元素不可见，可能被遮挡或未展开'),
    (r'Element is outside of the viewport', '页面元素超出可视范围'),
    # 浏览器连接
    (r'Target closed', '浏览器标签页已关闭'),
    (r'Browser has been closed', '浏览器已关闭，请重新启动 Chrome'),
    (r'browser disconnected', '浏览器连接断开，请检查 Chrome 是否正常运行'),
    (r'Session closed', '浏览器会话已断开'),
    (r'Connection refused', '无法连接到浏览器，请确认 Chrome 已启动调试模式'),
    (r'WebSocket', 'WebSocket 连接异常，浏览器可能已关闭'),
    (r'net::ERR_CONNECTION', '网络连接失败，请检查网络'),
    # 导航
    (r'net::ERR_NAME_NOT_RESOLVED', '域名解析失败，请检查网络连接'),
    (r'net::ERR_INTERNET_DISCONNECTED', '网络已断开'),
    (r'Navigation failed.*timeout', '页面加载超时，请检查网络'),
    # 文件操作
    (r'FileNotFoundError', '文件未找到，请检查配置路径'),
    (r'PermissionError', '文件权限不足，请以管理员身份运行'),
    # JSON
    (r'JSONDecodeError', '配置文件格式错误，请检查 JSON 语法'),
]


def friendly_error(error) -> str:
    """
    将技术异常翻译为用户友好提示。

    :param error: Exception 实例或错误字符串
    :return: 友好化的中文错误描述
    """
    msg = str(error)

    for pattern, friendly_msg in _ERROR_PATTERNS:
        if re.search(pattern, msg, re.IGNORECASE):
            return friendly_msg

    # 未匹配到已知模式：截断过长的错误信息
    if len(msg) > 120:
        msg = msg[:120] + '...'

    return msg
