import aiohttp
import re
from astrbot.api import logger
from ..card_renderer import render_card

API_URL = "https://uapis.cn/api/v1/github/repo"


async def fetch(arg_str: str, token: str, session: aiohttp.ClientSession = None):
    """
    GitHub 仓库查询模块
    """
    usage_hint = (
        "🐙 GitHub 查询规范：\n"
        "━━━━━━━━━━━━━━\n"
        "用法：/u github <所有者/仓库名> 或 <项目链接>\n"
        "示例：/u github torvalds/linux"
    )

    raw_input = arg_str.strip()
    if not raw_input:
        return False, "", usage_hint

    if len(raw_input) > 255:
        return False, "", "❌ 输入内容过长。"

    url_pattern = r"github\.com/([a-zA-Z0-9.\-_]+/[a-zA-Z0-9.\-_]+)"
    url_match = re.search(url_pattern, raw_input, re.I)
    repo_path = url_match.group(1) if url_match else raw_input

    if not re.match(r"^[a-zA-Z0-9.\-_]+/[a-zA-Z0-9.\-_]+$", repo_path):
        safe_repo = repo_path[:30]
        return False, "", f"❌ 格式错误：'{safe_repo}' 不符合规范。\n\n{usage_hint}"

    params = {"repo": repo_path}
    local_session = False
    if session is None:
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
                status_tags = []
                if data.get("archived"):
                    status_tags.append("📦 已归档")
                if data.get("fork"):
                    status_tags.append("🍴 Fork 项目")
                status_desc = f" ({' | '.join(status_tags)})" if status_tags else ""

                langs = data.get("languages", {})
                lang_list = sorted(langs.items(), key=lambda x: x[1], reverse=True)[:3]
                lang_str = " / ".join([f"{k}" for k, v in lang_list]) or data.get("language", "Unknown")

                topics = data.get("topics", [])
                topic_str = " | ".join(topics[:5]) if topics else "暂无标签"

                maintainers = data.get("maintainers", [])
                m_list = [m.get("login") for m in maintainers if m.get("login")][:3]
                m_str = ", ".join(m_list) if m_list else "未公开"

                fields = [
                    ("项目简介", f"📖 {data.get('description', '暂无描述')}\n🌐 {data.get('homepage', '无主页')}{status_desc}"),
                    ("核心指标", f"⭐ Stars: {data.get('stargazers', 0):,} | 🍴 Forks: {data.get('forks', 0):,}\n❗ Issues: {data.get('open_issues', 0):,} | 👁️ Watchers: {data.get('watchers', 0):,}"),
                    ("技术栈", f"🔤 语言: {lang_str}\n🏷️ 话题: {topic_str}"),
                    ("维护者", f"👥 {m_str}"),
                    ("关键日期", f"📅 创建: {str(data.get('created_at', ''))[:10]}\n🚀 最后推送: {str(data.get('pushed_at', ''))[:10]}\n📜 协议: {data.get('license', 'No License')}")
                ]

                release = data.get("latest_release")
                if release and isinstance(release, dict):
                    tag = release.get("tag_name", "N/A")
                    pub_at = str(release.get("published_at", ""))[:10]
                    fields.insert(3, ("最新版本", f"📦 {tag} ({pub_at})"))

                # 更换图标为 💻，并配合修改后的 card_renderer 防止文字飞出
                html = render_card(data.get("full_name", repo_path), "💻", fields, "#24292E")
                return True, html, ""

            api_msg = str(data.get("message", "查询失败"))[:100]
            if resp.status == 404:
                return False, "", "❌ 仓库未找到：请检查名称或链接是否正确。"
            return False, "", f"❌ 接口请求失败: {api_msg}"

    except Exception as e:
        logger.warning(f"[UApiPro] GitHub 查询异常: {e}")
        return False, "", "⚠️ 网络连接失败，请稍后再试。"
    finally:
        if local_session:
            await session.close()