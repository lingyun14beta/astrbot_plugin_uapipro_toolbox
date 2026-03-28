"""
apis/hitokoto.py
一言（语录）接口 - UApiPro V1 协议适配版
"""

import aiohttp
from ..card_renderer import render_card

API_URL = "https://uapis.cn/api/v1/saying"

async def fetch(token: str = ""):
    """
    随机获取一条名言、诗词或动漫台词
    返回: (bool 成功, str HTML内容, str 错误信息)
    """
    headers = {"User-Agent": "AstrBot_UApiPro"}
    # 接口通常不需要 token，但 V1 协议支持通过 params 传递
    params = {"token": token} if token else {}

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(API_URL, params=params, timeout=8) as resp:
                
                try:
                    data = await resp.json(content_type=None)
                except:
                    data = {}

                # 1. 处理请求成功 (200)
                if resp.status == 200:
                    content = data.get("text", "").strip()
                    if not content:
                        return False, "", "❌ API 未返回任何语录内容。"
                    
                    # 渲染精美卡片
                    fields = [
                        ("今日语录", content)
                    ]
                    
                    html = render_card("今日一言", "✨", fields, "#7C83FD")
                    return True, html, ""

                # 2. 处理请求失败 (500 等)
                api_msg = data.get("message")
                
                if resp.status == 500:
                    return False, "", f"❌ 语料库异常: {api_msg or '无法读取语录数据，请稍后再试'}"
                elif api_msg:
                    return False, "", f"❌ 查询失败: {api_msg}"
                else:
                    return False, "", f"❌ 接口响应异常 (HTTP {resp.status})"

    except Exception as e:
        return False, "", f"⚠️ 网络连接失败: {str(e)}"