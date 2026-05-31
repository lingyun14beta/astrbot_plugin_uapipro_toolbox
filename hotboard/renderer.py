"""
hotboard/renderer.py — 热榜 HTML 渲染器
根据平台类型调用对应解析器，生成完整 HTML 字符串。
"""

import os
import re
import html
import base64
from datetime import datetime, timezone

from . import bilibili, acfun, hellogithub, netease_music, qq_music, weread

# 平台 id → (解析器, 主题色, 图标文件名)
PLATFORM_CONFIG = {
    "bilibili":     (bilibili,     "#FB7299", "bilibili.png"),
    "acfun":        (acfun,        "#FD4061", "acfun.png"),
    "hellogithub":  (hellogithub,  "#24292F", "hellogithub.png"),
    "netease-music":(netease_music,"#C20C0C", "netease_music.png"),
    "qq-music":     (qq_music,     "#1DB954", "qq_music.png"),
    "weread":       (weread,       "#07C160", "weread.png"),
}

ICONS_DIR = os.path.join(os.path.dirname(__file__), "icons")


def _load_icon_b64(filename: str) -> str:
    """将图标文件读取为 base64 data URI，失败时返回空字符串。"""
    path = os.path.join(ICONS_DIR, filename)
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        ext = filename.rsplit(".", 1)[-1].lower()
        mime = "image/png" if ext == "png" else f"image/{ext}"
        return f"data:{mime};base64,{b64}"
    except Exception:
        return ""


def _fmt_update_time(raw: str) -> str:
    """将 ISO 时间字符串格式化为 HH:MM，解析失败则原样返回。"""
    try:
        # 兼容带 Z 和不带 Z 的 ISO 格式
        raw_clean = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw_clean)
        # 转本地时间（UTC+8）
        dt_local = dt.astimezone(timezone.utc).replace(tzinfo=None)
        # 粗略加8小时
        from datetime import timedelta
        dt_local = dt + timedelta(hours=8)
        return dt_local.strftime("%H:%M")
    except Exception:
        # 如果已经是 "2026-05-30 17:45:30" 格式
        try:
            dt = datetime.strptime(raw[:16], "%Y-%m-%d %H:%M")
            return dt.strftime("%H:%M")
        except Exception:
            return raw[:5] if len(raw) >= 5 else raw


def _render_item_with_cover(item: dict, accent: str, platform_id: str) -> str:
    """渲染带封面的条目（bilibili / 音乐 / 读书）。"""
    rank = item["index"]
    rank_color = accent if rank <= 3 else "#86868B"
    title = html.escape(item["title"])
    cover = html.escape(item.get("cover", ""))
    extra = item.get("extra", {})

    cover_html = (
        f'<img class="cover" src="{cover}" referrerpolicy="no-referrer" '
        f'onerror="this.style.background=\'#F0F0F0\';this.src=\'\'" />'
        if cover else '<div class="cover cover-placeholder"></div>'
    )

    # 副信息行：根据平台组装
    meta_parts = []
    if platform_id == "bilibili":
        up = html.escape(extra.get("up_name", ""))
        hot = html.escape(item.get("hot_value", ""))
        if up:
            meta_parts.append(f'<span class="meta-sub">UP: {up}</span>')
        if hot:
            meta_parts.append(f'<span class="meta-hot">{hot}</span>')
    elif platform_id in ("netease-music", "qq-music"):
        artist = html.escape(extra.get("artist_names", ""))
        album  = html.escape(extra.get("album", ""))
        dur    = html.escape(extra.get("duration_text", ""))
        if artist:
            meta_parts.append(f'<span class="meta-sub">{artist}</span>')
        sub2_parts = []
        if album:
            sub2_parts.append(album)
        if dur:
            sub2_parts.append(dur)
        if sub2_parts:
            meta_parts.append(f'<span class="meta-hot">{" · ".join(sub2_parts)}</span>')
    elif platform_id == "weread":
        author = html.escape(extra.get("author", ""))
        hot    = html.escape(item.get("hot_value", ""))
        if author:
            meta_parts.append(f'<span class="meta-sub">{author}</span>')
        if hot:
            meta_parts.append(f'<span class="meta-hot">{hot}</span>')

    meta_html = "".join(meta_parts)

    return f"""
    <div class="item">
      <span class="rank" style="color:{rank_color};">{rank}</span>
      {cover_html}
      <div class="info">
        <div class="title">{title}</div>
        <div class="meta">{meta_html}</div>
      </div>
    </div>"""


