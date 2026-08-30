import aiohttp
import base64
import re
from astrbot.api import logger
from ..card_renderer import render_card

API_URL = "https://uapis.cn/api/v1/game/epic-free"


async def fetch(arg_str: str, token: str, session: aiohttp.ClientSession = None):
    """
    Epic 免费游戏查询模块
    """
    local_session = False
    if session is None:
        headers = {"User-Agent": "AstrBot_UApiPro"}
        if token:
            headers["Token"] = token
            headers["Authorization"] = f"Bearer {token}"
        session = aiohttp.ClientSession(headers=headers)
        local_session = True

    try:
        async with session.get(API_URL, timeout=15) as resp:
            try:
                res_json = await resp.json(content_type=None)
            except Exception:
                res_json = {}

            if resp.status == 200:
                games = res_json.get("data", [])
                if not games:
                    return False, "", "空空如也：当前 Epic 商店似乎没有正在进行的免费活动。"

                # 排序：正在免费的排在前面
                games.sort(key=lambda x: x.get("is_free_now", False), reverse=True)

                fields = []
                # 限制 2 个游戏以减小 HTML 体积，防止渲染器超时
                for game in games[:2]:
                    title = game.get("title", "未知游戏")
                    price = game.get("original_price_desc", "免费")
                    is_free = game.get("is_free_now", False)
                    status = "🎁 正在免费" if is_free else "⏳ 即将开始"
                    end_time = game.get("free_end", "未知")
                    cover_url = game.get("cover")

                    # 1. 添加文字描述字段
                    fields.append((f"🎮 {title}", f"状态：{status}\n原价：{price}\n截止：{end_time}"))

                    # 2. 独立添加图片字段 (确保 Base64 字符串单独占据一个 field 才能被渲染器识别)
                    if cover_url and re.match(r'^https://[^/]*epicgames\.com/', cover_url):
                        try:
                            async with session.get(cover_url, timeout=5) as img_resp:
                                if img_resp.status == 200:
                                    img_data = await img_resp.read()
                                    b64_img = f"data:image/png;base64,{base64.b64encode(img_data).decode()}"
                                    fields.append(("游戏封面", b64_img))
                                    del img_data
                        except Exception as e:
                            logger.debug(f"[UApiPro] Epic 封面下载失败: {e}")

                html = render_card("Epic 本周免费游戏", "🎮", fields, "#303133")
                return True, html, ""

            api_msg = str(res_json.get("message", ""))[:100]
            return False, "", f"❌ 请求失败: {api_msg or f'HTTP {resp.status}'}"

    except Exception as e:
        logger.warning(f"[UApiPro] Epic 查询异常: {e}")
        return False, "", "⚠️ 网络连接失败，请稍后再试。"
    finally:
        if local_session:
            await session.close()