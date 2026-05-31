"""
hotboard — 全网热榜聚合模块
对外暴露统一入口 fetch()，由 main.py 直接调用。
"""

from .fetcher import fetch

__all__ = ["fetch"]
