"""
hotboard/bilibili.py — 哔哩哔哩热榜解析器
取前5条，含封面缩略图和UP主信息。
"""

LIMIT = 10
THUMB_SUFFIX = "@160w_100h_1c.webp"


def parse(items: list) -> list[dict]:
    """
    返回统一结构列表，每条包含：
      index, title, hot_value, cover(可选), extra(dict)
    """
    result = []
    for item in items[:LIMIT]:
        extra = item.get("extra", {})
        cover_raw = extra.get("pic", "")
        cover = (cover_raw + THUMB_SUFFIX) if cover_raw else ""
        result.append({
            "index":     item.get("index", 0),
            "title":     item.get("title", ""),
            "hot_value": item.get("hot_value", ""),
            "cover":     cover,
            "url":       item.get("url", ""),
            "extra": {
                "up_name": extra.get("owner", {}).get("name", ""),
            },
        })
    return result
