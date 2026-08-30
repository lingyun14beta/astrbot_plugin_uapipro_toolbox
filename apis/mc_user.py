import aiohttp
import base64
from astrbot.api import logger
from ..card_renderer import render_card

INFO_URL = "https://uapis.cn/api/v1/game/minecraft/userinfo"
HIST_URL = "https://uapis.cn/api/v1/game/minecraft/historyid"


async def fetch(arg_str: str, token: str, session: aiohttp.ClientSession = None):
    """
    Minecraft 玩家综合查询模块
    """
    usage_hint = (
        "🎮 MC 玩家查询规范：\n"
        "━━━━━━━━━━━━━━\n"
        "用法：/u mc玩家 [用户名]\n"
        "示例：/u mc玩家 Notch"
    )

    username = arg_str.strip()
    if not username:
        return False, "", usage_hint

    if len(username) > 20:
        return False, "", "❌ 用户名过长，MC 正版用户名最长 16 字符。"

    local_session = False
    if session is None:
        headers = {"User-Agent": "AstrBot_UApiPro"}
        if token:
            headers["Token"] = token
            headers["Authorization"] = f"Bearer {token}"
        session = aiohttp.ClientSession(headers=headers)
        local_session = True

    try:
        # 1. 获取基础资料
        async with session.get(INFO_URL, params={"username": username}, timeout=10) as resp:
            info_data = await resp.json(content_type=None) if resp.status == 200 else {}
            if resp.status == 404:
                return False, "", f"❌ 玩家未找到：未能找到名为 {username[:20]} 的玩家。"
            elif resp.status != 200:
                msg = str(info_data.get("message", "接口响应异常"))[:100]
                return False, "", f"❌ 查询失败: {msg}"

        uuid = info_data.get("uuid")
        real_name = info_data.get("username", username)
        skin_url = info_data.get("skin_url")

        # 2. 获取皮肤并转为 Base64 (防止渲染器缓存及访问受限)
        display_skin = "暂无皮肤数据"
        if skin_url:
            try:
                # 加入 no-cache 确保获取最新皮肤
                headers = {"Cache-Control": "no-cache"}
                async with session.get(skin_url, headers=headers, timeout=5) as img_resp:
                    if img_resp.status == 200:
                        img_data = await img_resp.read()
                        b64_str = base64.b64encode(img_data).decode()
                        display_skin = f"data:image/png;base64,{b64_str}"
                        del img_data # 显式释放大对象内存
                    else:
                        display_skin = skin_url
            except Exception as e:
                logger.warning(f"[UApiPro] 皮肤下载失败: {e}")
                display_skin = skin_url

        # 3. 获取曾用名
        history_text = "暂无更名记录"
        async with session.get(HIST_URL, params={"uuid": uuid}, timeout=10) as h_resp:
            if h_resp.status == 200:
                h_data = await h_resp.json(content_type=None)
                history_list = h_data.get("history", [])
                if history_list:
                    formatted_hist = [f"• {e.get('name')} ({e.get('changedToAt', '初始')})" for e in history_list]
                    history_text = "\n".join(formatted_hist[:10])
                    if len(history_list) > 10:
                        history_text += "\n..."

        fields = [
            ("玩家信息", f"👤 用户名: {real_name}\n🆔 UUID: {uuid}"),
            ("皮肤预览", display_skin),
            ("更名历史", history_text)
        ]

        html = render_card(f"{real_name} 的玩家档案", "🎮", fields, "#5CB85C")
        return True, html, ""

    except Exception as e:
        logger.warning(f"[UApiPro] MC 玩家查询异常: {e}")
        return False, "", "⚠️ 网络连接失败，请稍后再试。"
    finally:
        if local_session:
            await session.close()
