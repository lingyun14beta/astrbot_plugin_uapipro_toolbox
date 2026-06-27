import aiohttp
from ..card_renderer import render_card

API_URL = "https://uapis.cn/api/v1/saying"
API_URL_ADVANCED = "https://uapis.cn/api/v1/saying/random"


async def fetch(token: str = "", session: aiohttp.ClientSession = None):
    """基础一言：随机返回一条语录，无筛选参数。"""
    params = {"token": token} if token else {}
    headers = {"User-Agent": "AstrBot_UApiPro", "Token": token, "Authorization": f"Bearer {token}"}

    local_session = False
    if session is None:
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
                    return False, "", "❌ API 未返回任何语录内容。"
                fields = [("今日语录", content)]
                html = render_card("今日一言", "✨", fields, "#7C83FD")
                return True, html, ""

            api_msg = data.get("message")
            if resp.status == 500:
                return False, "", f"❌ 语料库异常: {api_msg or '无法读取语录数据，请稍后再试'}"
            elif api_msg:
                return False, "", f"❌ 查询失败: {api_msg}"
            else:
                return False, "", f"❌ 接口响应异常 (HTTP {resp.status})"
    except Exception as e:
        return False, "", f"⚠️ 网络连接失败: {str(e)}"
    finally:
        if local_session:
            await session.close()


def _build_advanced_params(token: str, settings: dict) -> dict:
    """根据 hitokoto_advanced 配置组装 /saying/random 请求参数。"""
    params = {}
    if token:
        params["token"] = token

    mode = (settings.get("mode") or "random").strip()
    if mode and mode != "random":
        params["mode"] = mode

    if mode == "recommend":
        scene = (settings.get("scene") or "").strip()
        if scene:
            params["scene"] = scene

    source = settings.get("source") or []
    if source:
        params["source"] = ",".join(source)

    category = settings.get("category") or []
    if category:
        params["category"] = ",".join(category)

    tag = settings.get("tag") or []
    if tag:
        params["tag"] = ",".join(tag)

    return params


async def fetch_advanced(token: str, settings: dict, session: aiohttp.ClientSession = None):
    """高级一言：按 hitokoto_advanced 配置（mode/scene/source/category/tag）请求语录。"""
    headers = {"User-Agent": "AstrBot_UApiPro", "Token": token, "Authorization": f"Bearer {token}"}
    params = _build_advanced_params(token, settings or {})

    local_session = False
    if session is None:
        session = aiohttp.ClientSession(headers=headers)
        local_session = True

    try:
        async with session.get(API_URL_ADVANCED, params=params, timeout=8) as resp:
            try:
                data = await resp.json(content_type=None)
            except Exception:
                data = {}

            if not isinstance(data, dict):
                data = {}

            if resp.status == 200:
                # daily/recommend/moment 模式返回包装对象，语录本体在 item 字段中；random 模式直接返回语录对象本身
                item = data.get("item") if isinstance(data.get("item"), dict) else data

                content = (item.get("content") or "").strip()
                if not content:
                    return False, "", "❌ API 未返回任何语录内容。"

                source_name = item.get("source") or ""
                author = item.get("author") or ""
                attribution = " · ".join(p for p in (source_name, author) if p)

                fields = [("今日语录", content)]
                if attribution:
                    fields.append(("出处", attribution))

                title_map = {
                    "daily": "每日一言",
                    "recommend": "场景一言",
                    "moment": "此刻一言",
                }
                title = title_map.get(data.get("mode"), "今日一言")

                html = render_card(title, "✨", fields, "#7C83FD")
                return True, html, ""

            api_msg = data.get("message")
            if resp.status == 400:
                return False, "", f"❌ 高级一言参数错误: {api_msg or '请检查 mode/scene 等配置是否合法'}"
            if resp.status == 404:
                return False, "", "❌ 未找到满足当前筛选条件的语录，请调整高级一言配置。"
            if resp.status == 500:
                return False, "", f"❌ 语料库异常: {api_msg or '无法读取语录数据，请稍后再试'}"
            elif api_msg:
                return False, "", f"❌ 查询失败: {api_msg}"
            else:
                return False, "", f"❌ 接口响应异常 (HTTP {resp.status})"
    except Exception as e:
        return False, "", f"⚠️ 网络连接失败: {str(e)}"
    finally:
        if local_session:
            await session.close()
