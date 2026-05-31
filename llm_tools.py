"""
UApiPro LLM 工具模块
将各 API 包装为 AstrBot function calling 工具，供 LLM 自动调用。
在 main.py 的 __init__ 末尾加入：
    from .llm_tools import register_llm_tools
    register_llm_tools(self)
"""

from dataclasses import field
from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext
from astrbot.api import logger

# 全局持有插件实例，注册时写入
_plugin_instance = None


def _token() -> str:
    return _plugin_instance.plugin_config.get("uapi_token", "")


def _session():
    return _plugin_instance.session


async def _call_api(coro) -> str:
    """统一调用 API 并返回文本结果。"""
    try:
        ok, data, err = await coro
    except Exception as e:
        return f"调用失败：{e}"

    if not ok:
        return err or "请求失败，请稍后再试。"

    # HTML 卡片 → 提取文本
    if isinstance(data, str) and ("<html" in data.lower() or "<style" in data):
        return _plugin_instance._parse_to_text(data)

    # 图片路径（工具模式不发图，只返回说明）
    if isinstance(data, str) and data.endswith(('.jpg', '.png', '.jpeg')):
        return err if (err and len(err) > 10) else "图片已生成"

    return str(data) if data else (err or "无结果")


# ── 有参数的查询类工具 ───────────────────────────────────────────────────────

@dataclass
class WeatherTool(FunctionTool[AstrAgentContext]):
    name: str = "uapi_weather"
    description: str = "查询指定城市的实时天气、温度、空气质量及生活建议。"
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "要查询天气的城市名，例如：北京、上海、广州"}
        },
        "required": ["city"]
    })

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        from .apis import weather
        city = kwargs.get("city", "").strip()[:40]
        if not city:
            return "请提供城市名称。"
        return await _call_api(weather.fetch(city, _token(), session=_session()))


@dataclass
class IpQueryTool(FunctionTool[AstrAgentContext]):
    name: str = "uapi_ip_query"
    description: str = "查询 IP 地址或域名的地理位置、运营商及 ASN 信息。"
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "要查询的 IP 地址或域名，例如：8.8.8.8、example.com"}
        },
        "required": ["target"]
    })

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        from .apis import ipquery
        target = kwargs.get("target", "").strip()[:100]
        if not target:
            return "请提供 IP 地址或域名。"
        return await _call_api(ipquery.fetch(target, _token(), session=_session()))


@dataclass
class McServerTool(FunctionTool[AstrAgentContext]):
    name: str = "uapi_mc_server"
    description: str = "查询 Minecraft 服务器的在线状态、版本号及在线玩家数量。"
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "address": {"type": "string", "description": "Minecraft 服务器地址，例如：hypixel.net 或 play.example.com:25565"}
        },
        "required": ["address"]
    })

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        from .apis import mcquery
        address = kwargs.get("address", "").strip()[:100]
        if not address:
            return "请提供服务器地址。"
        return await _call_api(mcquery.fetch(address, _token(), session=_session()))


@dataclass
class McUserTool(FunctionTool[AstrAgentContext]):
    name: str = "uapi_mc_player"
    description: str = "查询 Minecraft 正版账号的皮肤预览及更名历史。"
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "username": {"type": "string", "description": "Minecraft 正版用户名，例如：Notch"}
        },
        "required": ["username"]
    })

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        from .apis import mc_user
        username = kwargs.get("username", "").strip()[:20]
        if not username:
            return "请提供 Minecraft 用户名。"
        return await _call_api(mc_user.fetch(username, _token(), session=_session()))


@dataclass
class WhoisTool(FunctionTool[AstrAgentContext]):
    name: str = "uapi_whois"
    description: str = "查询域名的 WHOIS 信息，包括注册商、到期日期及 DNS 服务器。"
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "domain": {"type": "string", "description": "要查询的域名，例如：example.com"}
        },
        "required": ["domain"]
    })

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        from .apis import whois
        domain = kwargs.get("domain", "").strip()[:100]
        if not domain:
            return "请提供域名。"
        return await _call_api(whois.fetch(domain, _token(), session=_session()))


