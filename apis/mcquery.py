import aiohttp
import re
import ipaddress
import socket
import asyncio
from ..card_renderer import render_card

API_URL = "https://uapis.cn/api/v1/game/minecraft/serverstatus"

async def fetch(server: str, token: str, session: aiohttp.ClientSession = None):
    if not re.match(r'^[a-zA-Z0-9.\-]+(:\d{1,5})?$', server):
        return False, "", "❌ 服务器地址格式不合法"

    host = server.split(':')[0]
    try:
        loop = asyncio.get_event_loop()
        resolved_ip = await loop.run_in_executor(None, socket.gethostbyname, host)
        ip_obj = ipaddress.ip_address(resolved_ip)
        if (ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved or ip_obj.is_unspecified):
            return False, "", "❌ 禁止查询内网或受限网段地址"
    except (socket.gaierror, ValueError):
        return False, "", "❌ 无法解析服务器地址，请检查输入"

    params = {"server": server, "token": token}
    headers = {"User-Agent": "AstrBot_UApiPro", "Token": token, "Authorization": f"Bearer {token}"}

    local_session = False
    if session is None:
        session = aiohttp.ClientSession(headers=headers)
        local_session = True

    try:
        async with session.get(API_URL, params=params, timeout=12) as resp:
            try:
                data = await resp.json(content_type=None)
            except Exception: data = {}
            
            if resp.status == 200 and data.get("online"):
                favicon = data.get("favicon_url", "")
                fields = [
                    ("服务器地址", server),
                    ("在线人数", f"{data.get('players')} / {data.get('max_players')}"),
                    ("游戏版本", data.get("version", "未知")),
                    ("解析 IP", f"{data.get('ip')}:{data.get('port')}")
                ]
                if favicon: fields.insert(0, ("服务器图标", favicon))
                motd = data.get("motd_clean", "").strip().replace("\n", " ")
                fields.append(("服务器介绍", motd))

                html = render_card("Minecraft 服务器状态", "🎮", fields, "#5CB85C")
                return True, html, ""
            
            api_msg = data.get("message")
            if resp.status == 404: return False, "", f"❌ 未找到服务器: {api_msg or '地址无法解析或处于离线状态'}"
            elif resp.status == 400: return False, "", f"❌ 参数错误: {api_msg or '未提供服务器地址'}"
            return False, "", f"❌ {api_msg or '服务器离线或解析失败'}"
    except asyncio.TimeoutError: return False, "", "⚠️ 查询超时，服务器响应过慢"
    except Exception as e: return False, "", f"⚠️ 网络连接异常: {str(e)}"
    finally:
        if local_session: await session.close()
