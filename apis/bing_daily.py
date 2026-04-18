import aiohttp
import tempfile
import os
import re
import asyncio
from astrbot.api import logger

API_URL = "https://uapis.cn/api/v1/image/bing-daily"


async def fetch(arg_str: str, token: str, session: aiohttp.ClientSession = None):
    """
    必应每日壁纸查询模块
    """
    params = {"resolution": "4k", "format": "json"}
    arg = arg_str.strip()
    if arg:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", arg):
            params["date"] = arg
        else:
            return False, "", "❌ 日期格式错误，请使用 YYYY-MM-DD 格式。\n示例：/u 必应 2023-10-01"

    local_session = False
    if session is None:
        headers = {"User-Agent": "AstrBot_UApiPro", "Token": token, "Authorization": f"Bearer {token}"}
        session = aiohttp.ClientSession(headers=headers)
        local_session = True

    try:
        async with session.get(API_URL, params=params, timeout=10) as resp:
            if resp.status != 200:
                return False, "", f"❌ 接口请求失败 (HTTP {resp.status})"
            data = await resp.json(content_type=None)

        img_url = data.get("image_url_4k")
        if not img_url:
            return False, "", "❌ 未找到高清图片地址。"

        info_text = (
            f"🖼️ 必应每日壁纸 | {data.get('date')}\n"
            f"━━━━━━━━━━━━━━\n"
            f"✨ 主题：{data.get('title')}\n"
            f"📝 故事：{data.get('description', '暂无详细描述')}\n\n"
            f"©️ 版权：{data.get('copyright')}"
        )

        async with session.get(img_url, timeout=40) as img_resp:
            if img_resp.status == 200:
                img_data = await img_resp.read()
                
                fd, path = tempfile.mkstemp(suffix=".jpg", prefix="bing_")
                try:
                    with os.fdopen(fd, 'wb') as f:
                        f.write(img_data)
                finally:
                    del img_data
                
                return True, path, info_text

            return False, "", f"❌ 原图下载失败 (HTTP {img_resp.status})"

    except asyncio.TimeoutError:
        logger.warning("[UApiPro] 必应图片下载超时。")
        return False, "", "⚠️ 4K 图片下载超时，请稍后再试。"
    except Exception as e:
        err_type = e.__class__.__name__
        logger.warning(f"[UApiPro] 必应壁纸异常 ({err_type}): {e}")
        return False, "", "⚠️ 网络连接失败，请检查网络。"
    finally:
        if local_session:
            await session.close()
