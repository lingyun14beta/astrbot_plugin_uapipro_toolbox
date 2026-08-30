import aiohttp
import re
import ipaddress
import socket
import asyncio
from astrbot.api import logger
from ..card_renderer import render_card

API_URL = "https://uapis.cn/api/v1/game/minecraft/bedrockstatus"


async def fetch(server: str, token: str, session: aiohttp.ClientSession = None):
    """
    Minecraft 基岩版服务器状态查询模块

    Args:
        server: 基岩版服务器地址（域名或 IP，默认端口 19132）。
        token: UApiPro 接口密钥。
        session: 复用的 aiohttp 会话；为 None 时自动创建并关闭。

    Returns:
        (ok, data, err): ok 为 True 时 data 为渲染用 HTML；失败时 err 为提示文本。
    """
    if not re.match(r'^[a-zA-Z0-9.\-]+(:\d{1,5})?$', server):
        return False, "", "❌ 服务器地址格式不合法。"

    # 安全预检：拦截私网/回环/保留网段，防止 SSRF
    host = server.split(':')[0]
    try:
        loop = asyncio.get_event_loop()
        resolved_ip = await loop.run_in_executor(None, socket.gethostbyname, host)
        ip_obj = ipaddress.ip_address(resolved_ip)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved:
            return False, "", "❌ 安全拦截：禁止查询受限网段地址。"
    except Exception:
        pass

    params = {"server": server}
    local_session = False
    if session is None:
        # Token 为空时不发送鉴权头，否则会被 UApiPro 判定为无效密钥，访客额度失效
        headers = {"User-Agent": "AstrBot_UApiPro"}
        if token:
            headers["Token"] = token
            headers["Authorization"] = f"Bearer {token}"
        session = aiohttp.ClientSession(headers=headers)
        local_session = True

    try:
        async with session.get(API_URL, params=params, timeout=15) as resp:
            try:
                data = await resp.json(content_type=None)
            except Exception:
                data = {}

            if resp.status == 200:
                # 离线时文档约定仅返回 online:false，其余字段全部省略，必须判空
                if not isinstance(data, dict) or not data.get("online"):
                    return False, "", "❌ 服务器离线或无法连通，请检查地址与端口。"

                motd = (data.get("motd_clean") or "").strip() or "无服务器介绍"
                sub = (data.get("sub_motd_clean") or "").strip()
                fields = [
                    (
                        "服务器信息",
                        f"🌐 地址: {server}\n"
                        f"⚙️ 版本: {data.get('version') or '--'} (协议 {data.get('protocol', '--')})\n"
                        f"🎮 模式: {data.get('gamemode') or '--'}\n"
                        f"🏷️ 类型: {data.get('edition') or '--'}",
                    ),
                    (
                        "在线状态",
                        f"👥 玩家: {data.get('players', 0)} / {data.get('max_players', 0)}\n"
                        f"📍 解析: {data.get('ip') or '--'}:{data.get('port') or '--'}",
                    ),
                    ("MOTD (第一行)", f"📜 {motd[:150]}"),
                ]
                if sub:
                    fields.append(("MOTD (第二行)", f"📜 {sub[:150]}"))
                fields.append(
                    (
                        "延迟",
                        f"⏱ {data.get('latency_ms', '--')} ms（云端测速，仅供参考，不代表真实游戏延迟）",
                    )
                )

                html = render_card("Minecraft 基岩版服务器", "⛏️", fields, "#5CB85C")
                return True, html, ""

            api_msg = str(data.get("message", ""))[:100] if isinstance(data, dict) else ""
            if resp.status == 400:
                return False, "", "❌ 参数无效：地址无法解析，请检查域名/IP 与端口。"
            if resp.status == 401:
                return False, "", "❌ UApiPro Token 无效，请检查插件配置。"
            if resp.status == 404:
                return False, "", "❌ 未找到服务器：地址无法解析或处于离线状态。"
            if resp.status == 429:
                return False, "", "❌ 请求过于频繁，请稍后再试。"
            return False, "", f"❌ 查询失败：{api_msg or f'HTTP {resp.status}'}"

    except asyncio.TimeoutError:
        return False, "", "⚠️ 查询超时：目标服务器响应缓慢。"
    except Exception as e:
        logger.warning(f"[UApiPro] 基岩版MC查询异常: {e}")
        return False, "", "⚠️ 网络连接异常，请检查机器人网络。"
    finally:
        if local_session:
            await session.close()
