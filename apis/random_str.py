import aiohttp
from astrbot.api import logger

API_URL = "https://uapis.cn/api/v1/random/string"


async def fetch(arg_str: str, token: str, session: aiohttp.ClientSession = None):
    """
    随机字符串生成模块
    """
    type_map = {
        "数字": "numeric",
        "小写": "lower",
        "大写": "upper",
        "字母": "alpha",
        "混合": "alphanumeric",
        "十六进制": "hex"
    }

    usage_hint = (
        "🎲 随机字符串指令规范：\n"
        "━━━━━━━━━━━━━━\n"
        "用法：/u 随机 [长度] [类型]\n"
        "长度：1 到 1024 (默认 16)\n"
        "类型：数字、小写、大写、字母、混合、十六进制\n"
        "示例：/u 随机 32 十六进制"
    )

    length = 16
    str_type = "numeric"

    if arg_str:
        parts = arg_str.split()
        for p in parts:
            p_lower = p.lower()
            if p.isdigit():
                length = int(p)
            elif p_lower in type_map:
                str_type = type_map[p_lower]
            elif p_lower in type_map.values():
                str_type = p_lower
            else:
                # 截断恶意构造的参数输入，防止影响消息渲染
                safe_p = str(p)[:20]
                return False, "", f"❌ 无效的类型参数：{safe_p}\n\n{usage_hint}"

    if length < 1 or length > 1024:
        return False, "", f"❌ 无效的请求参数：长度需在 1 到 1024 之间。\n\n{usage_hint}"

    params = {"length": length, "type": str_type}
    local_session = False

    if session is None:
        headers = {"User-Agent": "AstrBot_UApiPro"}
        if token:
            headers["Token"] = token
            headers["Authorization"] = f"Bearer {token}"
        session = aiohttp.ClientSession(headers=headers)
        local_session = True

    try:
        async with session.get(API_URL, params=params, timeout=8) as resp:
            try:
                data = await resp.json(content_type=None)
            except Exception:
                data = {}

            if resp.status == 200:
                content = data.get("text", "").strip()
                if not content:
                    return False, "", "❌ 接口响应成功但未返回内容。"

                display_name = next((k for k, v in type_map.items() if v == str_type), str_type)
                result_msg = (
                    f"🎲 随机字符串 ({display_name})\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"返回结果：{content}"
                )
                return True, result_msg, ""

            api_msg = str(data.get("message", ""))[:100]

            if resp.status == 400:
                return False, "", f"❌ 无效的请求参数: {api_msg}\n\n{usage_hint}"
            elif resp.status == 500:
                return False, "", f"❌ 服务器内部错误: {api_msg or 'Failed to generate random string.'}"
            else:
                return False, "", f"❌ 接口请求失败: {api_msg or f'HTTP {resp.status}'}"

    except Exception as e:
        logger.warning(f"[UApiPro] 随机字符串请求异常: {e}")
        return False, "", "⚠️ 网络连接失败，请稍后再试。"
    finally:
        if local_session:
            await session.close()