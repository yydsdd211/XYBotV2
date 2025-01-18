from WechatAPI import WechatAPIClient
from utils.decorators import *
from utils.plugin_base import PluginBase


class ExamplePlugin(PluginBase):
    def __init__(self):
        super().__init__()

    @on_text_message
    async def handle_text(self, bot: WechatAPIClient, message: dict):
        if not self.enabled:
            return

    @on_image_message
    async def handle_image(self, bot: WechatAPIClient, message: dict):
        if not self.enabled:
            return

    @on_voice_message
    async def handle_voice(self, bot: WechatAPIClient, message: dict):
        if not self.enabled:
            return

    @on_file_message
    async def handle_file(self, bot: WechatAPIClient, message: dict):
        if not self.enabled:
            return

    @on_pat_message
    async def handle_pat(self, bot: WechatAPIClient, message: dict):
        if not self.enabled:
            return
