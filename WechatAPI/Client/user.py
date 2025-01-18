from typing import Any

import aiohttp

from .base import *
from .protect import protector
from ..errors import *


class UserMixin(WechatAPIClientBase):
    async def get_profile(self, wxid: str = None) -> dict:
        """
        :wxid: str 用户wxid
        获取用户信息
        :return: dict
        """
        if not self.wxid and not wxid:
            raise UserLoggedOut("请先登录")

        if not wxid:
            wxid = self.wxid

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": wxid}
            response = await session.post(f'http://{self.ip}:{self.port}/GetProfile', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return json_resp.get("Data").get("userInfo")
            else:
                self.error_handler(json_resp)

    async def get_my_qrcode(self, style: int = 0) -> str:
        """
        获取个人二维码
        :param style: 二维码样式，默认为0
        :return: 图片的base64
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")
        elif protector.check(14400) and not self.ignore_protect:
            raise BanProtection("登录新设备后4小时内请不要操作以避免风控")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "Style": style}
            response = await session.post(f'http://{self.ip}:{self.port}/GetMyQRCode', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return json_resp.get("Data").get("qrcode").get("buffer")
            else:
                self.error_handler(json_resp)

    async def is_logged_in(self, wxid: str = None) -> bool:
        """
        检查是否登录
        :wxid: str 用户wxid
        :return: bool
        """
        if not wxid:
            wxid = self.wxid
        try:
            await self.get_profile(wxid)
            return True
        except:
            return False