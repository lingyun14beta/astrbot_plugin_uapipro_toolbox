import aiohttp
from astrbot.api import logger
from ..card_renderer import render_card

API_URL = "https://uapis.cn/api/v1/misc/weather"

async def fetch(city: str, token: str, session: aiohttp.ClientSession = None):
    logger.debug(f"[UApiPro] Weather Query: city={city} token={token}")
    params = {"token": token, "city": city, "extended": "true", "indices": "true", "forecast": "true", "minutely": "true", "lang": "zh"}
    headers = {"User-Agent": "AstrBot_UApiPro", "Token": token, "Authorization": f"Bearer {token}"}

    local_session = False
    if session is None:
        session = aiohttp.ClientSession(headers=headers)
        local_session = True

    try:
        async with session.get(API_URL, params=params, timeout=10) as resp:
            try:
                res_json = await resp.json(content_type=None)
            except Exception: 
                res_json = {}

            if not isinstance(res_json, dict):
                res_json = {}

            if resp.status == 200:
                data = res_json
                location = f"{data.get('province', '')}{data.get('city', '')}{data.get('district', '')}"
                if not location: 
                    location = city or "自动定位"
                fields = [
                    ("地理位置", location),
                    ("实时天气", f"{data.get('weather', '--')} | {data.get('temperature', '--')}°C (体感 {data.get('feels_like', '--')}°C)"),
                    ("今日温差", f"最低 {data.get('temp_min', '--')}°C ~ 最高 {data.get('temp_max', '--')}°C"),
                    ("空气质量", f"{data.get('aqi_category', '--')} (AQI: {data.get('aqi', '--')})"),
                    ("降水预报", data.get('minutely_precip', {}).get('summary', '无降水数据')),
                    ("风力湿度", f"{data.get('wind_direction', '')}{data.get('wind_power', '--')} | 湿度 {data.get('humidity', '--')}%"),
                    ("紫外线", f"指数: {data.get('uv', '--')}"),
                    ("生活建议", data.get('life_indices', {}).get('clothing', {}).get('advice', '暂无建议')),
                    ("更新时间", data.get("report_time", "--")[-8:])
                ]
                html = render_card(f"{data.get('city', '天气')} 报告", "🌤️", fields, "#4AAFDB")
                return True, html, ""

            api_err_msg = res_json.get("message")
            if api_err_msg: 
                return False, "", f"天气查询失败: {api_err_msg}"
            if resp.status == 404: 
                return False, "", "❌ 未找到该城市，请检查城市名是否正确。"
            if resp.status == 400: 
                return False, "", "❌ 请求参数错误，请稍后再试。"
            return False, "", f"❌ 接口响应异常 (HTTP {resp.status})"
    except Exception as e: 
        return False, "", f"⚠️ 网络连接失败: {str(e)}"
    finally:
        if local_session: 
            await session.close()
