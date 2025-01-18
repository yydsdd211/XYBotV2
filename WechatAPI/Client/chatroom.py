from typing import Union, Any

import aiohttp

from .base import *
from ..errors import *
from .protect import protector


class ChatroomMixin(WechatAPIClientBase):
    async def add_chatroom_member(self, chatroom: str, wxid: str) -> bool:
        """
        添加群成员(群聊最多40人)
        :param chatroom: 群聊wxid
        :param wxid: 要添加的wxid
        :return: bool 成功返回True, 失败False或者报错
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")
        elif not self.ignore_protect and protector.check(14400):
            raise BanProtection("登录新设备后4小时内请不要操作以避免风控")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "Chatroom": chatroom, "InviteWxids": wxid}
            response = await session.post(f'http://{self.ip}:{self.port}/AddChatroomMember', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return True
            else:
                self.error_handler(json_resp)

    async def get_chatroom_announce(self, chatroom: str) -> dict:
        """
        获取群聊公告
        :param chatroom: 群聊id
        :return: dict (dict of chatroom info)
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "Chatroom": chatroom}
            response = await session.post(f'http://{self.ip}:{self.port}/GetChatroomInfo', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                data = dict(json_resp.get("Data"))
                data.pop("BaseResponse")
                return data
            else:
                self.error_handler(json_resp)

    async def get_chatroom_info(self, chatroom: str) -> dict:
        """
        获取群聊信息
        :param chatroom: 群聊id
        :return: dict (dict of chatroom info)
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")
        elif not self.ignore_protect and protector.check(14400):
            raise BanProtection("登录新设备后4小时内请不要操作以避免风控")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "Chatroom": chatroom}
            response = await session.post(f'http://{self.ip}:{self.port}/GetChatroomInfoNoAnnounce', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return json_resp.get("Data").get("ContactList")[0]
            else:
                self.error_handler(json_resp)

    async def get_chatroom_member_list(self, chatroom: str) -> list[dict]:
        """
        获取群聊成员列表
        :param chatroom: 群聊id
        :return: list[dict] (list of chatroom member)
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "Chatroom": chatroom}
            response = await session.post(f'http://{self.ip}:{self.port}/GetChatroomMemberDetail', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return json_resp.get("Data").get("NewChatroomData").get("ChatRoomMember")
            else:
                self.error_handler(json_resp)

    async def get_chatroom_qrcode(self, chatroom: str) -> dict[str, Any]:
        """
        获取群聊二维码
        :param chatroom:
        :return: 二维码的base64
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")
        elif not self.ignore_protect and protector.check(86400):
            raise BanProtection("获取二维码需要在登录后24小时才可使用")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "Chatroom": chatroom}
            response = await session.post(f'http://{self.ip}:{self.port}/GetChatroomQRCode', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                data = json_resp.get("Data")
                return {"base64": data.get("qrcode").get("buffer"), "description": data.get("revokeQrcodeWording")}
            else:
                self.error_handler(json_resp)

    async def invite_chatroom_member(self, wxid: Union[str, list], chatroom: str) -> bool:
        """
        邀请群聊成员(群聊大于40人)
        :param wxid:
        :param chatroom:
        :return: bool 成功返回True, 失败False或者报错
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")
        elif not self.ignore_protect and protector.check(14400):
            raise BanProtection("登录新设备后4小时内请不要操作以避免风控")

        if isinstance(wxid, list):
            wxid = ",".join(wxid)

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "Chatroom": chatroom, "InviteWxids": wxid}
            response = await session.post(f'http://{self.ip}:{self.port}/InviteChatroomMember', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return True
            else:
                self.error_handler(json_resp)
