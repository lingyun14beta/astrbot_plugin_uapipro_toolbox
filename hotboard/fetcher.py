"""
hotboard/fetcher.py — 热榜请求调度器
负责发起 HTTP 请求、处理错误码、将原始 JSON 交给对应平台解析器处理。
"""

import aiohttp
from astrbot.api import logger

from . import bilibili, acfun, hellogithub, netease_music, qq_music, weread

API_BASE = "https://uapis.cn/api/v1/misc/hotboard"

# 别名 → (platform_id, 解析器模块, 显示名)
PLATFORM_MAP = {
    "bili":   ("bilibili",     bilibili,     "哔哩哔哩热榜"),
    "a站":    ("acfun",        acfun,        "A站热榜"),
    "github": ("hellogithub",  hellogithub,  "HelloGitHub 热榜"),
    "网易云": ("netease-music", netease_music, "网易云音乐热歌榜"),
    "qq音乐": ("qq-music",     qq_music,     "QQ音乐热歌榜"),
    "微信读书":("weread",       weread,       "微信读书热榜"),
}

HELP_TEXT = (
    "📊 全网热榜 — 支持以下平台：\n"
    "━━━━━━━━━━━━━━\n"
    "  /u 热榜 bili      哔哩哔哩\n"
    "  /u 热榜 a站       A站\n"
    "  /u 热榜 github    HelloGitHub\n"
    "  /u 热榜 网易云    网易云音乐热歌榜\n"
    "  /u 热榜 qq音乐    QQ音乐热歌榜\n"
    "  /u 热榜 微信读书  微信读书热榜\n"
    "━━━━━━━━━━━━━━\n"
    "💡 每5分钟自动更新"
)


async def fetch(alias: str, token: str, session: aiohttp.ClientSession = None):
    """
    统一入口。
    返回 (ok, payload, err)：
      - ok=True  时 payload 为 dict：{"html": str, "items": list, "display_name": str, "platform_id": str}
      - ok=False 时 payload 为 None，err 为错误提示字符串
      - alias="" 时返回帮助文本（ok=False, payload=None, err=HELP_TEXT）
    """
    alias = alias.strip().lower()

    if not alias:
        return False, None, HELP_TEXT

    if alias not in PLATFORM_MAP:
        return False, None, f"❌ 未找到平台「{alias}」，发送 /u 热榜 查看支持的平台列表"

    platform_id, parser, display_name = PLATFORM_MAP[alias]
    url = API_BASE
    headers = {
        "User-Agent": "AstrBot_UApiPro",
        "Token": token,
        "Authorization": f"Bearer {token}",
    }

    local_session = False
    if session is None:
        session = aiohttp.ClientSession(headers=headers)
        local_session = True

    try:
        async with session.get(url, params={"type": platform_id}, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            try:
                res_json = await resp.json(content_type=None)
            except Exception:
                res_json = {}

            if not isinstance(res_json, dict):
                res_json = {}

            if resp.status == 200:
                raw_items = res_json.get("list", [])
                update_time = res_json.get("update_time", "")
                if not raw_items:
                    return False, None, "❌ 暂无热榜数据，请稍后再试"
                from .renderer import render_hotboard
                items = parser.parse(raw_items)
                html = render_hotboard(platform_id, display_name, update_time, raw_items)
                return True, {
                    "html":         html,
                    "items":        items,
                    "display_name": display_name,
                    "platform_id":  platform_id,
                }, ""

            if resp.status == 400:
                logger.warning(f"[UApiPro] hotboard 400: {res_json.get('message', '')}")
                return False, None, "❌ 平台参数错误，请发送 /u 热榜 查看支持的平台列表"
            if resp.status == 500:
                return False, None, "❌ 服务器处理数据时出错，请稍后再试"
            if resp.status == 502:
                return False, None, "❌ 暂时无法获取该平台数据，请稍后再试"
            return False, None, f"❌ 接口响应异常 (HTTP {resp.status})"

    except aiohttp.ClientTimeout:
        return False, None, "⚠️ 请求超时，请稍后再试"
    except Exception as e:
        logger.error(f"[UApiPro] hotboard fetch 异常: {e}")
        return False, None, f"⚠️ 网络连接失败: {str(e)}"
    finally:
        if local_session:
            await session.close()