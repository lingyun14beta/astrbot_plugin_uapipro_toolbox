"""
hotboard/acfun.py — A站热榜解析器
取前10条，纯文字列表，无封面。
"""

LIMIT = 10


def parse(items: list) -> list[dict]:
    result = []
    for item in items[:LIMIT]:
        result.append({
            "index":     item.get("index", 0),
            "title":     item.get("title", ""),
            "hot_value": item.get("hot_value", ""),
            "cover":     "",
            "url":       item.get("url", ""),
            "extra":     {},
        })
    return result
