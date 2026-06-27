import aiohttp
import re
from astrbot.api import logger
from ..card_renderer import render_card

API_URL = "https://uapis.cn/api/v1/network/icp"


async def fetch(arg_str: str, token: str, session: aiohttp.ClientSession = None):
    """
    域名 ICP 备案查询模块
    """
    usage_hint = (
        "🔍 ICP 备案查询规范：\n"
        "━━━━━━━━━━━━━━\n"
        "用法：/u icp <域名>\n"
        "示例：/u icp baidu.com"
    )

    domain = arg_str.strip().lower()
    if not domain:
        return False, "", usage_hint

    # 安全加固：校验域名格式，防止注入或非法请求
    if not re.match(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.[a-z]{2,}$", domain):
        safe_domain = domain[:30]
        return False, "", f"❌ 域名格式错误：{safe_domain}\n\n{usage_hint}"

    params = {"domain": domain}
    local_session = False
    
    if session is None:
        headers = {
            "User-Agent": "AstrBot_UApiPro",
            "Token": token,
            "Authorization": f"Bearer {token}"
        }
        session = aiohttp.ClientSession(headers=headers)
        local_session = True

    try:
        async with session.get(API_URL, params=params, timeout=10) as resp:
            try:
                data = await resp.json(content_type=None)
            except Exception:
                data = {}

            if resp.status == 200:
                # 提取备案核心字段
                unit_name = data.get("unitName", "--")
                nature = data.get("natureName", "--")
                licence = data.get("serviceLicence", "--")
                res_domain = data.get("domain", domain)

                fields = [
                    ("查询目标", f"🌐 {res_domain}"),
                    ("主办单位", f"🏢 {unit_name}"),
                    ("单位性质", f"⚖️ {nature}"),
                    ("备案编号", f"📋 {licence}")
                ]

                # 蓝色调卡片 (#2980B9) 展现权威感
                html = render_card(f"{domain} ICP 备案信息", "🔍", fields, "#2980B9")
                return True, html, ""

            # 错误处理：保留并翻译文档中的中文提示
            api_msg = str(data.get("message", "查询失败"))[:100]
            if resp.status == 400:
                return False, "", f"❌ 请求参数无效: {api_msg}\n\n{usage_hint}"
            elif resp.status == 404:
                return False, "", "❌ 未查询到备案信息: 该域名可能未备案或输入有误。"
            
            return False, "", f"❌ 接口请求失败 (HTTP {resp.status}): {api_msg}"

    except Exception as e:
        logger.warning(f"[UApiPro] ICP 查询异常: {e}")
        return False, "", "⚠️ 网络连接失败，请稍后再试。"
    finally:
        if local_session:
            await session.close()
