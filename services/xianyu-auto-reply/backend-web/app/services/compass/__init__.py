"""
Goofish 数据罗盘/分析服务

基于 Playwright + 账号 Cookie，对 Goofish 搜索与商品详情进行采集与分析。
"""

from app.services.compass.goofish_compass import GoofishCompassService

__all__ = ["GoofishCompassService"]

