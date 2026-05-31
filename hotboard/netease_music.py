"""
hotboard/netease_music.py — 网易云音乐热歌榜解析器
取前10条，含封面、歌手、专辑、时长。hot_value 全为0不显示。
"""

LIMIT = 10


def parse(items: list) -> list[dict]:
    result = []
    for item in items[:LIMIT]:
        extra = item.get("extra", {})
        result.append({
            "index":     item.get("index", 0),
            "title":     item.get("title", ""),
            "hot_value": "",
            "cover":     item.get("cover", ""),
            "url":       item.get("url", ""),
            "extra": {
                "artist_names":  extra.get("artist_names", ""),
                "album":         extra.get("album", ""),
                "duration_text": extra.get("duration_text", ""),
            },
        })
    return result
