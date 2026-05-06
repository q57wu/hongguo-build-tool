"""视觉识别服务：调用 OpenAI 兼容的 Vision API 识别图片中的文字"""
import base64
import json
import logging
import urllib.request
import urllib.error

_logger = logging.getLogger(__name__)

DEFAULT_API_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o"
DEFAULT_PROMPT = "请识别这张图片中的所有文字内容，原样输出，保持原始格式和换行。不要添加任何解释或额外内容。"
TIMEOUT = 60


def _get_config() -> dict:
    """读取 config.json common 字段中的视觉模型配置"""
    try:
        from backend.config_manager import load_config
        cfg = load_config()
        return cfg.get("common", {})
    except Exception as e:
        _logger.warning(f"vision_service: 读取配置失败: {e}")
        return {}


def _ensure_base64(image_data: str) -> str:
    """去除 data URI 前缀，只保留纯 base64 内容"""
    if "," in image_data:
        return image_data.split(",", 1)[1]
    return image_data


def _detect_mime(image_data_raw: str) -> str:
    """从 data URI 前缀推断 MIME 类型，默认 image/png"""
    if image_data_raw.startswith("data:"):
        try:
            mime = image_data_raw.split(";")[0].split(":")[1]
            if mime in ("image/png", "image/jpeg", "image/gif", "image/webp"):
                return mime
        except Exception:
            pass
    return "image/png"


def recognize_image(image_data: str, prompt: str = "") -> dict:
    """识别图片中的文字内容。

    Args:
        image_data: base64 编码的图片数据，可带或不带 ``data:image/...;base64,`` 前缀。
        prompt:     识别提示词，留空时使用默认 OCR 提示。

    Returns:
        成功: ``{"ok": True, "text": "识别结果"}``
        失败: ``{"ok": False, "error": "错误信息"}``
    """
    # 1. 读取配置
    common = _get_config()
    api_key = common.get("vision_api_key", "").strip()
    api_base = common.get("vision_api_base", DEFAULT_API_BASE).rstrip("/")
    model = common.get("vision_model", DEFAULT_MODEL).strip() or DEFAULT_MODEL

    if not api_key:
        return {"ok": False, "error": "视觉模型 API Key 未配置，请在设置中填写 vision_api_key"}

    # 2. 处理图片数据
    mime_type = _detect_mime(image_data)
    b64_data = _ensure_base64(image_data)

    # 简单校验 base64 合法性
    try:
        base64.b64decode(b64_data, validate=True)
    except Exception:
        return {"ok": False, "error": "图片数据不是合法的 base64 编码"}

    # 3. 构造请求体
    user_prompt = prompt.strip() or DEFAULT_PROMPT
    payload = {
        "model": model,
        "max_tokens": 4096,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{b64_data}",
                            "detail": "high",
                        },
                    },
                    {
                        "type": "text",
                        "text": user_prompt,
                    },
                ],
            }
        ],
    }

    # 4. 发送请求
    url = f"{api_base}/chat/completions"
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
            err_json = json.loads(err_body)
            err_msg = err_json.get("error", {}).get("message", err_body)
        except Exception:
            err_msg = str(e)
        _logger.error(f"vision_service: API 返回错误 {e.code}: {err_msg}")
        return {"ok": False, "error": f"API 错误 {e.code}: {err_msg}"}
    except urllib.error.URLError as e:
        _logger.error(f"vision_service: 网络错误: {e.reason}")
        return {"ok": False, "error": f"网络错误: {e.reason}"}
    except TimeoutError:
        _logger.error("vision_service: 请求超时")
        return {"ok": False, "error": f"请求超时（{TIMEOUT}s），请检查网络或更换 API 地址"}
    except Exception as e:
        _logger.exception("vision_service: 未知错误")
        return {"ok": False, "error": f"未知错误: {e}"}

    # 5. 解析响应
    try:
        text = result["choices"][0]["message"]["content"]
        return {"ok": True, "text": text}
    except (KeyError, IndexError, TypeError) as e:
        _logger.error(f"vision_service: 响应格式异常: {result}")
        return {"ok": False, "error": f"响应格式异常: {e}，原始响应: {result}"}
