import aiohttp
import re
import datetime
from astrbot.api import logger
from ..card_renderer import render_card

API_URL = "https://uapis.cn/api/v1/misc/holiday-calendar"


async def fetch(arg_str: str, token: str, session: aiohttp.ClientSession = None):
    """
    万年历与节假日查询模块
    """
    usage_hint = (
        "📅 万年历指令规范：\n"
        "━━━━━━━━━━━━━━\n"
        "用法：/u 万年历 [日期/月份]\n"
        "示例：\n"
        "- /u 万年历 2025.10.1\n"
        "- /u 万年历 2025/05\n"
        "提示：支持 . / - 分隔，不填默认查询今天"
    )

    params = {
        "timezone": "Asia/Shanghai",
        "include_nearby": "true",
        "exclude_past": "false",
        "holiday_type": "all"
    }

    arg = arg_str.strip()
    if not arg:
        params["date"] = datetime.datetime.now().strftime("%Y-%m-%d")
    else:
        clean_arg = arg.replace("/", "-").replace(".", "-")
        day_match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", clean_arg)
        month_match = re.match(r"^(\d{4})-(\d{1,2})$", clean_arg)

        if day_match:
            y, m, d = day_match.groups()
            params["date"] = f"{y}-{int(m):02d}-{int(d):02d}"
        elif month_match:
            y, m = month_match.groups()
            params["month"] = f"{y}-{int(m):02d}"
        else:
            safe_arg = str(arg)[:20]
            return False, "", f"❌ 格式不符：{safe_arg}\n\n{usage_hint}"

    local_session = False
    if session is None:
        headers = {"User-Agent": "AstrBot_UApiPro"}
        if token:
            headers["Token"] = token
            headers["Authorization"] = f"Bearer {token}"
        session = aiohttp.ClientSession(headers=headers)
        local_session = True

    try:
        async with session.get(API_URL, params=params, timeout=10) as resp:
            try:
                data = await resp.json(content_type=None)
            except Exception:
                data = {}

            if resp.status == 200:
                summary = data.get("summary", {})
                mode = data.get("mode")
                mode_map = {"day": "日视图", "month": "月视图"}
                mode_name = mode_map.get(mode, "查询结果")
                target = params.get("date") or params.get("month")

                fields = [("查询目标", f"📅 {target} ({mode_name})")]

                # 日视图特有详细信息
                if mode == "day" and data.get("days"):
                    d = data["days"][0]
                    lunar_str = f"{d.get('lunar_month_name')}{d.get('lunar_day_name')}"
                    ganzhi_str = f"{d.get('ganzhi_year')}年 {d.get('ganzhi_month')}月 {d.get('ganzhi_day')}日"
                    fields.append(("农历干支", f"🏮 {lunar_str}\n🎋 {ganzhi_str}"))
                    
                    festivals = [f for f in [d.get('solar_festival'), d.get('lunar_festival'), d.get('solar_term')] if f]
                    if festivals:
                        fields.append(("当日节日", "✨ " + " | ".join(festivals)))

                fields.extend([
                    ("概览统计", f"📊 总计 {summary.get('total_days')} 天"),
                    ("工作/休息", f"💼 工作日 {summary.get('workdays')} | 🏖️ 休息日 {summary.get('rest_days')}")
                ])

                legal_rest = summary.get('legal_rest_days', 0)
                legal_work = summary.get('legal_workdays', 0)
                if legal_rest > 0 or legal_work > 0:
                    fields.append(("法定详情", f"⚖️ 休假 {legal_rest} | 🛠️ 调休 {legal_work}"))

                holidays = data.get("holidays", [])
                if holidays:
                    h_list = []
                    for h in holidays[:8]:
                        d_str = h.get("date", "")[-5:]
                        h_name = h.get("name") or "暂无特定节日（none）"
                        h_list.append(f"{d_str} {h_name}")
                    fields.append(("节日事件", "\n".join(h_list) + ("\n..." if len(holidays) > 8 else "")))
                else:
                    fields.append(("节日事件", "☕ 该时段内暂无显著节日"))

                nearby = data.get("nearby", {})
                if mode == "day" and nearby.get("next"):
                    next_h = nearby["next"][0]
                    # nearby 结构中 events 是个列表
                    next_date = next_h.get('date', '')
                    events = next_h.get('events', [])
                    next_name = events[0].get('name') if events else '暂无特定节日（none）'
                    fields.append(("临近节日", f"🔜 {next_date} {next_name}"))

                html = render_card(f"{target} 万年历", "📅", fields, "#E67E22")
                return True, html, ""

            api_msg = str(data.get("message", ""))[:100]
            return False, "", f"❌ 请求失败: {api_msg or f'HTTP {resp.status}'}\n\n{usage_hint}"

    except Exception as e:
        logger.warning(f"[UApiPro] 万年历查询异常: {e}")
        return False, "", "⚠️ 网络连接失败，请稍后再试。"
    finally:
        if local_session:
            await session.close()