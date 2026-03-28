"""
apis/random_img.py
随机图片接口 - 适配 V1 协议与重定向图流处理
"""

import aiohttp
import tempfile
import os

API_URL = "https://uapis.cn/api/v1/random/image"

async def fetch(category: str = None, img_type: str = None, token: str = ""):
    """
    获取随机图片
    category: 主分类 (如 acg, bq, furry, landscape 等)
    img_type: 子分类 (如 pc, mb, ikun 等)
    """
    headers = {"User-Agent": "AstrBot_UApiPro"}
    
    # 构造参数：过滤掉空值
    params = {}
    if category: params["category"] = category
    if img_type: params["type"] = img_type
    if token: params["token"] = token
    
    try:
        # 随机图片可能涉及重定向或大图加载，设置 15s 超时
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.get(API_URL, params=params) as resp:
                
                content_type = resp.headers.get("Content-Type", "").lower()
                
                # 1. 处理请求成功 (直接返回二进制图片流)
                if resp.status == 200 and "image" in content_type:
                    image_data = await resp.read()
                    
                    if not image_data:
                        return False, "", "❌ API 返回了空的图片内容"

                    # 创建临时文件保存
                    fd, temp_path = tempfile.mkstemp(suffix=".jpg", prefix="uapi_img_")
                    try:
                        with os.fdopen(fd, 'wb') as f:
                            f.write(image_data)
                        return True, temp_path, ""
                    except Exception as fe:
                        return False, "", f"❌ 图片保存失败: {str(fe)}"

                # 2. 处理请求失败 (404, 500 等 JSON 报错)
                try:
                    res_json = await resp.json(content_type=None)
                    api_msg = res_json.get("message", "未知错误")
                except:
                    api_msg = f"HTTP {resp.status}"

                if resp.status == 404:
                    return False, "", f"❌ 未找到图片: {api_msg} (请检查分类名是否正确)"
                elif resp.status == 500:
                    return False, "", f"❌ 服务器错误: {api_msg} (选图逻辑异常)"
                else:
                    return False, "", f"❌ 接口请求失败: {api_msg}"

    except Exception as e:
        return False, "", f"⚠️ 网络异常: {str(e)}"