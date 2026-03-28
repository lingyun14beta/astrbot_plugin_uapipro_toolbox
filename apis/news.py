import aiohttp
import tempfile
import os
import asyncio

API_URL = "https://uapis.cn/api/v1/daily/news-image"

async def fetch(token: str = "", session: aiohttp.ClientSession = None):
    headers = {"User-Agent": "AstrBot_UApiPro", "Token": token, "Authorization": f"Bearer {token}"}
    params = {"token": token} if token else {}

    local_session = False
    if session is None:
        session = aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=25))
        local_session = True

    try:
        async with session.get(API_URL, params=params) as resp:
            content_type = resp.headers.get("Content-Type", "").lower()

            if resp.status == 200 and "image" in content_type:
                image_data = await resp.read()
                if not image_data:
                    return False, "", "❌ API 返回了空的图片内容"

                fd, temp_path = tempfile.mkstemp(suffix=".jpg", prefix="uapi_news_")
                with os.fdopen(fd, 'wb') as f:
                    f.write(image_data)
                return True, temp_path, ""

            try:
                res_json = await resp.json(content_type=None)
                api_msg = res_json.get("message", "未知错误")
            except Exception:
                api_msg = f"HTTP {resp.status}"

            if resp.status == 500:
                return False, "", f"❌ 渲染失败: {api_msg} (服务器渲染引擎故障)"
            elif resp.status == 502:
                return False, "", f"❌ 抓取失败: {api_msg} (新闻源响应异常，请稍后重试)"
            else:
                return False, "", f"❌ 接口请求失败: {api_msg}"

    except Exception as e:
        # 保持原始超时判断逻辑
        err_str = str(e).lower()
        if "timeout" in err_str:
            return False, "", "⚠️ 新闻生成超时（图片渲染较慢），请稍后再试。"
        return False, "", f"⚠️ 网络异常: {str(e)}"
    finally:
        if local_session: await session.close()
