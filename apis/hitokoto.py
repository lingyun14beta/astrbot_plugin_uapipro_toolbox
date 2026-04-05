import aiohttp
from ..card_renderer import render_card

API_URL = "https://uapis.cn/api/v1/saying"

async def fetch(token: str = "", session: aiohttp.ClientSession = None):
    params = {"token": token} if token else {}
    headers = {"User-Agent": "AstrBot_UApiPro", "Token": token, "Authorization": f"Bearer {token}"}

    local_session = False
    if session is None:
        session = aiohttp.ClientSession(headers=headers)
        local_session = True

    try:
        async with session.get(API_URL, params=params, timeout=8) as resp:
            try:
                data = await resp.json(content_type=None)
            except Exception: 
                data = {}

            if resp.status == 200:
                content = data.get("text", "").strip()
                if not content: 
                    return False, "", "❌ API 未返回任何语录内容。"
                fields = [("今日语录", content)]
                html = render_card("今日一言", "✨", fields, "#7C83FD")
                return True, html, ""

            api_msg = data.get("message")
            if resp.status == 500:
                return False, "", f"❌ 语料库异常: {api_msg or '无法读取语录数据，请稍后再试'}"
            elif api_msg:
                return False, "", f"❌ 查询失败: {api_msg}"
            else:
                return False, "", f"❌ 接口响应异常 (HTTP {resp.status})"
    except Exception as e: 
        return False, "", f"⚠️ 网络连接失败: {str(e)}"
    finally:
        if local_session: 
            await session.close()
