"""
hotboard/weread.py — 微信读书热榜解析器
取前10条，封面在 extra.cover，含作者和在读人数。
"""

LIMIT = 10


def parse(items: list) -> list[dict]:
    result = []
    for item in items[:LIMIT]:
        extra = item.get("extra", {})
        result.append({
            "index":     item.get("index", 0),
            "title":     item.get("title", ""),
            "hot_value": item.get("hot_value", ""),
            "cover":     extra.get("cover", ""),
            "url":       item.get("url", ""),
            "extra": {
                "author": extra.get("author", ""),
            },
        })
    return result
