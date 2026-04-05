import aiohttp
from ..card_renderer import render_card

API_URL = "https://uapis.cn/api/v1/network/ipinfo"

async def fetch(ip: str, token: str, session: aiohttp.ClientSession = None):
    if not ip or len(ip.strip()) == 0: 
        return False, "", "❌ 请输入要查询的 IP 地址或域名。"
    params = {"ip": ip, "token": token}
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
                fields = [
                    ("查询目标", data.get("ip", ip)),
                    ("地理位置", f"📍 {data.get('region', '未知位置')}"),
                    ("运营商", f"🏢 {data.get('isp', '--')}"),
                    ("归属机构", f"🏢 {data.get('llc', '--')}"),
                    ("ASN 编号", f"🔢 {data.get('asn', '--')}")
                ]
                lat, lon = data.get("latitude"), data.get("longitude")
                if lat and lon: 
                    fields.append(("地理坐标", f"🌐 {lat}, {lon}"))
                begin, end = data.get("beginip"), data.get("endip")
                if begin and end: 
                    fields.append(("所属网段", f"📶 {begin} ~ {end}"))

                html = render_card("IP 归属地查询", "🌐", fields, "#4E73DF")
                return True, html, ""

            api_msg = data.get("message")
            if resp.status == 404:
                return False, "", f"❌ 未找到信息: {api_msg or '该 IP 可能是内网地址或尚未分配'}"
            elif resp.status == 400:
                return False, "", f"❌ 格式错误: {api_msg or '请检查 IP 或域名格式是否正确'}"
            elif resp.status == 500:
                return False, "", f"❌ 服务器内部错误: {api_msg or 'IP查询服务暂时不可用'}"
            return False, "", f"❌ 查询失败: {api_msg or f'HTTP {resp.status}'}"
    except Exception as e: 
        return False, "", f"⚠️ 网络连接失败: {str(e)}"
    finally:
        if local_session: 
            await session.close()
