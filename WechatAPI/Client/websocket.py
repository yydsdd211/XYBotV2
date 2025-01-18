import aiohttp
import websockets
from websockets.asyncio.client import ClientConnection

from .base import *
from ..errors import *


class WebSocketMixin(WechatAPIClientBase):
    async def start_websocket(self, port: int = 0) -> int:
        """
        开启websocket
        :return: websocket的端口号
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        if not port:
            port = self.port+1

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "Port": port}
            response = await session.post(f'http://{self.ip}:{self.port}/WebsocketStart', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return port
            else:
                self.error_handler(json_resp)

    async def stop_websocket(self) -> bool:
        """
        关闭websocket
        :return: bool 成功返回True, 失败False或者报错
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid}
            response = await session.post(f'http://{self.ip}:{self.port}/WebsocketStop', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return True
            else:
                self.error_handler(json_resp)

    async def get_websocket_status(self) -> dict:
        """
        获取websocket状态
        :return: dict (dict of status, {"Running": bool, "Port": int})
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid}
            response = await session.post(f'http://{self.ip}:{self.port}/WebsocketStatus', json=json_param)
            json_resp = await response.json()

            data = json_resp.get("Data")
            status = {"Running": data.get("Running"), "Port": data.get("Port")}

            if json_resp.get("Success"):
                return status
            else:
                self.error_handler(json_resp)

    async def connect_websocket(self, port: int = 9001) -> ClientConnection:
        ws_url = f"ws://{self.ip}:{port}/ws?wxid={self.wxid}"
        ws = await websockets.connect(ws_url)
        return ws
