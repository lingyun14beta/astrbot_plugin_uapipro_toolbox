"""
UApiPro 工具箱插件 - 核心调度器
功能：一言、天气、IP查询、MC查询、万年历、随机图片、定时新闻、随机字符串、MC玩家查询、Epic免费游戏、必应壁纸、全网热榜。
"""

import re
import time
import asyncio
import datetime
import random
import importlib
import os
import contextlib
import aiohttp
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger
from astrbot.api.message_components import Image, Plain, Reply, Node

OCR_MAX_IMAGE_BYTES = 10 * 1024 * 1024


async def _extract_first_image_b64(event: AstrMessageEvent) -> tuple[bool, str, str]:
    """提取消息中第一张图片并转为 Base64，优先取直接发送的图，没有则取引用回复的图。"""
    direct_images: list[Image] = []
    quoted_images: list[Image] = []
    for comp in event.get_messages():
        if isinstance(comp, Image):
            direct_images.append(comp)
        elif isinstance(comp, Reply) and comp.chain:
            for sub in comp.chain:
                if isinstance(sub, Image):
                    quoted_images.append(sub)

    candidates = direct_images or quoted_images

    if not candidates:
        return False, "", "❓ 未检测到图片，请直接发图或引用一张图片后发送 /u ocr"

    try:
        b64 = await candidates[0].convert_to_base64()
    except Exception as e:
        logger.warning(f"[UApiPro] OCR 图片读取失败: {e}")
        return False, "", "❌ 图片读取失败，请重新发送。"

    if len(b64) > OCR_MAX_IMAGE_BYTES // 3 * 4:
        return False, "", "❌ 图片过大，请发送不超过 10MB 的图片。"

    return True, b64, ""


