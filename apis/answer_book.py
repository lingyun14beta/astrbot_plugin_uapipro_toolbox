import aiohttp
from astrbot.api import logger
from ..card_renderer import render_card

API_URL = "https://uapis.cn/api/v1/answerbook/ask"


async def fetch(arg_str: str, token: str, session: aiohttp.ClientSession = None):
    """
    答案之书查询模块
    """
    usage_hint = (
        "📖 答案之书指令规范：\n"
        "━━━━━━━━━━━━━━\n"
        "用法：/u 答案之书 <你的问题>\n"
        "示例：/u 答案之书 我今年会有好运吗？"
    )

    question = arg_str.strip()
    if not question:
        return False, "", usage_hint

    if len(question) > 100:
        return False, "", "❌ 问题太长了，请精简到 100 字以内。"

    local_session = False
    if session is None:
        headers = {
            "User-Agent": "AstrBot_UApiPro",
            "Token": token,
            "Authorization": f"Bearer {token}"
        }
        session = aiohttp.ClientSession(headers=headers)
        local_session = True

    try:
        async with session.get(API_URL, params={"question": question}, timeout=10) as resp:
            try:
                data = await resp.json(content_type=None)
            except Exception:
                data = {}

            if resp.status == 200:
                answer = data.get("answer", "冥冥之中，自有天意。")
                fields = [
                    ("你的问题", question),
                    ("启示答案", f"✨ {answer}")
                ]
                # 神秘感配色：深紫色 (#6A5ACD)
                html = render_card("答案之书", "📖", fields, "#6A5ACD")
                return True, html, ""

            api_msg = str(data.get("message", "接口响应异常"))[:100]
            if resp.status == 400:
                return False, "", f"❌ 无效提问: {api_msg}\n\n{usage_hint}"
            return False, "", f"❌ 接口请求失败: {api_msg}"

    except Exception as e:
        logger.warning(f"[UApiPro] 答案之书异常: {e}")
        return False, "", "⚠️ 神秘力量中断了连接，请稍后再试。"
    finally:
        if local_session:
            await session.close()