@dataclass
class IcpTool(FunctionTool[AstrAgentContext]):
    name: str = "uapi_icp"
    description: str = "查询域名的 ICP 备案信息，包括备案主体、性质及备案号。"
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "domain": {"type": "string", "description": "要查询备案的域名，例如：example.com"}
        },
        "required": ["domain"]
    })

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        from .apis import icp
        domain = kwargs.get("domain", "").strip()[:100]
        if not domain:
            return "请提供域名。"
        return await _call_api(icp.fetch(domain, _token(), session=_session()))


@dataclass
class TrackingTool(FunctionTool[AstrAgentContext]):
    name: str = "uapi_tracking"
    description: str = "查询快递物流实时轨迹，自动识别快递公司。"
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "tracking_number": {"type": "string", "description": "快递单号，例如：SF1234567890"}
        },
        "required": ["tracking_number"]
    })

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        from .apis import tracking
        number = kwargs.get("tracking_number", "").strip()[:50]
        if not number:
            return "请提供快递单号。"
        return await _call_api(tracking.fetch(number, _token(), session=_session()))


@dataclass
class HolidayTool(FunctionTool[AstrAgentContext]):
    name: str = "uapi_holiday"
    description: str = "查询万年历信息，包括农历、干支、法定节假日及调休安排。可查询具体日期或月份。"
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "要查询的日期，格式 YYYY-MM-DD 或 YYYY-MM，留空则查今天"}
        },
        "required": []
    })

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        from .apis import holiday
        date = kwargs.get("date", "").strip()[:20]
        return await _call_api(holiday.fetch(date, _token(), session=_session()))



@dataclass
class GithubTool(FunctionTool[AstrAgentContext]):
    name: str = "uapi_github"
    description: str = "查询 GitHub 仓库信息，包括 Star 数、Fork 数、编程语言分布及最新 Release。"
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "仓库名称或链接，例如：owner/repo 或 https://github.com/owner/repo"}
        },
        "required": ["repo"]
    })

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        from .apis import github
        repo = kwargs.get("repo", "").strip()[:200]
        if not repo:
            return "请提供仓库名称或链接。"
        return await _call_api(github.fetch(repo, _token(), session=_session()))


@dataclass
class SteamTool(FunctionTool[AstrAgentContext]):
    name: str = "uapi_steam"
    description: str = "查询 Steam 用户资料，包括昵称、在线状态、勋章及头像。"
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "steam_id": {"type": "string", "description": "Steam 用户 ID 或个人主页链接"}
        },
        "required": ["steam_id"]
    })

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        from .apis import steam_user
        steam_id = kwargs.get("steam_id", "").strip()[:200]
        if not steam_id:
            return "请提供 Steam ID 或链接。"
        return await _call_api(steam_user.fetch(steam_id, _token(), session=_session()))


@dataclass
class BiliTool(FunctionTool[AstrAgentContext]):
    name: str = "uapi_bilibili"
    description: str = "查询 B 站 UP 主的详细档案及最新投稿视频列表。"
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "uid": {"type": "string", "description": "B 站用户 UID，例如：12345678"}
        },
        "required": ["uid"]
    })

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        from .apis import bili
        uid = kwargs.get("uid", "").strip()[:20]
        if not uid:
            return "请提供 B 站 UID。"
        return await _call_api(bili.fetch(uid, _token(), session=_session()))


@dataclass
class AnswerBookTool(FunctionTool[AstrAgentContext]):
    name: str = "uapi_answer_book"
    description: str = "答案之书：针对用户的问题给出一个神秘而随机的答案，适合娱乐性提问。"
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "要提问的问题，例如：我今天会发财吗？"}
        },
        "required": ["question"]
    })

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        from .apis import answer_book
        question = kwargs.get("question", "").strip()[:200]
        if not question:
            return "请提供问题。"
        return await _call_api(answer_book.fetch(question, _token(), session=_session()))


# ── 无参数工具 ───────────────────────────────────────────────────────────────

@dataclass
class HitokotoTool(FunctionTool[AstrAgentContext]):
    name: str = "uapi_hitokoto"
    description: str = "获取一条随机的一言语录，内容涵盖诗词、动漫台词或名人名言。"
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {},
        "required": []
    })

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        from .apis import hitokoto
        return await _call_api(hitokoto.fetch(_token(), session=_session()))


@dataclass
class EpicTool(FunctionTool[AstrAgentContext]):
    name: str = "uapi_epic_free"
    description: str = "查询 Epic 游戏商店当前正在免费领取的游戏，包括游戏名称及截止时间。"
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {},
        "required": []
    })

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        from .apis import epic
        return await _call_api(epic.fetch("", _token(), session=_session()))


