import aiohttp
import base64
import re
from astrbot.api import logger
from ..card_renderer import render_card

API_URL = "https://uapis.cn/api/v1/github/user"

USERNAME_RE = re.compile(r"^[a-zA-Z0-9](?:-?[a-zA-Z0-9])*$")
USER_URL_RE = re.compile(r"github\.com/([a-zA-Z0-9](?:-?[a-zA-Z0-9]){0,38})", re.I)
AVATAR_RE = re.compile(r"^https://avatars\.githubusercontent\.com/")


def _format_count(value):
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "0"


def _repo_line(repo: dict) -> str:
    extra = []
    if repo.get("language"):
        extra.append(repo["language"])
    if repo.get("stargazers") is not None:
        extra.append(f"⭐ {_format_count(repo.get('stargazers'))}")
    if repo.get("forks") is not None:
        extra.append(f"🍴 {_format_count(repo.get('forks'))}")
    suffix = f"  [{ ' | '.join(extra) }]" if extra else ""

    desc = repo.get("description") or ""
    if desc:
        desc = " - " + (desc if len(desc) <= 30 else desc[:30] + "…")

    return f"{repo.get('full_name', repo.get('name', '?'))}{suffix}{desc}"


async def _build_card(data: dict, session: aiohttp.ClientSession) -> str:
    login = data.get("login", "Unknown")
    name = data.get("name") or login

    display_avatar = ""
    avatar_url = data.get("avatar_url")
    if avatar_url and AVATAR_RE.match(avatar_url):
        try:
            async with session.get(avatar_url, timeout=6) as img_resp:
                if img_resp.status == 200:
                    img_data = await img_resp.read()
                    mime = img_resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
                    display_avatar = f"data:{mime};base64,{base64.b64encode(img_data).decode()}"
                    del img_data
        except Exception:
            pass

    fields = []

    if display_avatar:
        fields.append(("用户头像", display_avatar))

    profile_parts = []
    if data.get("bio"):
        profile_parts.append(f"📝 {data['bio']}")
    if data.get("company"):
        profile_parts.append(f"🏢 {data['company']}")
    if data.get("location"):
        profile_parts.append(f"📍 {data['location']}")
    if data.get("blog"):
        profile_parts.append(f"🌐 {data['blog']}")
    fields.append(("个人简介", "\n".join(profile_parts) if profile_parts else "暂无简介"))

    fields.append(
        (
            "核心数据",
            f"⭐ 关注者: {_format_count(data.get('followers'))} | 👀 正在关注: {_format_count(data.get('following'))}\n"
            f"📦 公开仓库: {_format_count(data.get('public_repos'))} | 📄 公开 Gist: {_format_count(data.get('public_gists'))}",
        )
    )

    orgs = data.get("organizations") or []
    org_list = [o.get("login", "") for o in orgs if o.get("login")][:4]
    if org_list:
        fields.append(("所属组织", " / ".join(org_list)))

    activity = data.get("activity")
    if isinstance(activity, dict):
        act_parts = [
            f"🔥 年度总贡献: {_format_count(activity.get('total_contributions'))} 次",
            (
                f"✍️ 提交: {_format_count(activity.get('total_commit_contributions'))} | "
                f"🐛 Issue: {_format_count(activity.get('total_issue_contributions'))} | "
                f"🔀 PR: {_format_count(activity.get('total_pull_request_contributions'))} | "
                f"👀 Review: {_format_count(activity.get('total_pull_request_review_contributions'))}"
            ),
            (
                f"🗓️ 统计区间: {str(activity.get('from', ''))[:10]} ~ "
                f"{str(activity.get('to', ''))[:10]}"
            ),
        ]
        timeline = activity.get("timeline") or []
        if timeline:
            top = sorted(
                timeline,
                key=lambda x: x.get("contribution_count", 0) or 0,
                reverse=True,
            )[:3]
            top_str = " | ".join(
                [f"{t.get('month', '')}: {_format_count(t.get('contribution_count'))}" for t in top]
            )
            act_parts.append(f"📈 最活跃月份: {top_str}")
        fields.append(("年度贡献", "\n".join(act_parts)))
    else:
        fields.append(("年度贡献", "该用户未公开贡献数据"))

    pinned = data.get("pinned_repositories") or []
    if pinned:
        fields.append(("Pinned 仓库", "\n".join(_repo_line(r) for r in pinned[:5])))

    repos = data.get("repositories") or []
    if repos:
        fields.append(("最近活跃仓库", "\n".join(_repo_line(r) for r in repos[:5])))

    fields.append(
        (
            "账户信息",
            f"🏷️ 类型: {data.get('type', 'User')}\n"
            f"📅 注册时间: {str(data.get('created_at', ''))[:10]}\n"
            f"🔗 {data.get('html_url', '')}",
        )
    )

    html = render_card(f"{name} (@{login})", "🐙", fields, "#24292E")
    return html


async def fetch(arg_str: str, token: str, session: aiohttp.ClientSession = None):
    """
    GitHub 用户信息查询模块
    """
    usage_hint = (
        "🐙 GitHub 用户查询规范：\n"
        "━━━━━━━━━━━━━━\n"
        "用法：/u gh <用户名> 或 <主页链接>\n"
        "示例：/u gh torvalds"
    )

    raw_input = arg_str.strip()
    if not raw_input:
        return False, "", usage_hint

    if len(raw_input) > 100:
        return False, "", "❌ 输入内容过长。"

    url_match = USER_URL_RE.search(raw_input)
    username = url_match.group(1) if url_match else raw_input

    if not USERNAME_RE.match(username) or len(username) > 39:
        safe_name = username[:30]
        return False, "", f"❌ 用户名不合法：'{safe_name}' 不符合 GitHub 命名规范。\n\n{usage_hint}"

    params = {
        "user": username,
        "activity": "true",
        "pinned": "true",
        "repos": "true",
        "repos_limit": "5",
    }
    local_session = False
    if session is None or not token:
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
                html = await _build_card(data, session)
                return True, html, ""

            api_msg = str(data.get("error") or data.get("message", "查询失败"))[:100]
            if resp.status == 404:
                return False, "", "❌ 用户未找到：请检查用户名或链接是否正确。"
            return False, "", f"❌ 接口请求失败: {api_msg}"

    except Exception as e:
        logger.warning(f"[UApiPro] GitHub 用户查询异常: {e}")
        return False, "", "⚠️ 网络连接失败，请稍后再试。"
    finally:
        if local_session:
            await session.close()