def _render_item_text(item: dict, accent: str, platform_id: str) -> str:
    """渲染纯文字条目（acfun / hellogithub）。"""
    rank = item["index"]
    rank_color = accent if rank <= 3 else "#86868B"
    title = html.escape(item["title"])
    extra = item.get("extra", {})

    meta_parts = []
    summary_html = ""

    if platform_id == "hellogithub":
        lang      = html.escape(extra.get("primary_lang", ""))
        full_name = html.escape(extra.get("full_name", ""))
        hot       = html.escape(item.get("hot_value", ""))
        summary   = html.escape(extra.get("summary", ""))
        if lang:
            meta_parts.append(f'<span class="badge">{lang}</span>')
        if full_name:
            meta_parts.append(f'<span class="meta-sub">{full_name}</span>')
        if hot:
            meta_parts.append(f'<span class="meta-hot">{hot}</span>')
        if summary:
            summary_html = f'<div class="summary">{summary}</div>'
    else:
        # acfun
        hot = html.escape(item.get("hot_value", ""))
        if hot:
            meta_parts.append(f'<span class="meta-hot">{hot}</span>')

    meta_html = "".join(meta_parts)

    return f"""
    <div class="item-plain">
      <span class="rank" style="color:{rank_color};">{rank}</span>
      <div class="info">
        <div class="title">{title}</div>
        <div class="meta">{meta_html}</div>
        {summary_html}
      </div>
    </div>"""


def render_hotboard(platform_id: str, display_name: str, update_time: str, raw_items: list) -> str:
    """
    生成完整热榜 HTML 字符串。
    由 fetcher.py 调用，结果传给 _send_analysis_report 渲染截图。
    """
    parser_mod, accent, icon_file = PLATFORM_CONFIG[platform_id]
    items = parser_mod.parse(raw_items)

    has_cover = platform_id in ("bilibili", "netease-music", "qq-music", "weread")
    time_str = _fmt_update_time(update_time)
    icon_b64 = _load_icon_b64(icon_file)
    icon_html = (
        f'<img class="header-icon" src="{icon_b64}" />'
        if icon_b64
        else f'<div class="header-icon header-icon-fallback" style="background:{accent};"></div>'
    )

    items_html = ""
    for item in items:
        if has_cover:
            items_html += _render_item_with_cover(item, accent, platform_id)
        else:
            items_html += _render_item_text(item, accent, platform_id)

    cover_css = """
        .cover {
            width: 120px; height: 75px; border-radius: 8px;
            object-fit: cover; flex-shrink: 0;
            background: #F0F0F0;
        }
        .cover-placeholder { background: #F0F0F0; }
        .cover-sq {
            width: 56px; height: 56px; border-radius: 6px;
            object-fit: cover; flex-shrink: 0;
            background: #F0F0F0;
        }
    """ if has_cover else ""

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=500">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html {{ background: #FFFFFF; display: table; width: 100%; }}
    body {{
      display: table-cell;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", sans-serif;
    }}
    .card {{
      width: 100%;
      background: #FFFFFF;
      overflow: hidden;
    }}
    .header {{
      padding: 18px 20px 15px;
      border-bottom: 1px solid #F0F0F0;
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .header-icon {{
      width: 28px; height: 28px; border-radius: 6px;
      object-fit: contain; flex-shrink: 0;
    }}
    .header-icon-fallback {{
      width: 28px; height: 28px; border-radius: 6px; flex-shrink: 0;
    }}
    .header-title {{
      font-size: 16px; font-weight: 600; color: #1D1D1F;
    }}
    .header-time {{
      font-size: 12px; color: #AEAEB2; margin-left: auto;
    }}
    .item {{
      display: flex; gap: 14px;
      padding: 12px 20px;
      border-bottom: 1px solid #F5F5F7;
      align-items: center;
    }}
    .item:last-child {{ border-bottom: none; }}
    .item-plain {{
      display: flex; gap: 14px;
      padding: 10px 20px;
      border-bottom: 1px solid #F5F5F7;
      align-items: flex-start;
    }}
    .item-plain:last-child {{ border-bottom: none; }}
    .rank {{
      font-size: 15px; font-weight: 600;
      width: 22px; flex-shrink: 0; text-align: center;
    }}
    .info {{ flex: 1; min-width: 0; }}
    .title {{
      font-size: 13px; color: #1D1D1F; line-height: 1.5;
      display: -webkit-box; -webkit-line-clamp: 2;
      -webkit-box-orient: vertical; overflow: hidden;
      font-weight: 500;
    }}
    .meta {{
      display: flex; gap: 8px; margin-top: 5px;
      align-items: center; flex-wrap: wrap;
    }}
    .meta-sub {{ font-size: 11px; color: #636366; }}
    .meta-hot {{ font-size: 11px; color: #AEAEB2; margin-left: auto; white-space: nowrap; }}
    .badge {{
      font-size: 10px; padding: 1px 6px; border-radius: 3px;
      background: #F2F2F7; color: #636366; flex-shrink: 0;
    }}
    .summary {{
      font-size: 11px; color: #AEAEB2; margin-top: 4px;
      line-height: 1.6;
      word-break: break-all;
      overflow-wrap: break-word;
      white-space: normal;
    }}
    .footer {{
      padding: 12px 20px;
      background: #FAFAFA;
      border-top: 1px solid #F0F0F0;
      display: flex; justify-content: space-between;
      font-size: 11px; color: #AEAEB2;
    }}
    {cover_css}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      {icon_html}
      <span class="header-title">{html.escape(display_name)}</span>
      <span class="header-time">更新于 {html.escape(time_str)}</span>
    </div>
    {items_html}
    <div class="footer">
      <span>Powered by UApiPro</span>
      <span>{datetime.now().strftime("%Y-%m-%d %H:%M")}</span>
    </div>
  </div>
</body>
</html>"""