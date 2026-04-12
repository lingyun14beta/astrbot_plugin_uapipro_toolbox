import aiohttp
from astrbot.api import logger
from ..card_renderer import render_card

API_URL = "https://uapis.cn/api/v1/misc/tracking/query"


async def fetch(arg_str: str, token: str, session: aiohttp.ClientSession = None):
    """
    快递物流查询模块
    """
    usage_hint = (
        "📦 快递查询规范：\n"
        "━━━━━━━━━━━━━━\n"
        "用法：/u 快递 <快递单号>\n"
        "示例：/u 快递 YT1234567890"
    )

    tracking_number = arg_str.strip()
    if not tracking_number:
        return False, "", usage_hint

    if len(tracking_number) > 32:
        return False, "", "❌ 快递单号长度异常，请核对后重试。"

    params = {"tracking_number": tracking_number}
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
        async with session.get(API_URL, params=params, timeout=12) as resp:
            try:
                data = await resp.json(content_type=None)
            except Exception:
                data = {}

            if resp.status == 200:
                carrier_name = data.get("carrier_name", "未知快递")
                tracks = data.get("tracks", [])

                fields = [
                    ("快递详情", f"🔢 单号: {tracking_number}\n🏢 公司: {carrier_name}"),
                    ("轨迹统计", f"📊 共计 {data.get('track_count', 0)} 条记录")
                ]

                if tracks:
                    formatted_tracks = []
                    for i, t in enumerate(tracks[:10]):
                        time_str = str(t.get("time", ""))
                        context = str(t.get("context", ""))
                        # 视觉区分：最新一条使用 🚩，其余使用 •
                        symbol = "🚩" if i == 0 else "•"
                        formatted_tracks.append(f"{symbol} {time_str}\n   {context}")

                    track_msg = "\n\n".join(formatted_tracks)
                    if len(tracks) > 10:
                        track_msg += "\n\n(仅展示最近 10 条动态，余下略...)"

                    fields.append(("最新轨迹", track_msg))
                else:
                    fields.append(("最新轨迹", "📭 暂无详细物流轨迹"))

                html_card = render_card(f"{carrier_name} 物流追踪", "📦", fields, "#F39C12")
                return True, html_card, ""

            api_msg = str(data.get("message", "查询失败"))[:100]
            if resp.status == 404:
                return False, "", "❌ 暂无物流信息：请核对单号是否正确。"
            return False, "", f"❌ 接口请求失败: {api_msg}"

    except Exception as e:
        logger.warning(f"[UApiPro] 快递查询异常: {e}")
        return False, "", "⚠️ 网络连接失败，请稍后再试。"
    finally:
        if local_session:
            await session.close()