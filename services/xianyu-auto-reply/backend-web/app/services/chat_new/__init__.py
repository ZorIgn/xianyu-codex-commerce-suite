"""
在线聊天(新)服务模块

基于WebSocket API直接与闲鱼IM通信，获取会话列表和聊天记录
不依赖浏览器，轻量级实现
"""
from .im_session_manager import ImSessionManager, get_im_session_manager

__all__ = ['ImSessionManager', 'get_im_session_manager']
