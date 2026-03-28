"""
apis/mcquery.py

"""
import aiohttp
import re
import ipaddress
from ..card_renderer import render_card

# 完整 API 地址：https://uapis.cn/api/v1/game/minecraft/serverstatus
API_URL = "https://uapis.cn/api/v1/game/minecraft/serverstatus"

async def fetch(server: str, token: str):
    """
    查询 Minecraft Java 版服务器实时状态
    """
    # 1. 基础格式校验 (允许字母、数字、点、横杠，以及可选的端口)
    if not re.match(r'^[a-zA-Z0-9.\-]+(:\d{1,5})?$', server):
        return False, "", "❌ 服务器地址格式不合法"

    # 2. SSRF 深度检查：拦截私有/保留 IP 网段
    host = server.split(':')[0]
    try:
        # 尝试将输入解析为 IP 对象
        ip_obj = ipaddress.ip_address(host)
        
        # 检查是否属于受限网段
        if (ip_obj.is_private or      # 私有地址
            ip_obj.is_loopback or     # 回环地址
            ip_obj.is_link_local or   # 链路本地
            ip_obj.is_multicast or    # 组播地址
            ip_obj.is_reserved or     # 保留地址
            ip_obj.is_unspecified):   # 未指定地址
            return False, "", "❌ 禁止查询内网或受限网段地址"
            
    except ValueError:
        # 如果不是合法的 IP 格式，说明它是域名，此处放行
        pass

    # 构造参数与增强 Header 鉴权，确保后台计费统计
    params = {"server": server, "token": token}
    headers = {
        "User-Agent": "AstrBot_UApiPro",
        "Token": token,                  # 方案 A
        "Authorization": f"Bearer {token}" # 方案 B
    }

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            # 接口文档定义方法为 GET
            async with session.get(API_URL, params=params, timeout=12) as resp:
                
                try:
                    data = await resp.json(content_type=None)
                except:
                    data = {}
                
                # 1. 处理请求成功 (200) 且服务器在线
                if resp.status == 200 and data.get("online"):
                    # 提取图标 (favicon_url 为 Base64 Data URI)
                    favicon = data.get("favicon_url", "")
                    
                    fields = [
                        ("服务器地址", server),
                        ("在线人数", f"{data.get('players')} / {data.get('max_players')}"),
                        ("游戏版本", data.get("version", "未知")),
                        ("解析 IP", f"{data.get('ip')}:{data.get('port')}")
                    ]
                    
                    if favicon:
                        fields.insert(0, ("服务器图标", favicon))
                        
                    # 提取纯文本格式的 MOTD，去除换行
                    motd = data.get("motd_clean", "").strip().replace("\n", " ")
                    fields.append(("服务器介绍", motd))

                    html = render_card("Minecraft 服务器状态", "🎮", fields, "#5CB85C")
                    return True, html, ""
                
                # 2. 处理请求失败，保留原始中文报错逻辑
                # 文档 404 为地址无法解析或服务器离线
                api_msg = data.get("message")
                if resp.status == 404:
                    return False, "", f"❌ 未找到服务器: {api_msg or '地址无法解析或处于离线状态'}"
                elif resp.status == 400:
                    return False, "", f"❌ 参数错误: {api_msg or '未提供服务器地址'}"
                
                # 兜底返回 API 提供的错误信息
                err_msg = api_msg or "服务器离线或解析失败"
                return False, "", f"❌ {err_msg}"

    except Exception as e:
        # 保持原始网络报错
        return False, "", f"⚠️ 网络连接异常: {str(e)}"