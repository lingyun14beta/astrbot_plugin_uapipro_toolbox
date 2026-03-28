import aiohttp
from ..card_renderer import render_card

API_URL = "https://uapis.cn/api/v1/network/ipinfo"

async def fetch(ip: str, token: str):
    """
    查询 IP 或域名的地理位置信息
    """
    if not ip or len(ip.strip()) == 0:
        return False, "", "❌ 请输入要查询的 IP 地址或域名。"

    # 构造请求参数，包含 token 以确保计费
    params = {"ip": ip, "token": token}
    
    # 增强 Header 鉴权，确保后台能记录调用
    headers = {
        "User-Agent": "AstrBot_UApiPro",
        "Token": token,
        "Authorization": f"Bearer {token}"
    }
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(API_URL, params=params, timeout=8) as resp:
                try:
                    data = await resp.json(content_type=None)
                except:
                    data = {}

                # 1. 处理请求成功 (200)
                if resp.status == 200:
                    fields = [
                        ("查询目标", data.get("ip", ip)),
                        ("地理位置", f"📍 {data.get('region', '未知位置')}"),
                        ("运营商", f"🏢 {data.get('isp', '--')}"),
                        ("归属机构", f"🏢 {data.get('llc', '--')}"), # 新增文档字段
                        ("ASN 编号", f"🔢 {data.get('asn', '--')}")
                    ]
                    
                    # 坐标信息
                    lat = data.get("latitude")
                    lon = data.get("longitude")
                    if lat and lon:
                        fields.append(("地理坐标", f"🌐 {lat}, {lon}"))
                    
                    # IP 段信息 (标准查询特有)
                    begin = data.get("beginip")
                    end = data.get("endip")
                    if begin and end:
                        fields.append(("所属网段", f"📶 {begin} ~ {end}"))

                    html = render_card("IP 归属地查询", "🌐", fields, "#4E73DF")
                    return True, html, ""

                # 2. 处理请求失败，保留原始中文错误输出
                api_msg = data.get("message")
                
                if resp.status == 404:
                    return False, "", f"❌ 未找到信息: {api_msg or '该 IP 可能是内网地址或尚未分配'}"
                elif resp.status == 400:
                    return False, "", f"❌ 格式错误: {api_msg or '请检查 IP 或域名格式是否正确'}"
                elif resp.status == 500:
                    return False, "", f"❌ 服务器内部错误: {api_msg or 'IP查询服务暂时不可用'}"
                
                return False, "", f"❌ 查询失败: {api_msg or f'HTTP {resp.status}'}"

    except Exception as e:
        # 保留原始网络报错
        return False, "", f"⚠️ 网络连接失败: {str(e)}"