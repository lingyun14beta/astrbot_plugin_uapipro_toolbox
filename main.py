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
from typing import AsyncGenerator
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger
from astrbot.api.message_components import Image, Plain

class UApiProPlugin(Star):
    # 允许动态加载的 API 模块白名单
    ALLOWED_MODULES = {"weather", "ipquery", "mcquery", "hitokoto", "random_img", "news"}

    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.plugin_config = config
        self.render_lock = asyncio.Lock()
        self.cd_lock = asyncio.Lock()
        self.last_call_times = {}
        # 启动后台定时任务
        self.bg_task = asyncio.create_task(self._news_scheduler())

    # ================================================================
    # 核心转接引擎 (Relay Engine)
    # ================================================================

    async def _relay(self, event: AstrMessageEvent, api_coro, fallback_title: str):
        """
        统一指令转接器：负责 CD 检查、执行 API 逻辑、分发渲染及文件清理。
        """
        event.should_call_llm(False)
        
        # 1. 冷却检查
        in_cd, remain = await self._check_cd(event)
        if in_cd: 
            yield event.plain_result(f"⏰ 冷却中: 还剩 {remain} 秒")
            return

        # 2. 执行 API 请求
        try:
            ok, data, err = await api_coro 
        except Exception as e:
            logger.error(f"[UApiPro] API 执行异常: {e}")
            yield event.plain_result("❌ 插件内部执行异常")
            return
        
        if not ok:
            yield event.plain_result(err or "❌ 请求失败，请稍后再试。")
            return

        # 3. 结果分发与临时文件清理
        try:
            if isinstance(data, str) and ("<html" in data.lower() or "<style" in data):
                # HTML 渲染模式
                async for r in self._send_analysis_report(event, data, fallback_title):
                    yield r
            elif isinstance(data, str) and data.endswith(('.jpg', '.png', '.jpeg')):
                # 本地图片文件模式
                yield event.chain_result([Image(file=data), Plain(f"\n✨ {fallback_title}")])
            else:
                # 纯文本模式
                yield event.plain_result(str(data))
        finally:
            # 发送完成后清理本地产生的临时文件
            if isinstance(data, str) and os.path.isabs(data) and os.path.exists(data):
                with contextlib.suppress(OSError):
                    os.remove(data)
                    logger.debug(f"[UApiPro] 已清理临时文件: {data}")

    async def _send_analysis_report(self, event: AstrMessageEvent, html: str, title: str) -> AsyncGenerator:
        """调用渲染引擎处理 HTML，并清理渲染产生的缓存图片"""
        if self.plugin_config.get("uapi_text_mode", False):
            yield event.plain_result(self._parse_to_text(html))
            return

        image_path = None
        async with self.render_lock:
            try:
                if hasattr(self, "html_render"):
                    image_path = await self.html_render(html, {})
                    if image_path:
                        yield event.chain_result([Image(file=image_path), Plain(f"\n✨ {title}")])
            except Exception as e:
                logger.warning(f"[UApiPro] 渲染失败，降级为纯文本: {e}")
            finally:
                # 清理 html_render 产生的截图缓存
                if image_path and isinstance(image_path, str) and os.path.exists(image_path):
                    with contextlib.suppress(OSError):
                        os.remove(image_path)
                        logger.debug(f"[UApiPro] 已清理渲染缓存图: {image_path}")

        # 渲染失败则走纯文本兜底
        if not image_path:
            yield event.plain_result(self._parse_to_text(html))

    async def _check_cd(self, event: AstrMessageEvent) -> tuple[bool, float]:
        """带内存保护的冷却检查逻辑"""
        user_id = event.get_sender_id()
        async with self.cd_lock:
            # 限制记录字典大小，防止内存溢出
            if len(self.last_call_times) > 1000:
                keys = list(self.last_call_times.keys())
                for _ in range(200): 
                    self.last_call_times.pop(random.choice(keys), None)
            
            now = time.time()
            cd_sec = self.plugin_config.get("uapi_cd", 5.0)
            elapsed = now - self.last_call_times.get(user_id, 0)
            if elapsed < cd_sec: 
                return True, round(cd_sec - elapsed, 1)
            
            self.last_call_times[user_id] = now
            return False, 0

    # ================================================================
    # 2. 查询处理器 (Query Handler)
    # ================================================================
    
    async def _handle_query(self, event: AstrMessageEvent, api_module: str, pattern: str, title: str, max_len: int = 150):
        """通用查询处理器，支持参数校验与动态加载"""
        if api_module not in self.ALLOWED_MODULES:
            yield event.plain_result("❌ 调用的模块未授权")
            return

        arg = re.split(pattern, event.message_str.strip(), maxsplit=1)[-1].strip()
        
        if not arg:
            # 避免 f-string 内部使用反斜杠以兼容 Python 3.10
            usage_hint = pattern.replace(r'u\s+', '/u ')
            yield event.plain_result(f"❓ 用法示例：{usage_hint} <内容>")
            return
            
        if len(arg) > max_len:
            yield event.plain_result(f"❌ 输入内容过长 (限制 {max_len} 字符)")
            return

        try:
            # 按需动态加载 API 模块
            module = importlib.import_module(f".apis.{api_module}", __package__)
            api_coro = module.fetch(arg, self.plugin_config.get("uapi_token", ""))
            async for r in self._relay(event, api_coro, title):
                yield r
        except Exception as e:
            logger.error(f"[UApiPro] 模块 {api_module} 加载失败: {e}")
            yield event.plain_result(f"❌ 功能模块执行失败")

    # ================================================================
    # 3. 指令处理器 (Handlers)
    # ================================================================

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
        async for r in self._relay(event, hitokoto.fetch(self.plugin_config.get("uapi_token", "")), "今日一言"):
            yield r

    @filter.command("u 随机图片")
    async def cmd_random_img(self, event: AstrMessageEvent):
        # 从配置的分类中随机挑选一个
        cats = self.plugin_config.get("random_img_categories", [])
        selected = random.choice(cats) if cats else None
        from .apis import random_img
        async for r in self._relay(event, random_img.fetch(selected, token=self.plugin_config.get("uapi_token", "")), f"随机图片 ({selected})"):
            yield r

    @filter.command("u 新闻")
    async def cmd_news(self, event: AstrMessageEvent):
        from .apis import news
        async for r in self._relay(event, news.fetch(self.plugin_config.get("uapi_token", "")), "每日新闻"):
            yield r

    @filter.command("u 帮助")
    async def cmd_help(self, event: AstrMessageEvent):
        msg = "📦 UApiPro 工具箱\n━━━━━━\n✨ /u 一言\n🌤️ /u 天气 <城市>\n🌐 /u ip <IP>\n🎮 /u mc <地址>\n📰 /u 新闻\n🖼️ /u 随机图片"
        yield event.plain_result(msg)

    # ================================================================
    # 4. 广播与定时任务 (Scheduler)
    # ================================================================

    async def _news_scheduler(self):
        """早报定时推送调度器"""
        now = datetime.datetime.now()
        target_str = self.plugin_config.get("news_schedule_time", "08:00").replace("：", ":").strip()
        last_date = None
        
        # 重载保护：避免在重启后重复发送当天的早报
        try:
            h, m = map(int, target_str.split(":"))
            if now >= now.replace(hour=h, minute=m, second=0): 
                last_date = now.date()
        except: pass

        while True:
            await asyncio.sleep(30)
            try:
                if self.plugin_config.get("news_schedule_enabled", False):
                    now = datetime.datetime.now()
                    target_str = self.plugin_config.get("news_schedule_time", "08:00").replace("：", ":").strip()
                    h, m = map(int, target_str.split(":"))

                    if now.hour == h and now.minute == m and last_date != now.date():
                        last_date = now.date()
                        await self._broadcast_news()
            except Exception as e: 
                logger.error(f"[UApiPro] 调度器循环报错: {e}")

    async def _broadcast_news(self):
        """跨平台早报推送，带推送后自动清理功能"""
        from .apis import news
        from astrbot.api.event import MessageChain
        groups, users = self.plugin_config.get("news_groups", []), self.plugin_config.get("news_users", [])
        if not groups and not users: return
        
        plat = "default"
        try:
            all_plats = self.context.get_all_platforms()
            if all_plats: plat = list(all_plats.keys())[0]
        except: pass

        ok, path, err = await news.fetch(self.plugin_config.get("uapi_token", ""))
        if not ok: return
        
        try:
            # 依次推送至配置的群聊
            for gid in groups:
                try:
                    umo = str(gid) if ":" in str(gid) else f"{plat}:GroupMessage:{gid}"
                    await self.context.send_message(umo, MessageChain().file_image(path).message("\n📰 每日早报"))
                except: pass
                await asyncio.sleep(1.5)
            # 依次推送至配置的用户
            for uid in users:
                try:
                    umo = str(uid) if ":" in str(uid) else f"{plat}:FriendMessage:{uid}"
                    await self.context.send_message(umo, MessageChain().file_image(path).message("\n📰 每日早报"))
                except: pass
                await asyncio.sleep(1.5)
        finally:
            # 广播结束后删除生成的临时图片
            if path and os.path.exists(path):
                with contextlib.suppress(OSError):
                    os.remove(path)

    def _parse_to_text(self, html: str) -> str:
        """解析 HTML 为纯文本作为渲染失败时的兜底"""
        try:
            m = re.search(r'header-title">(.*?)<', html)
            title = m.group(1) if m else "查询结果"
            rows = re.findall(r'section-title">.*?</div>\s*(.*?)\s*</div.*?section-content">\s*(.*?)\s*</div>', html, re.S)
            res =[f"📊 {title}", "━━━━━━━━━━━━━━"]
            for label, val in rows:
                clean_label = re.sub(r'<[^>]+>', '', label).strip()
                clean_val = re.sub(r'<[^>]+>', '', val).strip()
                res.append(f"📍 {clean_label}: {clean_val}")
            return "\n".join(res)
        except: 
            return "📊 结果解析失败。"

    async def terminate(self):
        """卸载插件时清理协程任务"""
        if hasattr(self, 'bg_task'): 
            self.bg_task.cancel()
        logger.info("[UApiPro] 插件卸载完成。")
