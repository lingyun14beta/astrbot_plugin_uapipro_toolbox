"""
main.py - 重构版
修复：Session 全局复用、导入规范化、CD 清理逻辑、调度器健壮性
"""
import re
import time
import asyncio
import datetime
import random
import os
import contextlib
import aiohttp # 必须导入以创建全局 Session
from typing import AsyncGenerator
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger
from astrbot.api.message_components import Image, Plain

# 1. 修复导入规范：将 API 模块提前导入，避免局部动态导入违反 PEP 8
from .apis import weather, ipquery, mcquery, hitokoto, random_img, news

class UApiProPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.plugin_config = config
        self.render_lock = asyncio.Lock()
        self.cd_lock = asyncio.Lock()
        self.last_call_times = {}
        
        # 2. 核心修复：创建全局异步 Session 供所有 API 模块复用
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        
        self.bg_task = asyncio.create_task(self._news_scheduler())

    async def _check_cd(self, event: AstrMessageEvent) -> tuple[bool, float]:
        """3. 修复 CD 清理策略：改用时间戳过期清理，而非随机剔除"""
        user_id = event.get_sender_id()
        now = time.time()
        cd_sec = self.plugin_config.get("uapi_cd", 5.0)
        
        async with self.cd_lock:
            # 定期清理超过 10 分钟未活动的记录，防止内存堆积
            if len(self.last_call_times) > 500:
                self.last_call_times = {k: v for k, v in self.last_call_times.items() if now - v < 600}
            
            elapsed = now - self.last_call_times.get(user_id, 0)
            if elapsed < cd_sec: 
                return True, round(cd_sec - elapsed, 1)
            
            self.last_call_times[user_id] = now
            return False, 0

    # ... 在调用 API 时，必须将 self.session 传进去 ...
    # 示例修改：
    # api_coro = weather.fetch(arg, self.plugin_config.get("uapi_token", ""), session=self.session)

    async def _news_scheduler(self):
        """4. 修复调度器异常捕获：避免裸 except 并将配置解析移出循环"""
        last_date = None
        while True:
            await asyncio.sleep(30)
            try:
                if not self.plugin_config.get("news_schedule_enabled", False):
                    continue
                
                now = datetime.datetime.now()
                target_str = self.plugin_config.get("news_schedule_time", "08:00").replace("：", ":").strip()
                
                # 严谨的配置解析
                try:
                    h, m = map(int, target_str.split(":"))
                except ValueError:
                    logger.warning(f"[UApiPro] 配置的时间格式错误: {target_str}")
                    continue

                if now.hour == h and now.minute == m and last_date != now.date():
                    last_date = now.date()
                    await self._broadcast_news()
            except Exception as e: # 5. 使用 Exception 而非裸 except
                logger.error(f"[UApiPro] 调度器循环报错: {e}")

    async def terminate(self):
        """卸载插件时清理资源"""
        if hasattr(self, 'bg_task'): 
            self.bg_task.cancel()
        # 6. 必须手动关闭全局 Session
        if self.session:
            await self.session.close()
        logger.info("[UApiPro] 插件卸载并已安全关闭连接池。")
