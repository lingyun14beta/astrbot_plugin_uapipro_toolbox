"""
apis/hitokoto.py
一言（语录）接口 
"""

import aiohttp
from ..card_renderer import render_card

# 接口完整地址：https://uapis.cn/api/v1/saying
API_URL = "https://uapis.cn/api/v1/saying"

async def fetch(token: str = ""):
    """
    随机获取一条名言、诗词或动漫台词
    返回: (bool 成功, str HTML内容, str 错误信息)
    """
    # 保持 URL 参数传递 token
    params = {"token": token} if token else {}
    
    headers = {
        "User-Agent": "AstrBot_UApiPro",
        "Token": token,
        "Authorization": f"Bearer {token}"
    }

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            # 接口文档定义方法为 GET
            async with session.get(API_URL, params=params, timeout=8) as resp:
                
                try:
                    data = await resp.json(content_type=None)
                except:
                    data = {}

                # 1. 处理请求成功 (200)
                if resp.status == 200:
                    # 文档响应字段为 text
                    content = data.get("text", "").strip()
                    if not content:
                        # 保持原始报错逻辑
                        return False, "", "❌ API 未返回任何语录内容。"
                    
                    # 渲染
                    fields = [
                        ("今日语录", content)
                    ]
                    
                    html = render_card("今日一言", "✨", fields, "#7C83FD")
                    return True, html, ""

                # 2. 处理请求失败 (保留你原始的 500 逻辑与中文输出)
                api_msg = data.get("message")
                
                if resp.status == 500:
                    # 文档定义 500 为语料库为空或无法读取
                    return False, "", f"❌ 语料库异常: {api_msg or '无法读取语录数据，请稍后再试'}"
                elif api_msg:
                    return False, "", f"❌ 查询失败: {api_msg}"
                else:
                    return False, "", f"❌ 接口响应异常 (HTTP {resp.status})"

    except Exception as e:
        # 保持原始网络报错信息
        return False, "", f"⚠️ 网络连接失败: {str(e)}"