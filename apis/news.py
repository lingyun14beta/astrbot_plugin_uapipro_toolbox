"""
apis/news.py
每日新闻图接口 - 适配 V1 协议与实时渲染逻辑
"""

import aiohttp
import tempfile
import os

API_URL = "https://uapis.cn/api/v1/daily/news-image"

async def fetch(token: str = ""):
    """
    获取每日新闻摘要图片
    返回: (bool 成功, str 图片路径, str 错误信息)
    """
    # 根据文档建议，渲染耗时较长，超时需设在 10s 以上
    timeout = aiohttp.ClientTimeout(total=20)
    headers = {
        "User-Agent": "AstrBot_UApiPro",
    }
    
    # 如果你的 API 需要 Token，根据实际情况添加（文档虽未详写，但 V1 协议通常支持）
    params = {"token": token} if token else {}

    try:
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.get(API_URL, params=params) as resp:
                
                content_type = resp.headers.get("Content-Type", "").lower()

                # 1. 处理请求成功 (直接返回二进制图片)
                if resp.status == 200 and "image" in content_type:
                    image_data = await resp.read()
                    
                    if not image_data:
                        return False, "", "❌ API 返回了空的图片内容"

                    # 创建临时文件保存 JPEG
                    fd, temp_path = tempfile.mkstemp(suffix=".jpg", prefix="uapi_news_")
                    try:
                        with os.fdopen(fd, 'wb') as f:
                            f.write(image_data)
                        return True, temp_path, ""
                    except Exception as fe:
                        return False, "", f"❌ 文件写入失败: {str(fe)}"

                # 2. 处理请求失败 (500, 502 等 JSON 报错)
                try:
                    res_json = await resp.json(content_type=None)
                    api_msg = res_json.get("message", "未知错误")
                except:
                    api_msg = f"HTTP {resp.status}"

                if resp.status == 500:
                    return False, "", f"❌ 渲染失败: {api_msg} (服务器渲染引擎故障)"
                elif resp.status == 502:
                    return False, "", f"❌ 抓取失败: {api_msg} (新闻源响应异常，请稍后重试)"
                else:
                    return False, "", f"❌ 接口请求失败: {api_msg}"

    except Exception as e:
        # 针对超时的友好提示
        err_str = str(e).lower()
        if "timeout" in err_str:
            return False, "", "⚠️ 新闻生成超时（图片渲染较慢），请稍后再试。"
        return False, "", f"⚠️ 网络异常: {str(e)}"