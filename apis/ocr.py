import aiohttp
from astrbot.api import logger

API_URL = "https://uapis.cn/api/v1/image/ocr"

MAX_IMAGE_BYTES = 10 * 1024 * 1024


async def fetch(
    image_b64: str,
    token: str,
    return_markdown: bool = False,
    enable_cls: bool = True,
    session: aiohttp.ClientSession = None,
):
    """
    通用 OCR 文字识别模块。
    image_b64 为纯 Base64 编码图片，不带 data:image/...;base64, 前缀。
    """
    if not image_b64:
        return False, "", "❌ 未获取到图片数据。"

    if len(image_b64) > MAX_IMAGE_BYTES // 3 * 4:
        return False, "", "❌ 图片过大，请发送不超过 10MB 的图片。"

    form = aiohttp.FormData()
    form.add_field("image_base64", image_b64)
    form.add_field("need_location", "false")
    form.add_field("return_markdown", "true" if return_markdown else "false")
    form.add_field("enable_cls", "true" if enable_cls else "false")

    local_session = False
    if session is None:
        headers = {"User-Agent": "AstrBot_UApiPro", "Token": token, "Authorization": f"Bearer {token}"}
        session = aiohttp.ClientSession(headers=headers)
        local_session = True

    try:
        async with session.post(API_URL, data=form, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            try:
                data = await resp.json(content_type=None)
            except Exception:
                data = {}

            if not isinstance(data, dict):
                data = {}

            if resp.status == 200:
                if return_markdown:
                    text = (data.get("markdown") or data.get("text") or data.get("plain_text") or "").strip()
                else:
                    text = (data.get("text") or data.get("plain_text") or "").strip()
                if not text:
                    return False, "", "❌ 未识别到任何文字内容。"
                return True, text, ""

            api_msg = str(data.get("message", ""))[:150]
            if resp.status == 413:
                return False, "", "❌ 图片过大，请发送不超过 10MB 的图片。"
            elif resp.status == 415:
                return False, "", "❌ 不支持的图片格式，请发送 JPG/PNG/WebP 等常见格式。"
            elif resp.status == 400:
                return False, "", f"❌ 请求参数错误: {api_msg or '图片数据无效'}"
            elif resp.status in (502, 503):
                return False, "", f"❌ 识别服务暂时不可用: {api_msg or '请稍后再试'}"
            return False, "", f"❌ 接口请求失败 (HTTP {resp.status}): {api_msg}"

    except Exception as e:
        logger.warning(f"[UApiPro] OCR 识别异常: {e}")
        return False, "", "⚠️ 网络连接失败，请稍后再试。"
    finally:
        if local_session:
            await session.close()
