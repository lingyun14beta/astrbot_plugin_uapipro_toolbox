import aiohttp
import tempfile
import os
from astrbot.api import logger

API_URL = "https://uapis.cn/api/v1/image/qrcode"


async def fetch(arg_str: str, token: str, session: aiohttp.ClientSession = None):
    """
    二维码生成模块
    解析逻辑：<内容> [尺寸]
    """
    usage_hint = (
        "🔗 二维码指令规范：\n"
        "━━━━━━━━━━━━━━\n"
        "用法：/u 二维码 <内容> [尺寸]\n"
        "示例：/u 二维码 https://uapis.cn 512\n"
        "提示：尺寸范围 256-2048，不填默认 256"
    )

    arg = arg_str.strip()
    if not arg:
        return False, "", usage_hint

    # 逻辑：从右侧分割，判断最后一个空格后的部分是否为数字尺寸
    parts = arg.rsplit(maxsplit=1)
    size = 256
    text = ""

    if len(parts) == 2 and parts[1].isdigit():
        text = parts[0].strip()
        size = int(parts[1])
    else:
        text = arg

    if not text:
        return False, "", f"❌ 请求参数错误：请提供要编码的内容。\n\n{usage_hint}"

    if len(text) > 500:
        return False, "", "❌ 内容过长，请限制在 500 字符以内。"

    if size < 256 or size > 2048:
        return False, "", "❌ 请求参数错误：尺寸需在 256 到 2048 之间。"

    params = {"text": text, "size": size, "format": "image"}
    local_session = False

    if session is None:
        headers = {"User-Agent": "AstrBot_UApiPro"}
        if token:
            headers["Token"] = token
            headers["Authorization"] = f"Bearer {token}"
        session = aiohttp.ClientSession(headers=headers)
        local_session = True

    try:
        async with session.get(API_URL, params=params, timeout=20) as resp:
            content_type = resp.headers.get("Content-Type", "").lower()

            if resp.status == 200 and "image" in content_type:
                img_data = await resp.read()
                fd, path = tempfile.mkstemp(suffix=".png", prefix="qrcode_")
                try:
                    with os.fdopen(fd, 'wb') as f:
                        f.write(img_data)
                finally:
                    del img_data
                return True, path, ""

            try:
                data = await resp.json(content_type=None)
                api_msg = str(data.get("message", ""))[:100]
            except Exception:
                api_msg = ""

            if resp.status == 401:
                return False, "", "❌ 鉴权失败：Authorization 头缺失或 Token 无效。"
            elif resp.status == 400:
                return False, "", f"❌ 无效参数: {api_msg}"
            return False, "", f"❌ 接口请求失败 (HTTP {resp.status})"

    except Exception as e:
        logger.warning(f"[UApiPro] 二维码生成异常: {e}")
        return False, "", "⚠️ 网络连接失败，请稍后再试。"
    finally:
        if local_session:
            await session.close()
