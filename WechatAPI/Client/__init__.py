from WechatAPI.errors import *
from .base import WechatAPIClientBase, Proxy, Section
from .chatroom import ChatroomMixin
from .friend import FriendMixin
from .hongbao import HongBaoMixin
from .login import LoginMixin
from .message import MessageMixin
from .protect import protector
from .protect import protector
from .tool import ToolMixin
from .user import UserMixin
from .websocket import WebSocketMixin


class WechatAPIClient(LoginMixin, MessageMixin, WebSocketMixin, FriendMixin, ChatroomMixin, UserMixin,
                      ToolMixin, HongBaoMixin):

    # 这里都是需要结合多个功能的方法

    async def send_at_message(self, wxid: str, content: str, at: list[str]) -> tuple[int, int, int]:
        """
        发送@消息
        :param wxid: 接收人
        :param content: str
        :param at: list[str]
        :return: int, int, int (int: ClientMsgid, int: CreateTime, int: NewMsgId)
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")
        elif not self.ignore_protect and protector.check(14400):
            raise BanProtection("登录新设备后4小时内请不要操作以避免风控")

        output = ""
        for id in at:
            nickname = await self.get_nickname(id)
            output += f"@{nickname}\u2005"

        output += content

        return await self.send_text_message(wxid, output, at)
