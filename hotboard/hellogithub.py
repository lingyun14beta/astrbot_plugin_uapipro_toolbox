"""
hotboard/hellogithub.py — HelloGitHub 热榜解析器
取前10条，含编程语言、仓库名、简介。
"""

LIMIT = 10
SUMMARY_MAX = 60  # 简介截断字符数


def parse(items: list) -> list[dict]:
    result = []
    for item in items[:LIMIT]:
        extra = item.get("extra", {})
        summary = extra.get("summary", "")
        if len(summary) > SUMMARY_MAX:
            summary = summary[:SUMMARY_MAX] + "…"
        result.append({
            "index":     item.get("index", 0),
            "title":     item.get("title", ""),
            "hot_value": item.get("hot_value", ""),
            "cover":     "",
            "url":       item.get("url", ""),
            "extra": {
                "primary_lang": extra.get("primary_lang", ""),
                "full_name":    extra.get("full_name", ""),
                "summary":      summary,
            },
        })
    return result
