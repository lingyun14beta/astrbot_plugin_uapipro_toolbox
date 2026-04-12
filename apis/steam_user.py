import aiohttp
import base64
import re
from astrbot.api import logger
from ..card_renderer import render_card

API_URL = "https://uapis.cn/api/v1/game/steam/summary"


async def fetch(arg_str: str, token: str, session: aiohttp.ClientSession = None):
    """
    Steam 用户资料查询模块
    """
    usage_hint = (
        "🎮 Steam 查询规范：\n"
        "━━━━━━━━━━━━━━\n"
        "用法：/u steam <ID/链接/代码>\n"
        "示例：/u steam gabelogannewell"
    )

    identifier = arg_str.strip()
    if not identifier:
        return False, "", usage_hint

    # 安全加固：限制输入长度，防止恶意超长字符串注入
    if len(identifier) > 100:
        return False, "", "❌ 输入内容过长，请检查 Steam ID 是否正确。"

    STATE_MAP = {0: "离线", 1: "在线", 2: "忙碌", 3: "离开", 4: "打盹", 5: "想交易", 6: "想玩"}
    VIS_MAP = {1: "私密 (Private)", 3: "公开 (Public)"}

    params = {"steamid": identifier}
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
        async with session.get(API_URL, params=params, timeout=12) as resp:
            try:
                data = await resp.json(content_type=None)
            except Exception:
                data = {}

            if resp.status == 200:
                name = data.get("personaname", "未知用户")
                avatar_url = data.get("avatarfull")
                
                p_state = STATE_MAP.get(data.get("personastate"), "未知")
                v_state = VIS_MAP.get(data.get("communityvisibilitystate"), "未知")
                
                display_avatar = ""
                # 安全审计：SSRF 白名单过滤 (Steam 官方域名)
                steam_cdn_pattern = r'^https://([^/]*\.steamstatic\.com|steamcdn-a\.akamaihd\.net)/'
                
                if avatar_url and re.match(steam_cdn_pattern, avatar_url):
                    try:
                        async with session.get(avatar_url, timeout=5) as img_resp:
                            if img_resp.status == 200:
                                img_data = await img_resp.read()
                                display_avatar = f"data:image/jpeg;base64,{base64.b64encode(img_data).decode()}"
                                del img_data
                    except Exception:
                        pass

                fields = [
                    ("基本资料", f"👤 昵称: {name}\n🆔 ID: {data.get('steamid', '--')}\n🏷️ 姓名: {data.get('realname', '未公开')}"),
                    ("账户状态", f"🔐 可见性: {v_state}\n🌐 在线状态: {p_state}"),
                    ("其他信息", f"📅 注册时间: {data.get('timecreated_str', '未公开')}\n🌍 国家: {data.get('loccountrycode', '未公开')}")
                ]

                if display_avatar:
                    fields.insert(0, ("用户头像", display_avatar))
                
                fields.append(("个人主页", data.get("profileurl", "无")))

                html = render_card(f"{name} 的 Steam 档案", "🎮", fields, "#171A21")
                return True, html, ""

            api_msg = str(data.get("message", "查询失败"))[:100]
            if resp.status == 404:
                return False, "", "❌ 用户未找到：该 ID 可能无效或资料为完全私密状态。"
            return False, "", f"❌ 接口请求失败: {api_msg}"

    except Exception as e:
        logger.warning(f"[UApiPro] Steam 查询异常: {e}")
        return False, "", "⚠️ 网络连接失败，请稍后再试。"
    finally:
        if local_session:
            await session.close()