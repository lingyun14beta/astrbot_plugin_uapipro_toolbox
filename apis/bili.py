import aiohttp
import base64
import re
import contextlib
from datetime import datetime
from astrbot.api import logger
from ..card_renderer import render_card

USER_URL = "https://uapis.cn/api/v1/social/bilibili/userinfo"
ARCHIVE_URL = "https://uapis.cn/api/v1/social/bilibili/archives"


async def fetch(arg_str: str, token: str, session: aiohttp.ClientSession = None):
    """
    B站资料综合查询 (用户信息 + 投稿接口集成)
    """
    usage_hint = (
        "📺 B站查询规范：\n"
        "━━━━━━━━━━━━━━\n"
        "用法：/u bili <UID>\n"
        "示例：/u bili 483307278"
    )

    mid = arg_str.strip()
    if not mid or not mid.isdigit():
        return False, "", usage_hint

    if len(mid) > 20:
        return False, "", "❌ UID 长度异常。"

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
        # 1. 获取用户基础信息 (userinfo 接口)
        async with session.get(USER_URL, params={"uid": mid}, timeout=10) as u_resp:
            u_data = await u_resp.json(content_type=None) if u_resp.status == 200 else {}
            if u_resp.status == 404:
                return False, "", "❌ 找不到该用户：请检查 UID 是否正确。"
            elif u_resp.status != 200:
                return False, "", f"❌ 用户接口异常 (HTTP {u_resp.status})"

        name = u_data.get("name", "未知用户")
        face_url = u_data.get("face")
        
        # 处理头像 Base64
        display_face = ""
        if face_url and re.match(r"^https?://([^/]*\.hdslb\.com)/", face_url):
            with contextlib.suppress(Exception):
                async with session.get(face_url, timeout=3) as img_resp:
                    if img_resp.status == 200:
                        img_data = await img_resp.read()
                        display_face = f"data:image/jpeg;base64,{base64.b64encode(img_data).decode()}"
                        del img_data

        # 2. 获取投稿列表 (archives 接口)
        v1_info, v1_cover, v2_info = "暂无投稿", "", "暂无更多投稿"
        async with session.get(ARCHIVE_URL, params={"mid": mid, "ps": "2"}, timeout=10) as a_resp:
            if a_resp.status == 200:
                a_data = await a_resp.json(content_type=None)
                videos = a_data.get("videos", [])
                if videos:
                    # 视频 1 (详细)
                    v1 = videos[0]
                    dur = v1.get("duration", 0)
                    v1_time = datetime.fromtimestamp(v1.get("publish_time", 0)).strftime('%Y-%m-%d')
                    v1_info = f"🎬 {v1.get('title')}\n📊 {v1.get('play_count', 0):,} 播放 · ⏱️ {dur//60:02d}:{dur%60:02d}\n🆔 {v1.get('bvid')} · 📅 {v1_time}"
                    
                    # 抓取视频 1 的封面
                    c_url = v1.get("cover")
                    if c_url and re.match(r"^https?://([^/]*\.hdslb\.com)/", c_url):
                        with contextlib.suppress(Exception):
                            async with session.get(c_url, timeout=4) as c_resp:
                                if c_resp.status == 200:
                                    c_data = await c_resp.read()
                                    v1_cover = f"data:image/jpeg;base64,{base64.b64encode(c_data).decode()}"
                                    del c_data

                    # 视频 2 (精简)
                    if len(videos) > 1:
                        v2 = videos[1]
                        v2_info = f"🎞️ {v2.get('title')}\n📊 {v2.get('play_count', 0):,} 播放 · 🆔 {v2.get('bvid')}"

        # 3. 构造卡片 (核心：文字和图片必须分在不同的 field，否则文本解析器会挂掉)
        fields = [
            ("基本信息", f"👤 昵称: {name}\n🆔 UID: {mid}\n🆙 等级: Lv.{u_data.get('level', 0)}"),
            ("粉丝数据", f"👥 粉丝: {u_data.get('follower', 0):,} | 👤 关注: {u_data.get('following', 0):,}"),
            ("个人签名", u_data.get("sign") or "空"),
            ("最新作品", v1_info)
        ]

        if v1_cover:
            fields.append(("视频预览", v1_cover))
        
        fields.append(("上期作品", v2_info))

        if display_face:
            fields.insert(0, ("用户头像", display_face))

        html = render_card(f"{name} 的 B 站资料", "📺", fields, "#FB7299")
        return True, html, ""

    except Exception as e:
        logger.warning(f"[UApiPro] B站综合查询异常: {e}")
        return False, "", "⚠️ 网络连接失败，请稍后再试。"
    finally:
        if local_session:
            await session.close()
