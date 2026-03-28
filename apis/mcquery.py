"""
apis/mcquery.py
安全加强版：增加 IP 归属地深度检查，彻底拦截 SSRF
"""
import aiohttp
import re
import ipaddress
from ..card_renderer import render_card

API_URL = "https://uapis.cn/api/v1/game/minecraft/serverstatus"

async def fetch(server: str, token: str):
    # 1. 基础格式校验 (允许字母、数字、点、横杠，以及可选的端口)
    if not re.match(r'^[a-zA-Z0-9.\-]+(:\d{1,5})?$', server):
        return False, "", "❌ 服务器地址格式不合法"

    # 2. SSRF 深度检查：拦截私有/保留 IP 网段
    host = server.split(':')[0]
    try:
        # 尝试将输入解析为 IP 对象
        ip_obj = ipaddress.ip_address(host)
        
        # 检查是否属于受限网段
        if (ip_obj.is_private or      # 私有地址 (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
            ip_obj.is_loopback or     # 回环地址 (127.0.0.1)
            ip_obj.is_link_local or   # 链路本地 (169.254.0.0/16)
            ip_obj.is_multicast or    # 组播地址
            ip_obj.is_reserved or     # 保留地址
            ip_obj.is_unspecified):   # 未指定地址 (0.0.0.0)
            return False, "", "❌ 禁止查询内网或受限网段地址"
            
    except ValueError:
        # 如果不是合法的 IP 格式，说明它是域名 (Domain Name)
        # 域名通常由上游 API 服务端进行解析，此处放行
        pass

    params = {"server": server}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL, params=params, timeout=12) as resp:
                data = await resp.json() if resp.status == 200 else {}
                
                if resp.status == 200 and data.get("online"):
                    favicon = data.get("favicon_url", "")
                    
                    fields = [
                        ("服务器地址", server),
                        ("在线人数", f"{data.get('players')} / {data.get('max_players')}"),
                        ("游戏版本", data.get("version", "未知")),
                        ("解析 IP", f"{data.get('ip')}:{data.get('port')}")
                    ]
                    
                    if favicon:
                        fields.insert(0, ("服务器图标", favicon))
                        
                    motd = data.get("motd_clean", "").strip().replace("\n", " ")
                    fields.append(("服务器介绍", motd))

                    html = render_card("Minecraft 服务器状态", "🎮", fields, "#5CB85C")
                    return True, html, ""
                
                msg = data.get("message", "服务器离线或解析失败")
                return False, "", f"❌ {msg}"
    except Exception as e:
        return False, "", "⚠️ 网络连接异常"