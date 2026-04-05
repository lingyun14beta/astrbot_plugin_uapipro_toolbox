"""
UApiPro 工具箱插件 - 核心调度器
功能：一言、天气、IP查询、MC查询、随机图片、定时新闻。
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
from typing import AsyncGenerator
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger
from astrbot.api.message_components import Image, Plain

class UApiProPlugin(Star):
    ALLOWED_MODULES = {"weather", "ipquery", "mcquery", "hitokoto", "random_img", "news"}

    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.plugin_config = config
        
        # --- 仅增加：初始化全局持久 Session ---
        headers = {
            "User-Agent": "AstrBot_UApiPro",
            "Token": config.get("uapi_token", ""),
            "Authorization": f"Bearer {config.get('uapi_token', '')}"
        }
        self.session = aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=30))
        
        self.render_lock = asyncio.Lock()
        self.cd_lock = asyncio.Lock()
        self.last_call_times = {}
        self.bg_task = asyncio.create_task(self._news_scheduler())

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
            elif isinstance(data, str) and data.endswith(('.jpg', '.png', '.jpeg')):
                yield event.chain_result([Image(file=data), Plain(f"\n✨ {fallback_title}")])
            else:
                yield event.plain_result(str(data))
        finally:
            if isinstance(data, str) and os.path.isabs(data) and os.path.exists(data):
                with contextlib.suppress(OSError):
                    os.remove(data)

    async def _handle_query(self, event: AstrMessageEvent, api_module: str, pattern: str, title: str, max_len: int = 150):
        if api_module not in self.ALLOWED_MODULES:
            yield event.plain_result("❌ 调用的模块未授权")
            return
        arg = re.split(pattern, event.message_str.strip(), maxsplit=1)[-1].strip()
        if not arg:
            usage_hint = pattern.replace(r'u\s+', '/u ')
            yield event.plain_result(f"❓ 用法示例：{usage_hint} <内容>")
            return
        if len(arg) > max_len:
            yield event.plain_result(f"❌ 输入内容过长 (限制 {max_len} 字符)")
            return
        try:
            module = importlib.import_module(f".apis.{api_module}", __package__)
            # --- 仅增加：传入 self.session ---
            api_coro = module.fetch(arg, self.plugin_config.get("uapi_token", ""), session=self.session)
            async for r in self._relay(event, api_coro, title):
                yield r
        except Exception as e:
            logger.error(f"[UApiPro] 模块 {api_module} 加载失败: {e}")
            yield event.plain_result(f"❌ 功能模块执行失败")

    @filter.command("u 天气")
    async def cmd_weather(self, event: AstrMessageEvent):
        async for r in self._handle_query(event, "weather", r"u\s+天气", "天气报告", max_len=40):
            yield r

    @filter.command("u ip")
    async def cmd_ip(self, event: AstrMessageEvent):
        async for r in self._handle_query(event, "ipquery", r"u\s+ip", "IP查询结果", max_len=100):
            yield r

    @filter.command("u mc")
    async def cmd_mc(self, event: AstrMessageEvent):
        async for r in self._handle_query(event, "mcquery", r"u\s+mc", "MC服务器状态", max_len=100):
            yield r

    @filter.command("u 一言")
    async def cmd_hitokoto(self, event: AstrMessageEvent):
        from .apis import hitokoto
        async for r in self._relay(event, hitokoto.fetch(self.plugin_config.get("uapi_token", ""), session=self.session), "今日一言"):
            yield r

    @filter.command("u 随机图片")
    async def cmd_random_img(self, event: AstrMessageEvent):
        cats = self.plugin_config.get("random_img_categories", [])
        selected = random.choice(cats) if cats else None
        from .apis import random_img
        async for r in self._relay(event, random_img.fetch(selected, token=self.plugin_config.get("uapi_token", ""), session=self.session), f"随机图片 ({selected})"):
            yield r

    @filter.command("u 新闻")
    async def cmd_news(self, event: AstrMessageEvent):
        from .apis import news
        async for r in self._relay(event, news.fetch(self.plugin_config.get("uapi_token", ""), session=self.session), "每日新闻"):
            yield r

    @filter.command("u 帮助")
    async def cmd_help(self, event: AstrMessageEvent):
        msg = "📦 UApiPro 工具箱\n━━━━━━\n✨ /u 一言\n🌤️ /u 天气 <城市>\n🌐 /u ip <IP>\n🎮 /u mc <地址>\n📰 /u 新闻\n🖼️ /u 随机图片"
        yield event.plain_result(msg)

    async def _news_scheduler(self):
        now = datetime.datetime.now()
        target_str = self.plugin_config.get("news_schedule_time", "08:00").replace("：", ":").strip()
        last_date = None
        try:
            h, m = map(int, target_str.split(":"))
            if now >= now.replace(hour=h, minute=m, second=0): last_date = now.date()
        except: pass
        while True:
            await asyncio.sleep(30)
            try:
                if self.plugin_config.get("news_schedule_enabled", False):
                    now = datetime.datetime.now()
                    target_str = self.plugin_config.get("news_schedule_time", "08:00").replace("：", ":").strip()
                    h, m = map(int, target_str.split(":"))
                    target_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
                    if now >= target_time and last_date != now.date():
                        last_date = now.date()
                        await self._broadcast_news()
            except Exception as e: logger.error(f"[UApiPro] 调度器异常: {e}")

    async def _broadcast_news(self):
        from .apis import news
        from astrbot.api.event import MessageChain
        groups, users = self.plugin_config.get("news_groups", []), self.plugin_config.get("news_users", [])
        if not groups and not users: return
        plat = "default"
        try:
            all_plats = self.context.get_all_platforms()
            if all_plats: plat = list(all_plats.keys())[0]
        except: pass
        ok, path, err = await news.fetch(self.plugin_config.get("uapi_token", ""), session=self.session)
        if not ok: return
        try:
            for gid in groups:
                try:
                    umo = str(gid) if ":" in str(gid) else f"{plat}:GroupMessage:{gid}"
                    await self.context.send_message(umo, MessageChain().file_image(path).message("\n📰 每日早报"))
                except: pass
                await asyncio.sleep(1.5)
            for uid in users:
                try:
                    umo = str(uid) if ":" in str(uid) else f"{plat}:FriendMessage:{uid}"
                    await self.context.send_message(umo, MessageChain().file_image(path).message("\n📰 每日早报"))
                except: pass
                await asyncio.sleep(1.5)
        finally:
            if path and os.path.exists(path):
                with contextlib.suppress(OSError): os.remove(path)

    async def _send_analysis_report(self, event, html, title):
        if self.plugin_config.get("uapi_text_mode", False):
            yield event.plain_result(self._parse_to_text(html))
            return
        image_path = None
        async with self.render_lock:
            try:
                if hasattr(self, "html_render"):
                    image_path = await self.html_render(html, {})
                    if image_path: yield event.chain_result([Image(file=image_path), Plain(f"\n✨ {title}")])
            except Exception as e: logger.warning(f"[UApiPro] 渲染失败: {e}")
            finally:
                if image_path and os.path.exists(image_path):
                    with contextlib.suppress(OSError): os.remove(image_path)
        if not image_path: yield event.plain_result(self._parse_to_text(html))

    async def _check_cd(self, event) -> tuple[bool, float]:
        user_id = event.get_sender_id()
        async with self.cd_lock:
            if len(self.last_call_times) > 1000:
                keys = list(self.last_call_times.keys())
                for _ in range(200): self.last_call_times.pop(random.choice(keys), None)
            now = time.time()
            cd_sec = self.plugin_config.get("uapi_cd", 5.0)
            elapsed = now - self.last_call_times.get(user_id, 0)
            if elapsed < cd_sec: return True, round(cd_sec - elapsed, 1)
            self.last_call_times[user_id] = now
            return False, 0

    def _parse_to_text(self, html: str) -> str:
        try:
            m = re.search(r'header-title">([^<]+)<', html)
            title = m.group(1).strip() if m else "查询结果"
            sections = re.findall(r'section-title">(.*?)</div>.*?section-content">(.*?)</div>', html, re.S)
            res = [f"📊 {title}", "━━━━━━━━━━━━━━"]
            for label_html, val_html in sections:
                label = re.sub(r'<[^>]+>', '', label_html).strip()
                val = re.sub(r'<[^>]+>', ' ', val_html).strip()
                if label and val:
                    res.append(f"📍 {label}: {val}")
            return "\n".join(res) if len(res) > 2 else "📊 暂无结果数据。"
        except: return "📊 结果解析失败。"

    async def terminate(self):
        if hasattr(self, 'session') and not self.session.closed:
            await self.session.close()
        if hasattr(self, 'bg_task'): self.bg_task.cancel()
        logger.info("[UApiPro] 插件卸载完成。")
