import aiohttp
import tempfile
import os

API_URL = "https://uapis.cn/api/v1/random/image"

async def fetch(category: str = None, img_type: str = None, token: str = "", session: aiohttp.ClientSession = None):
    headers = {"User-Agent": "AstrBot_UApiPro", "Token": token, "Authorization": f"Bearer {token}"}
    params = {k: v for k, v in {"category": category, "type": img_type, "token": token}.items() if v}
    
    local_session = False
    if session is None:
        session = aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=15))
        local_session = True

    try:
        async with session.get(API_URL, params=params) as resp:
            content_type = resp.headers.get("Content-Type", "").lower()
            
            if resp.status == 200 and "image" in content_type:
                image_data = await resp.read()
                if not image_data:
                    return False, "", "❌ API 返回了空的图片内容"

                fd, temp_path = tempfile.mkstemp(suffix=".jpg", prefix="uapi_img_")
                with os.fdopen(fd, 'wb') as f:
                    f.write(image_data)
                return True, temp_path, ""

            try:
                res_json = await resp.json(content_type=None)
                api_msg = res_json.get("message", "未知错误")
            except Exception:
                api_msg = f"HTTP {resp.status}"

            if resp.status == 404:
                return False, "", f"❌ 未找到图片: {api_msg} (请检查分类名是否正确)"
            elif resp.status == 500:
                return False, "", f"❌ 服务器错误: {api_msg} (选图逻辑异常)"
            else:
                return False, "", f"❌ 接口请求失败: {api_msg}"
    except Exception as e:
        return False, "", f"⚠️ 网络异常: {str(e)}"
    finally:
        if local_session: await session.close()
