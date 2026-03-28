"""
apis/ipquery.py
IP 归属地查询接口 - 标准数据源版 (UApiPro V1)
"""

import aiohttp
from ..card_renderer import render_card

API_URL = "https://uapis.cn/api/v1/network/ipinfo"

async def fetch(ip: str, token: str):
    """
    查询 IP 或域名的地理位置信息
    返回: (bool 成功, str HTML内容, str 错误信息)
    """
    if not ip or len(ip.strip()) == 0:
        return False, "", "❌ 请输入要查询的 IP 地址或域名。"

    # 默认留空 source，使用标准数据库，响应更快
    params = {"ip": ip}
    headers = {"User-Agent": "AstrBot_UApiPro"}
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(API_URL, params=params, timeout=8) as resp:
                
                try:
                    data = await resp.json(content_type=None)
                except:
                    data = {}

                # 1. 处理请求成功 (200)
                if resp.status == 200:
                    query_ip = data.get("ip", ip)
                    if not query_ip:
                        return False, "", "❌ API 未返回有效的 IP 数据。"

                    # 基础字段：归属地与运营商
                    region = data.get("region", "未知位置")
                    isp = data.get("isp", "--")
                    
                    fields = [
                        ("查询目标", query_ip),
                        ("地理位置", f"📍 {region}"),
                        ("运营商", f"🏢 {isp}"),
                        ("ASN 编号", f"🔢 {data.get('asn', '--')}")
                    ]
                    
                    # 标准源特有字段：IP 段信息
                    begin_ip = data.get("beginip")
                    end_ip = data.get("endip")
                    if begin_ip and end_ip:
                        fields.append(("所属 IP 段", f"📶 {begin_ip} ~ {end_ip}"))

                    # 坐标信息
                    lat, lon = data.get("latitude"), data.get("longitude")
                    if lat and lon:
                        fields.append(("地理坐标", f"🌐 {lat}, {lon}"))

                    html = render_card("IP 归属地查询", "🌐", fields, "#4E73DF")
                    return True, html, ""

                # 2. 处理请求失败 (400, 404, 500)
                api_msg = data.get("message")
                
                if resp.status == 404:
                    return False, "", f"❌ 未找到信息: {api_msg or '该 IP 可能是内网地址或尚未分配'}"
                elif resp.status == 400:
                    return False, "", f"❌ 格式错误: {api_msg or '请检查 IP 或域名格式是否正确'}"
                elif api_msg:
                    return False, "", f"❌ 查询失败: {api_msg}"
                else:
                    return False, "", f"❌ 接口响应异常 (HTTP {resp.status})"

    except Exception as e:
        return False, "", f"⚠️ 网络连接失败: {str(e)}"