class UApiProPlugin(Star):
    ALLOWED_MODULES = {
        "weather",
        "ipquery",
        "mcquery",
        "hitokoto",
        "random_img",
        "news",
        "random_str",
        "holiday",
        "mc_user",
        "epic",
        "bing_daily",
        "answer_book",
        "qrcode",
        "whois",
        "tracking",
        "github",
        "steam_user",
        "bili",
        "icp",
    }

    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.plugin_config = config

        headers = {
            "User-Agent": "AstrBot_UApiPro",
            "Token": config.get("uapi_token", ""),
            "Authorization": f"Bearer {config.get('uapi_token', '')}",
        }
        self.session = aiohttp.ClientSession(
            headers=headers, timeout=aiohttp.ClientTimeout(total=30)
        )

        self.render_lock = asyncio.Lock()
        self.cd_lock = asyncio.Lock()
        self.last_call_times = {}
        self.bg_task = asyncio.create_task(self._news_scheduler())

        # 注册 LLM function calling 工具（仅在开关开启时）
        if self.plugin_config.get("llm_tools_enabled", False):
            from .llm_tools import register_llm_tools

            register_llm_tools(self)

    async def _relay(self, event: AstrMessageEvent, api_coro, fallback_title: str):
        event.should_call_llm(False)
        in_cd, remain = await self._check_cd(event)
        if in_cd:
            yield event.plain_result(f"⏰ 冷却中: 还剩 {remain} 秒")
            return

        try:
            ok, data, err = await api_coro
        except Exception as e:
            logger.error(f"[UApiPro] API 执行异常: {e}")
            yield event.plain_result("❌ 插件内部执行异常")
            return

        if not ok:
            yield event.plain_result(err or "❌ 请求失败，请稍后再试。")
            return

        try:
            if isinstance(data, str) and ("<html" in data.lower() or "<style" in data):
                async for r in self._send_analysis_report(event, data, fallback_title):
                    yield r
            elif isinstance(data, str) and data.endswith((".jpg", ".png", ".jpeg")):
                caption = err if (err and len(err) > 20) else f"✨ {fallback_title}"
                yield event.chain_result([Image(file=data), Plain(f"\n{caption}")])
            else:
                yield event.plain_result(str(data))
        finally:
            if isinstance(data, str) and os.path.isabs(data) and os.path.exists(data):
                with contextlib.suppress(OSError):
                    os.remove(data)

    def _extract_arg(self, event: AstrMessageEvent, pattern: str) -> str:
        """从消息中提取指令参数，兼容 AstrBot 别名（别名触发时 message_str 不含原始前缀）"""
        msg = event.message_str.strip()
        parts = re.split(pattern, msg, maxsplit=1)
        if len(parts) > 1:
            return parts[-1].strip()
        # 别名触发：正则未命中，剥离第一个空格前的 token（即别名本身）
        tokens = msg.split(maxsplit=1)
        return tokens[1].strip() if len(tokens) > 1 else ""

    async def _handle_query(
        self,
        event: AstrMessageEvent,
        api_module: str,
        pattern: str,
        title: str,
        max_len: int = 150,
    ):
        if api_module not in self.ALLOWED_MODULES:
            yield event.plain_result("❌ 调用的模块未授权")
            return
        arg = self._extract_arg(event, pattern)
        if not arg:
            usage_hint = pattern.replace(r"u\s+", "/u ")
            yield event.plain_result(f"❓ 用法示例：{usage_hint} <内容>")
            return
        if len(arg) > max_len:
            yield event.plain_result(f"❌ 输入内容过长 (限制 {max_len} 字符)")
            return
        try:
            module = importlib.import_module(f".apis.{api_module}", __package__)
            api_coro = module.fetch(
                arg, self.plugin_config.get("uapi_token", ""), session=self.session
            )
            async for r in self._relay(event, api_coro, title):
                yield r
        except Exception as e:
            logger.error(f"[UApiPro] 模块 {api_module} 加载失败: {e}")
            yield event.plain_result("❌ 功能模块执行失败")

    @filter.command("u 天气", desc="查询城市天气")
    async def cmd_weather(self, event: AstrMessageEvent):
        async for r in self._handle_query(
            event, "weather", r"u\s+天气", "天气报告", max_len=40
        ):
            yield r

    @filter.command("u ip", desc="IP归属地查询")
    async def cmd_ip(self, event: AstrMessageEvent):
        async for r in self._handle_query(
            event, "ipquery", r"u\s+ip", "IP查询结果", max_len=100
        ):
            yield r

    @filter.command("u mc", desc="MC服务器状态")
    async def cmd_mc(self, event: AstrMessageEvent):
        async for r in self._handle_query(
            event, "mcquery", r"u\s+mc", "MC服务器状态", max_len=100
        ):
            yield r

    @filter.command("u mc玩家", desc="MC正版玩家信息")
    async def cmd_mc_user(self, event: AstrMessageEvent):
        arg = self._extract_arg(event, r"u\s+mc玩家")
        from .apis import mc_user

        async for r in self._relay(
            event,
            mc_user.fetch(
                arg, self.plugin_config.get("uapi_token", ""), session=self.session
            ),
            "MC玩家资料",
        ):
            yield r

    @filter.command("u 一言", desc="随机一句话")
    async def cmd_hitokoto(self, event: AstrMessageEvent):
        from .apis import hitokoto

        token = self.plugin_config.get("uapi_token", "")
        adv = self.plugin_config.get("hitokoto_advanced", {})

        if adv.get("enabled", False):
            api_coro = hitokoto.fetch_advanced(token, adv, session=self.session)
        else:
            api_coro = hitokoto.fetch(token, session=self.session)

        async for r in self._relay(event, api_coro, "今日一言"):
            yield r

    @filter.command("u 随机图片", desc="随机壁纸")
    async def cmd_random_img(self, event: AstrMessageEvent):
        cats = self.plugin_config.get("random_img_categories", [])
        selected = random.choice(cats) if cats else None
        from .apis import random_img

        async for r in self._relay(
            event,
            random_img.fetch(
                selected,
                token=self.plugin_config.get("uapi_token", ""),
                session=self.session,
            ),
            f"随机图片 ({selected})",
        ):
            yield r

    @filter.command("u 随机", desc="生成随机字符串")
    async def cmd_random_str(self, event: AstrMessageEvent):
        arg = self._extract_arg(event, r"u\s+随机")
        from .apis import random_str

        async for r in self._relay(
            event,
            random_str.fetch(
                arg, self.plugin_config.get("uapi_token", ""), session=self.session
            ),
            "随机字符串",
        ):
            yield r

    @filter.command("u 万年历", desc="节假日/日历查询")
    async def cmd_holiday(self, event: AstrMessageEvent):
        arg = self._extract_arg(event, r"u\s+万年历")
        from .apis import holiday

        async for r in self._relay(
            event,
            holiday.fetch(
                arg, self.plugin_config.get("uapi_token", ""), session=self.session
            ),
            "万年历查询",
        ):
            yield r

    @filter.command("u epic", desc="Epic本周免费游戏")
    async def cmd_epic(self, event: AstrMessageEvent):
        from .apis import epic

        async for r in self._relay(
            event,
            epic.fetch(
                "", self.plugin_config.get("uapi_token", ""), session=self.session
            ),
            "Epic免费游戏",
        ):
            yield r

    @filter.command("u 必应", desc="必应每日壁纸")
    async def cmd_bing_daily(self, event: AstrMessageEvent):
        arg = self._extract_arg(event, r"u\s+必应")
        from .apis import bing_daily

        async for r in self._relay(
            event,
            bing_daily.fetch(
                arg, self.plugin_config.get("uapi_token", ""), session=self.session
            ),
            "必应每日壁纸",
        ):
            yield r

    @filter.command("u 答案之书", desc="随机答案")
    async def cmd_answer_book(self, event: AstrMessageEvent):
        arg = self._extract_arg(event, r"u\s+答案之书")
        from .apis import answer_book

        async for r in self._relay(
            event,
            answer_book.fetch(
                arg, self.plugin_config.get("uapi_token", ""), session=self.session
            ),
            "答案之书",
        ):
            yield r

    @filter.command("u 二维码", desc="生成二维码")
    async def cmd_qrcode(self, event: AstrMessageEvent):
        arg = self._extract_arg(event, r"u\s+二维码")
        from .apis import qrcode

        async for r in self._relay(
            event,
            qrcode.fetch(
                arg, self.plugin_config.get("uapi_token", ""), session=self.session
            ),
            "二维码生成",
        ):
            yield r

    @filter.command("u whois", desc="域名WHOIS查询")
    async def cmd_whois(self, event: AstrMessageEvent):
        arg = self._extract_arg(event, r"u\s+whois")
        from .apis import whois

        async for r in self._relay(
            event,
            whois.fetch(
                arg, self.plugin_config.get("uapi_token", ""), session=self.session
            ),
            "WHOIS查询",
        ):
            yield r

    @filter.command("u icp", desc="ICP备案查询")
    async def cmd_icp(self, event: AstrMessageEvent):
        arg = self._extract_arg(event, r"u\s+icp")
        from .apis import icp

        async for r in self._relay(
            event,
            icp.fetch(
                arg, self.plugin_config.get("uapi_token", ""), session=self.session
            ),
            "ICP备案查询",
        ):
            yield r

    @filter.command("u 快递", desc="快递物流查询")
    async def cmd_tracking(self, event: AstrMessageEvent):
        arg = self._extract_arg(event, r"u\s+快递")
        from .apis import tracking

        async for r in self._relay(
            event,
            tracking.fetch(
                arg, self.plugin_config.get("uapi_token", ""), session=self.session
            ),
            "快递物流查询",
        ):
            yield r

    @filter.command("u github", desc="GitHub仓库信息")
    async def cmd_github(self, event: AstrMessageEvent):
        arg = self._extract_arg(event, r"u\s+github")
        from .apis import github

        async for r in self._relay(
            event,
            github.fetch(
                arg, self.plugin_config.get("uapi_token", ""), session=self.session
            ),
            "GitHub仓库信息",
        ):
            yield r

    @filter.command("u steam", desc="Steam用户信息")
    async def cmd_steam(self, event: AstrMessageEvent):
        arg = self._extract_arg(event, r"u\s+steam")
        from .apis import steam_user

        async for r in self._relay(
            event,
            steam_user.fetch(
                arg, self.plugin_config.get("uapi_token", ""), session=self.session
            ),
            "Steam用户信息",
        ):
            yield r

    @filter.command("u bili", desc="B站UP主信息")
    async def cmd_bili(self, event: AstrMessageEvent):
        arg = self._extract_arg(event, r"u\s+bili")
        from .apis import bili

        async for r in self._relay(
            event,
            bili.fetch(
                arg, self.plugin_config.get("uapi_token", ""), session=self.session
            ),
            "B站投稿列表",
        ):
            yield r

    @filter.command("u ocr", desc="图片文字识别")
    async def cmd_ocr(self, event: AstrMessageEvent):
        event.should_call_llm(False)
        in_cd, remain = await self._check_cd(event)
        if in_cd:
            yield event.plain_result(f"⏰ 冷却中: 还剩 {remain} 秒")
            return

        ok, b64, err = await _extract_first_image_b64(event)
        if not ok:
            yield event.plain_result(err)
            return

        from .apis import ocr

        ocr_settings = self.plugin_config.get("ocr_settings", {})
        try:
            ok, text, err = await ocr.fetch(
                b64,
                self.plugin_config.get("uapi_token", ""),
                return_markdown=ocr_settings.get("return_markdown", False),
                enable_cls=ocr_settings.get("enable_cls", True),
                session=self.session,
            )
        except Exception as e:
            logger.error(f"[UApiPro] OCR 执行异常: {e}")
            yield event.plain_result("❌ 插件内部执行异常")
            return

        if not ok:
            yield event.plain_result(err or "❌ 识别失败，请稍后再试。")
            return

        result_msg = f"📝 OCR 识别结果\n━━━━━━━━━━━━━━\n{text}"

        # QQ 平台用合并转发，其他平台直接发文本
        if event.get_platform_name() == "aiocqhttp":
            try:
                yield event.chain_result(
                    [Node(content=[Plain(text=result_msg)], name="OCR 识别结果", uin="10000")]
                )
                return
            except Exception as e:
                logger.warning(f"[UApiPro] 合并转发发送失败，降级为普通文本: {e}")

        yield event.plain_result(result_msg)

    @filter.command("u 新闻", desc="每日新闻早报")
    async def cmd_news(self, event: AstrMessageEvent):
        from .apis import news

        async for r in self._relay(
            event,
            news.fetch(self.plugin_config.get("uapi_token", ""), session=self.session),
            "每日新闻",
        ):
            yield r

    @filter.command("u 热榜", desc="全网热榜聚合")
    async def cmd_hotboard(self, event: AstrMessageEvent):
        from .hotboard import fetch

        arg = self._extract_arg(event, r"u\s+热榜")
        event.should_call_llm(False)

        if not arg:
            from .hotboard.fetcher import HELP_TEXT
            yield event.plain_result(HELP_TEXT)
            return

        in_cd, remain = await self._check_cd(event)
        if in_cd:
            yield event.plain_result(f"⏰ 冷却中: 还剩 {remain} 秒")
            return

        try:
            ok, payload, err = await fetch(
                arg, self.plugin_config.get("uapi_token", ""), session=self.session
            )
        except Exception as e:
            logger.error(f"[UApiPro] hotboard 执行异常: {e}")
            yield event.plain_result("❌ 插件内部执行异常")
            return

        if not ok:
            yield event.plain_result(err or "❌ 请求失败，请稍后再试。")
            return

        html         = payload["html"]
        items        = payload["items"]
        display_name = payload["display_name"]
        platform_id  = payload["platform_id"]

        # 文本降级函数：用结构化数据拼文本，不依赖 HTML 解析
        def _hotboard_fallback() -> str:
            EMOJI = {
                "bilibili":      "📺",
                "acfun":         "🍌",
                "hellogithub":   "🐙",
                "netease-music": "🎵",
                "qq-music":      "🎶",
                "weread":        "📖",
            }
            icon = EMOJI.get(platform_id, "📊")
            lines = [f"{icon} {display_name}", "━━━━━━━━━━━━━━"]
            for item in items:
                rank  = item["index"]
                title = item["title"]
                hot   = item.get("hot_value", "")
                extra = item.get("extra", {})

                # 副信息
                sub = ""
                if platform_id == "bilibili":
                    up = extra.get("up_name", "")
                    sub = f"  UP: {up}" if up else ""
                elif platform_id == "hellogithub":
                    lang = extra.get("primary_lang", "")
                    repo = extra.get("full_name", "")
                    sub = f"  [{lang}] {repo}" if lang else f"  {repo}"
                elif platform_id in ("netease-music", "qq-music"):
                    artist = extra.get("artist_names", "")
                    dur    = extra.get("duration_text", "")
                    sub = f"  {artist}" + (f" · {dur}" if dur else "")
                elif platform_id == "weread":
                    author = extra.get("author", "")
                    sub = f"  {author}" if author else ""

                hot_str = f"  {hot}" if hot else ""
                lines.append(f"#{rank} {title}{hot_str}")
                if sub:
                    lines.append(sub)
                url = item.get("url", "")
                if url:
                    lines.append(f"  🔗 {url}")

            lines.append("━━━━━━━━━━━━━━")
            lines.append("Powered by UApiPro")
            return "\n".join(lines)

        # 文本模式直接降级
        if self.plugin_config.get("uapi_text_mode", False):
            yield event.plain_result(_hotboard_fallback())
            return

        # 尝试渲染，失败则降级文本
        import base64 as _base64
        render_strategies = [
            {"full_page": True, "type": "png",  "scale": "device", "device_scale_factor_level": "ultra"},
            {"full_page": True, "type": "jpeg", "quality": 100, "scale": "device", "device_scale_factor_level": "ultra"},
            {"full_page": True, "type": "jpeg", "quality": 95,  "scale": "device", "device_scale_factor_level": "high"},
            {"full_page": True, "type": "jpeg", "quality": 80,  "scale": "device"},
        ]

        async with self.render_lock:
            for options in render_strategies:
                try:
                    image_data = await self.html_render(html, {}, False, options)
                    if not image_data:
                        continue
                    raw = None
                    if isinstance(image_data, bytes):
                        raw = image_data
                    elif isinstance(image_data, str) and os.path.exists(image_data):
                        with open(image_data, "rb") as f:
                            raw = f.read()
                        with contextlib.suppress(OSError):
                            os.remove(image_data)
                    if not raw:
                        continue
                    if raw[:2] == b"\xff\xd8" or raw[:4] == b"\x89PNG":
                        b64 = _base64.b64encode(raw).decode()
                        yield event.chain_result(
                            [Image(file=f"base64://{b64}"), Plain(f"\n✨ {display_name}")]
                        )
                        return
                    logger.warning(f"[UApiPro] hotboard 策略 {options} 返回非图片数据")
                except Exception as e:
                    logger.warning(f"[UApiPro] hotboard 策略 {options} 失败: {e}")

        yield event.plain_result(
            "⚠️ 渲染服务器故障，已自动切换至文本模式：\n\n" + _hotboard_fallback()
        )

    @filter.command("u 帮助", desc="查看所有指令")
    async def cmd_help(self, event: AstrMessageEvent):
        msg = (
            "📦 UApiPro 工具箱\n"
            "━━━━━━━━━━━━━━\n"
            "✨ /u 一言\n"
            "🌤️ /u 天气 <城市>\n"
            "🌐 /u ip <IP/域名>\n"
            "🎮 /u mc <服务器地址>\n"
            "👤 /u mc玩家 <正版ID>\n"
            "📅 /u 万年历 [日期/月份]\n"
            "🎲 /u 随机 [长度] [类型]\n"
            "🎁 /u epic\n"
            "🖼️ /u 必应 [日期]\n"
            "📖 /u 答案之书 <问题>\n"
            "📊 /u 热榜 <平台>      发送 /u 热榜 查看支持平台\n"
            " /u 二维码 <内容> [尺寸]\n"
            " /u whois <域名>\n"
            " /u icp <域名>\n"
            " /u 快递 <单号>\n"
            " /u github <仓库/链接>\n"
            " /u steam <ID/链接>\n"
            " /u bili <UID> [关键词]\n"
            " /u 新闻\n"
            " /u 随机图片\n"
            " /u ocr 发图或引用图片识别文字\n"
            "━━━━━━━━━━━━━━\n"
            "💡 提示：[] 为可选，<> 为必填"
        )
        yield event.plain_result(msg)

    async def _news_scheduler(self):
        while True:
            await asyncio.sleep(30)
            try:
                if self.plugin_config.get("news_schedule_enabled", False):
                    now = datetime.datetime.now()
                    target_str = (
                        self.plugin_config.get("news_schedule_time", "08:00")
                        .replace("：", ":")
                        .strip()
                    )
                    h, m = map(int, target_str.split(":"))
                    target_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
                    last_date = await self.get_kv_data("news_last_push_date", None)
                    if now >= target_time and last_date != now.date().isoformat():
                        await self.put_kv_data("news_last_push_date", now.date().isoformat())
                        await self._broadcast_news()
            except Exception as e:
                logger.error(f"[UApiPro] 调度器异常: {e}")

    async def _broadcast_news(self):
        logger.info("[UApiPro] 开始推送早报")
        from .apis import news
        from astrbot.api.event import MessageChain

        groups, users = (
            self.plugin_config.get("news_groups", []),
            self.plugin_config.get("news_users", []),
        )
        if not groups and not users:
            return
        plat = None
        try:
            plat_insts = self.context.platform_manager.platform_insts
            if plat_insts:
                plat = plat_insts[0].meta().id
        except Exception:
            pass
        if not plat:
            logger.warning("[UApiPro] 未找到任何已注册的平台，无法推送早报")
            return
        ok, path, err = await news.fetch(
            self.plugin_config.get("uapi_token", ""), session=self.session
        )
        logger.info(f"[UApiPro] 新闻获取结果 ok={ok} err={err}")
        if not ok:
            return
        try:
            for gid in groups:
                umo = str(gid) if ":" in str(gid) else f"{plat}:GroupMessage:{gid}"
                await self.context.send_message(
                    umo, MessageChain().file_image(path).message("\n📰 每日早报")
                )
                await asyncio.sleep(1.5)
            for uid in users:
                umo = str(uid) if ":" in str(uid) else f"{plat}:FriendMessage:{uid}"
                await self.context.send_message(
                    umo, MessageChain().file_image(path).message("\n📰 每日早报")
                )
                await asyncio.sleep(1.5)
        finally:
            if path and os.path.exists(path):
                with contextlib.suppress(OSError):
                    os.remove(path)

    async def _send_analysis_report(self, event, html, title):
        import base64 as _base64

        if self.plugin_config.get("uapi_text_mode", False):
            yield event.plain_result(self._parse_to_text(html))
            return

        render_strategies = [
            {
                "full_page": True,
                "type": "png",
                "scale": "device",
                "device_scale_factor_level": "ultra",
            },
            {
                "full_page": True,
                "type": "jpeg",
                "quality": 100,
                "scale": "device",
                "device_scale_factor_level": "ultra",
            },
            {
                "full_page": True,
                "type": "jpeg",
                "quality": 95,
                "scale": "device",
                "device_scale_factor_level": "high",
            },
            {"full_page": True, "type": "jpeg", "quality": 80, "scale": "device"},
        ]

        async with self.render_lock:
            if not hasattr(self, "html_render"):
                yield event.plain_result(self._parse_to_text(html))
                return

            for options in render_strategies:
                try:
                    image_data = await self.html_render(html, {}, False, options)
                    if not image_data:
                        continue

                    # 获取原始字节
                    raw = None
                    if isinstance(image_data, bytes):
                        raw = image_data
                    elif isinstance(image_data, str) and os.path.exists(image_data):
                        with open(image_data, "rb") as f:
                            raw = f.read()
                        with contextlib.suppress(OSError):
                            os.remove(image_data)

                    if not raw:
                        continue

                    # 校验是否为真实图片
                    if raw[:2] == b"\xff\xd8" or raw[:4] == b"\x89PNG":
                        b64 = _base64.b64encode(raw).decode()
                        yield event.chain_result(
                            [Image(file=f"base64://{b64}"), Plain(f"\n✨ {title}")]
                        )
                        return

                    logger.warning(
                        f"[UApiPro] 策略 {options} 返回非图片数据，尝试下一个"
                    )
                except Exception as e:
                    logger.warning(f"[UApiPro] 策略 {options} 失败: {e}，尝试下一个")

        yield event.plain_result(
            "⚠️ 渲染服务器故障，已自动切换至文本模式：\n\n" + self._parse_to_text(html)
        )

    async def _check_cd(self, event) -> tuple[bool, float]:
        user_id = event.get_sender_id()
        async with self.cd_lock:
            if len(self.last_call_times) > 1000:
                keys = list(self.last_call_times.keys())
                for k in random.sample(keys, min(200, len(keys))):
                    self.last_call_times.pop(k, None)
            now = time.time()
            cd_sec = self.plugin_config.get("uapi_cd", 5.0)
            elapsed = now - self.last_call_times.get(user_id, 0)
            if elapsed < cd_sec:
                return True, round(cd_sec - elapsed, 1)
            self.last_call_times[user_id] = now
            return False, 0

    def _parse_to_text(self, html: str) -> str:
        try:
            m = re.search(r'header-title">([^<]+)<', html)
            title = m.group(1).strip() if m else "查询结果"
            res = [f"📊 {title}", "━━━━━━━━━━━━━━"]

            sections = re.findall(
                r'item-label">\s*<div[^>]+></div>\s*(.*?)</div>.*?item-value">(.*?)</div>',
                html,
                re.S,
            )

            for label_html, val_html in sections:
                label = re.sub(r"<[^>]+>", "", label_html).strip()
                val_raw = val_html.replace("<br>", "\n").replace("<br/>", "\n")
                val_clean = re.sub(r"<[^>]+>", "", val_raw).strip()

                if label and val_clean and "data:image" not in val_clean:
                    res.append(f"📍 {label}: {val_clean}")

            if len(res) > 2:
                return "\n".join(res)
            return f"📊 {title}\n抱歉，无法从页面提取有效文本数据。"
        except Exception:
            return "📊 结果解析失败。"

    async def terminate(self):
        if hasattr(self, "session") and not self.session.closed:
            await self.session.close()
        if hasattr(self, "bg_task"):
            self.bg_task.cancel()
        logger.info("[UApiPro] 插件卸载完成。")
