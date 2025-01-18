import aiohttp

from .base import *
from ..errors import *


class HongBaoMixin(WechatAPIClientBase):
    async def get_hongbao_detail(self, xml: str, encrypt_key: str, encrypt_userinfo: str) -> dict:
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "Xml": xml, "EncryptKey": encrypt_key, "EncryptUserinfo": encrypt_userinfo}
            response = await session.post(f'http://{self.ip}:{self.port}/GetHongBaoDetail', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return json_resp.get("Data")
            else:
                self.error_handler(json_resp)
