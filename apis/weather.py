"""
apis/weather.py
天气查询接口 - 深度适配 UApiPro V1 协议
"""

import aiohttp
from ..card_renderer import render_card

API_URL = "https://uapis.cn/api/v1/misc/weather"

async def fetch(city: str, token: str):
    # 如果没传城市，API 支持自动 IP 定位，但插件逻辑通常建议传参
    params = {
        "city": city,
        "extended": "true",  # 开启空气质量、体感温度
        "indices": "true",   # 开启生活指数
        "forecast": "true",  # 获取当日最高/最低温
        "minutely": "true",  # 分钟级降水预报
        "lang": "zh"
    }
    
    headers = {"User-Agent": "AstrBot_UApiPro"}

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(API_URL, params=params, timeout=10) as resp:
                
                try:
                    res_json = await resp.json(content_type=None)
                except:
                    res_json = {}

                # 1. 处理成功响应
                if resp.status == 200:
                    data = res_json
                    
                    # 组合地理位置 (省+市+区)
                    location = f"{data.get('province', '')}{data.get('city', '')}{data.get('district', '')}"
                    if not location: location = city or "自动定位"

                    # 基础信息
                    weather = data.get('weather', '--')
                    temp = data.get('temperature', '--')
                    feels = data.get('feels_like', '--')
                    
                    # 预报温差 (来自 forecast=true)
                    t_max = data.get('temp_max', '--')
                    t_min = data.get('temp_min', '--')

                    # 降水预报 (来自 minutely=true)
                    precip_summary = data.get('minutely_precip', {}).get('summary', '无降水数据')

                    # 生活指数 (来自 indices=true) - 选取最实用的穿衣建议
                    clothing = data.get('life_indices', {}).get('clothing', {})
                    advice = clothing.get('advice', '暂无建议')

                    fields = [
                        ("地理位置", location),
                        ("实时天气", f"{weather} | {temp}°C (体感 {feels}°C)"),
                        ("今日温差", f"最低 {t_min}°C ~ 最高 {t_max}°C"),
                        ("空气质量", f"{data.get('aqi_category', '--')} (AQI: {data.get('aqi', '--')})"),
                        ("降水预报", precip_summary),
                        ("风力湿度", f"{data.get('wind_direction', '')}{data.get('wind_power', '--')} | 湿度 {data.get('humidity', '--')}%"),
                        ("紫外线", f"指数: {data.get('uv', '--')}"),
                        ("生活建议", advice),
                        ("更新时间", data.get("report_time", "--")[-8:]) # 仅截取时间部分
                    ]

                    html = render_card(f"{data.get('city', '天气')} 报告", "🌤️", fields, "#4AAFDB")
                    return True, html, ""

                # 2. 处理文档定义的错误 (400, 404, 500, 503)
                # 优先返回 API 文档中提供的 message 字段
                api_err_msg = res_json.get("message")
                if api_err_msg:
                    return False, "", f"天气查询失败: {api_err_msg}"
                
                # 回退处理
                if resp.status == 404: return False, "", "❌ 未找到该城市，请检查城市名是否正确。"
                if resp.status == 400: return False, "", "❌ 请求参数错误，请稍后再试。"
                return False, "", f"❌ 接口响应异常 (HTTP {resp.status})"

    except Exception as e:
        return False, "", f"⚠️ 网络连接失败: {str(e)}"