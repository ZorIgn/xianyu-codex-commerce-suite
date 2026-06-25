"""
发货服务模块

包含:
- BaseShippingService: 发货服务基类
- ConfirmShippingService: 确认发货服务
- FreeshippingService: 免拼发货服务
"""

from app.services.shipping.base import BaseShippingService
from app.services.shipping.confirm_service import ConfirmShippingService
from app.services.shipping.freeshipping_service import FreeshippingService

__all__ = [
    'BaseShippingService',
    'ConfirmShippingService',
    'FreeshippingService',
]
