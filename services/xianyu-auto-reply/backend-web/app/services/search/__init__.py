"""
商品搜索服务模块

基于Playwright实现闲鱼商品搜索功能
"""
from app.services.search.searcher import (
    ItemSearchService,
    search_xianyu_items,
    search_multiple_pages_xianyu,
)
from app.services.search.parser import ItemParser
from app.services.search.slider_handler import SliderHandler
from app.services.search.browser import BrowserManager

__all__ = [
    "ItemSearchService",
    "ItemParser",
    "SliderHandler",
    "BrowserManager",
    "search_xianyu_items",
    "search_multiple_pages_xianyu",
]
