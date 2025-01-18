from .base import WechatAPIClientBase, Proxy, Section
from .chatroom import ChatroomMixin
from .friend import FriendMixin
from .hongbao import HongBaoMixin
from .login import LoginMixin
from .message import MessageMixin
from .tool import ToolMixin
from .user import UserMixin
from .websocket import WebSocketMixin

class WechatAPIClient(LoginMixin, MessageMixin, WebSocketMixin, FriendMixin, ChatroomMixin, UserMixin,
                         ToolMixin, HongBaoMixin):
    pass
