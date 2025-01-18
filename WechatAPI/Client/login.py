from typing import Union

import aiohttp
import qrcode

from .base import *
from .protect import protector
from ..errors import *


class LoginMixin(WechatAPIClientBase):
    async def is_running(self) -> bool:
        """
        检查WechatAPI是否在运行
        :return:
        """
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.get(f'http://{self.ip}:{self.port}/IsRunning')
                return await response.text() == 'OK'
        except aiohttp.client_exceptions.ClientConnectorError:
            return False

    async def get_qr_code(self, device_name: str, device_id: str = "", proxy: Proxy = None, print_qr: bool = False) -> (
            str, str):
        """
        获取登录二维码
        :param device_name:
        :param device_id:
        :param proxy: A Proxy dataclass object
        :param print_qr: bool, whether print QR code to console
        :return: str Login QR code UUID
        """
        async with aiohttp.ClientSession() as session:
            json_param = {'DeviceName': device_name, 'DeviceID': device_id}
            if proxy:
                json_param['ProxyInfo'] = {'ProxyIp': f'{proxy.ip}:{proxy.port}',
                                           'ProxyPassword': proxy.password,
                                           'ProxyUser': proxy.username}

            response = await session.post(f'http://{self.ip}:{self.port}/GetQRCode', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):

                if print_qr:
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=10,
                        border=4,
                    )
                    qr.add_data(f'http://weixin.qq.com/x/{json_resp.get("Data").get("Uuid")}')
                    qr.print_ascii()

                return json_resp.get("Data").get("Uuid"), json_resp.get("Data").get("QRCodeURL")
            else:
                self.error_handler(json_resp)

    async def check_login_uuid(self, uuid: str, awaken_login: bool = False) -> tuple[bool, Union[dict, int]]:
        """
        检查登录的UUID
        :param uuid: 登录的UUID，从获取二维码或者唤醒登录时获取
        :param awaken_login: 是否是唤醒登录
        :return: bool, int (bool: True if logged in, int: expired time if not logged in)
        """
        async with aiohttp.ClientSession() as session:
            json_param = {"Uuid": uuid}
            response = await session.post(f'http://{self.ip}:{self.port}/CheckUuid', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                if json_resp.get("Data").get("acctSectResp", ""):
                    self.wxid = json_resp.get("Data").get("acctSectResp").get("userName")
                    self.nickname = json_resp.get("Data").get("acctSectResp").get("nickName")
                    protector.update_login_time(awaken_login=awaken_login)
                    return True, json_resp.get("Data")
                else:
                    return False, json_resp.get("Data").get("expiredTime")
            else:
                self.error_handler(json_resp)

    async def log_out(self) -> bool:
        """
        登出
        :return: bool 成功返回True, 失败False或者报错
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid}
            response = await session.post(f'http://{self.ip}:{self.port}/Logout', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return True
            elif json_resp.get("Success"):
                return False
            else:
                self.error_handler(json_resp)

    async def awaken_login(self, wxid: str = "") -> str:
        """
        唤醒登录
        :return: str (str: Uuid)
        """
        if not wxid and not self.wxid:
            raise Exception("Please login using QRCode first")

        if not wxid and self.wxid:
            wxid = self.wxid

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": wxid}
            response = await session.post(f'http://{self.ip}:{self.port}/AwakenLogin', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success") and json_resp.get("Data").get("QrCodeResponse").get("Uuid"):
                return json_resp.get("Data").get("QrCodeResponse").get("Uuid")
            elif not json_resp.get("Data").get("QrCodeResponse").get("Uuid"):
                raise LoginError("Please login using QRCode first")
            else:
                self.error_handler(json_resp)

    async def get_cached_info(self, wxid: str = None) -> dict:
        """
        获取登陆缓存信息
        :param wxid: 要查询的wxid
        :return:
        """
        if not wxid:
            wxid = self.wxid

        if not wxid:
            return {}

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": wxid}
            response = await session.post(f'http://{self.ip}:{self.port}/GetCachedInfo', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return json_resp.get("Data")
            else:
                return {}

    async def heartbeat(self) -> bool:
        """
        心跳
        :return: bool 成功返回True, 失败False或者报错
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid}
            response = await session.post(f'http://{self.ip}:{self.port}/Heartbeat', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return True
            else:
                self.error_handler(json_resp)

    async def start_auto_heartbeat(self) -> bool:
        """
        开始自动心跳
        :return: bool 成功返回True, 失败False或者报错
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid}
            response = await session.post(f'http://{self.ip}:{self.port}/AutoHeartbeatStart', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return True
            else:
                self.error_handler(json_resp)

    async def stop_auto_heartbeat(self) -> bool:
        """
        停止自动心跳
        :return: bool 成功返回True, 失败False或者报错
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid}
            response = await session.post(f'http://{self.ip}:{self.port}/AutoHeartbeatStop', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return True
            else:
                self.error_handler(json_resp)

    async def get_auto_heartbeat_status(self) -> bool:
        """
        获取自动心跳状态
        :return: bool (True if running, False if stopped)
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid}
            response = await session.post(f'http://{self.ip}:{self.port}/AutoHeartbeatStatus', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return json_resp.get("Data").get("Running")
            else:
                return self.error_handler(json_resp)