@dataclass
class RandomStrTool(FunctionTool[AstrAgentContext]):
    name: str = "uapi_random_string"
    description: str = "生成随机字符串，可指定长度和类型（数字、十六进制、字母等），常用于生成密码或随机 token。"
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "length": {"type": "integer", "description": "生成字符串的长度，默认 16"},
            "type": {"type": "string", "description": "字符串类型：数字、十六进制、字母、混合，默认混合"}
        },
        "required": []
    })

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        from .apis import random_str
        length = str(kwargs.get("length", "")).strip()
        type_ = kwargs.get("type", "").strip()
        arg = f"{length} {type_}".strip()
        return await _call_api(random_str.fetch(arg, _token(), session=_session()))


@dataclass
class HotBoardTool(FunctionTool[AstrAgentContext]):
    name: str = "uapi_hotboard"
    description: str = (
        "获取各大平台实时热榜，返回热榜条目列表（标题、热度、UP主/歌手等副信息）。"
        "支持平台：bili（哔哩哔哩）、a站（AcFun）、github（HelloGitHub）、"
        "网易云（网易云音乐）、qq音乐（QQ音乐）、微信读书。"
    )
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "platform": {
                "type": "string",
                "description": "平台别名，可选：bili、a站、github、网易云、qq音乐、微信读书"
            }
        },
        "required": ["platform"]
    })

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        from .hotboard.fetcher import fetch, PLATFORM_MAP
        platform = kwargs.get("platform", "").strip().lower()
        if not platform:
            return "请提供平台名称，例如：bili、网易云、github"
        if platform not in PLATFORM_MAP:
            supported = "、".join(PLATFORM_MAP.keys())
            return f"不支持的平台「{platform}」，支持的平台有：{supported}"
        try:
            ok, payload, err = await fetch(platform, _token(), session=_session())
        except Exception as e:
            return f"调用失败：{e}"
        if not ok:
            return err or "请求失败，请稍后再试。"

        items        = payload["items"]
        display_name = payload["display_name"]
        platform_id  = payload["platform_id"]

        lines = [f"{display_name} 热榜"]
        for item in items:
            rank  = item["index"]
            title = item["title"]
            hot   = item.get("hot_value", "")
            extra = item.get("extra", {})

            parts = [f"#{rank} {title}"]
            if hot:
                parts.append(hot)

            if platform_id == "bilibili":
                up = extra.get("up_name", "")
                if up:
                    parts.append(f"UP: {up}")
            elif platform_id == "hellogithub":
                lang = extra.get("primary_lang", "")
                repo = extra.get("full_name", "")
                if lang:
                    parts.append(f"[{lang}]")
                if repo:
                    parts.append(repo)
            elif platform_id in ("netease-music", "qq-music"):
                artist = extra.get("artist_names", "")
                dur    = extra.get("duration_text", "")
                if artist:
                    parts.append(artist)
                if dur:
                    parts.append(dur)
            elif platform_id == "weread":
                author = extra.get("author", "")
                if author:
                    parts.append(author)

            url = item.get("url", "")
            line = "  ".join(parts)
            if url:
                line += f"\n    {url}"
            lines.append(line)

        return "\n".join(lines)


# ── 注册入口 ─────────────────────────────────────────────────────────────────

ALL_TOOL_CLASSES = [
    WeatherTool, IpQueryTool, McServerTool, McUserTool,
    WhoisTool, IcpTool, TrackingTool, HolidayTool,
    GithubTool, SteamTool, BiliTool,
    AnswerBookTool, HitokotoTool, EpicTool, RandomStrTool,
    HotBoardTool,
]


def register_llm_tools(plugin_instance):
    """在插件 __init__ 末尾调用此函数，完成所有 LLM 工具注册。"""
    global _plugin_instance
    _plugin_instance = plugin_instance
    tools = [cls() for cls in ALL_TOOL_CLASSES]
    try:
        plugin_instance.context.add_llm_tools(*tools)
        logger.info(f"[UApiPro] 已注册 {len(tools)} 个 LLM 工具")
    except Exception as e:
        logger.error(f"[UApiPro] LLM 工具注册失败: {e}")
