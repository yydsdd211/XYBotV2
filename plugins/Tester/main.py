import base64

from WechatAPI import WechatAPIClient
from utils.decorators import *
from utils.plugin_base import PluginBase


class Tester(PluginBase):
    description = "测试"
    author = "HenryXiaoYang"
    version = "1.0.0"

    def __init__(self):
        super().__init__()

    async def async_init(self):
        return

    @on_text_message(priority=99)
    async def on_text_1(self, bot: WechatAPIClient, message: dict):
        with open("test_vid.mp4", "rb") as f:
            file = f.read()
        file = base64.b64encode(file).decode("utf-8")
        if "测试" in message["Content"]:
            await bot.send_video_message(message["FromWxid"], file)

    @on_text_message(priority=98)
    async def on_text_2(self, bot: WechatAPIClient, message: dict):
        if "测试" in message["Content"]:
            await bot.send_text_message(message["FromWxid"], "222")
