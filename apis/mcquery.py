import aiohttp
import re
import ipaddress
import socket
import asyncio
from astrbot.api import logger
from ..card_renderer import render_card

API_URL = "https://uapis.cn/api/v1/game/minecraft/serverstatus"


async def fetch(server: str, token: str, session: aiohttp.ClientSession = None):
    """
    Minecraft 服务器状态查询模块
    """
    if not re.match(r'^[a-zA-Z0-9.\-]+(:\d{1,5})?$', server):
        return False, "", "❌ 服务器地址格式不合法。"

    # 1. 安全预检
    host = server.split(':')[0]
    try:
        loop = asyncio.get_event_loop()
        resolved_ip = await loop.run_in_executor(None, socket.gethostbyname, host)
        ip_obj = ipaddress.ip_address(resolved_ip)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved:
            return False, "", "❌ 安全拦截：禁止查询受限网段地址。"
    except Exception:
        pass

    params = {"server": server}
    local_session = False
    if session is None:
        headers = {"User-Agent": "AstrBot_UApiPro"}
        if token:
            headers["Token"] = token
            headers["Authorization"] = f"Bearer {token}"
        session = aiohttp.ClientSession(headers=headers)
        local_session = True

    try:
        async with session.get(API_URL, params=params, timeout=15) as resp:
            try:
                data = await resp.json(content_type=None)
            except Exception:
                data = {}

            if resp.status == 200 and data.get("online"):
                # 提取数据
                players_online = data.get("players", 0)
                players_max = data.get("max_players", 0)
                version = data.get("version", "未知版本")
                motd = data.get("motd_clean", "无服务器介绍").strip().replace("\n", " ")
                favicon = data.get("favicon_url")

                fields = [
                    ("服务器信息", f"🌐 地址: {server}\n⚙️ 版本: {version}"),
                    ("在线状态", f"👥 玩家: {players_online} / {players_max}\n📍 解析 IP: {data.get('ip')}:{data.get('port')}"),
                    ("服务器介绍", motd[:150])
                ]

                # 处理在线玩家列表 (如果有且存在)
                player_list = data.get("online_players", [])
                if player_list and isinstance(player_list, list):
                    names = [p.get("name") for p in player_list if p.get("name")][:8]
                    if names:
                        fields.append(("在线玩家预览", "👤 " + ", ".join(names)))

                # 插入图标 (API 已返回 Base64 格式)
                if favicon and favicon.startswith("data:image/"):
                    fields.insert(0, ("服务器图标", favicon))

                html = render_card("Minecraft 服务器状态", "🎮", fields, "#5CB85C")
                return True, html, ""

            # 处理文档定义的错误
            api_msg = str(data.get("message", "服务器离线或解析失败"))[:100]
            if resp.status == 404:
                return False, "", "❌ 未找到服务器：地址无法解析或处于离线状态。"
            elif resp.status == 502:
                return False, "", "❌ 接口查询失败：尝试连接目标服务器时发生错误。"
            return False, "", f"❌ 查询失败：{api_msg}"

    except asyncio.TimeoutError:
        return False, "", "⚠️ 查询超时：目标服务器响应缓慢。"
    except Exception as e:
        logger.warning(f"[UApiPro] MC查询异常: {e}")
        return False, "", "⚠️ 网络连接异常，请检查机器人网络。"
    finally:
        if local_session:
            await session.close()