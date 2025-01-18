import base64
import io
import os
from random import choice

import aiohttp
import pysilk
from pydub import AudioSegment

from .base import *
from .protect import protector
from ..errors import *


class ToolMixin(WechatAPIClientBase):
    async def download_image(self, aeskey: str, cdnmidimgurl: str) -> str:
        """
        CDN下载高清图片
        :param aeskey:
        :param cdnmidimgurl:
        :return: str 图片的base64
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "AesKey": aeskey, "Cdnmidimgurl": cdnmidimgurl}
            response = await session.post(f'http://{self.ip}:{self.port}/CdnDownloadImg', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return json_resp.get("Data")
            else:
                self.error_handler(json_resp)

    async def download_voice(self, msg_id: str, voiceurl: str, length: int) -> str:
        """
        下载语音
        :param msg_id: 消息的msgid
        :param voiceurl: 语音的url 从xml获取
        :param length: 语音长度 从xml获取
        :return: str 语音的base64
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "MsgId": msg_id, "Voiceurl": voiceurl, "Length": length}
            response = await session.post(f'http://{self.ip}:{self.port}/DownloadVoice', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return json_resp.get("Data").get("data").get("buffer")
            else:
                self.error_handler(json_resp)

    async def download_attach(self, attach_id: str) -> dict:
        """
        下载附件
        :param attach_id:
        :return: dict
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "AttachId": attach_id}
            response = await session.post(f'http://{self.ip}:{self.port}/DownloadAttach', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return json_resp.get("Data").get("data").get("buffer")
            else:
                self.error_handler(json_resp)

    async def download_video(self, msg_id) -> str:
        """
        下载视频
        :param msg_id: 消息的msg_id
        :return: str 视频的base64
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "MsgId": msg_id}
            response = await session.post(f'http://{self.ip}:{self.port}/DownloadVideo', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return json_resp.get("Data").get("data").get("buffer")
            else:
                self.error_handler(json_resp)

    async def set_step(self, count: int) -> bool:
        """
        设置步数
        :param count: 步数
        :return: bool 成功返回True, 失败False或者报错
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")
        elif not self.ignore_protect and protector.check(14400):
            raise BanProtection("登录新设备后4小时内请不要操作以避免风控")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "StepCount": count}
            response = await session.post(f'http://{self.ip}:{self.port}/SetStep', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return True
            else:
                self.error_handler(json_resp)

    async def set_proxy(self, proxy: Proxy) -> bool:
        """
        设置代理
        :param proxy: Proxy
        :return: bool 成功返回True, 失败False或者报错
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid,
                          "Proxy": {"ProxyIp": f"{proxy.ip}:{proxy.port}",
                                    "ProxyUser": proxy.username,
                                    "ProxyPassword": proxy.password}}
            response = await session.post(f'http://{self.ip}:{self.port}/SetProxy', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return True
            else:
                self.error_handler(json_resp)

    async def check_database(self) -> bool:
        """
        检查数据库
        :return: bool
        """
        async with aiohttp.ClientSession() as session:
            response = await session.get(f'http://{self.ip}:{self.port}/CheckDatabaseOK')
            json_resp = await response.json()

            if json_resp.get("Running"):
                return True
            else:
                return False

    @staticmethod
    def base64_to_file(base64_str: str, file_name: str, file_path: str) -> bool:
        """
        将 base64 字符串转换为文件并保存
        :param base64_str: str base64 编码的字符串
        :param file_name: str 要保存的文件名
        :param file_path: str 文件保存路径
        :return: bool 转换是否成功
        """
        try:
            os.makedirs(file_path, exist_ok=True)

            # 拼接完整的文件路径
            full_path = os.path.join(file_path, file_name)

            # 移除可能存在的 base64 头部信息
            if ',' in base64_str:
                base64_str = base64_str.split(',')[1]

            # 解码 base64 并写入文件
            with open(full_path, 'wb') as f:
                f.write(base64.b64decode(base64_str))

            return True

        except Exception as e:
            return False

    @staticmethod
    def file_to_base64(file_path: str) -> str:
        """
        将文件转换为 base64 字符串
        :param file_path: str 文件路径
        :return: str base64 编码的字符串
        """
        with open(file_path, 'rb') as f:
            return base64.b64encode(f.read()).decode()

    @staticmethod
    def base64_to_byte(base64_str: str) -> bytes:
        """
        将 base64 字符串转换为 bytes
        :param base64_str: str base64 编码的字符串
        :return: bytes
        """
        # 移除可能存在的 base64 头部信息
        if ',' in base64_str:
            base64_str = base64_str.split(',')[1]

        return base64.b64decode(base64_str)

    @staticmethod
    def byte_to_base64(byte: bytes) -> str:
        """
        将 bytes 转换为 base64 字符串
        :param byte: bytes
        :return: str
        """
        return base64.b64encode(byte).decode()

    @staticmethod
    async def silk_byte_to_byte_wav_byte(silk_byte: bytes) -> bytes:
        """
        将 silk 字节转换为 wav 字节
        :param silk_byte:
        :return:
        """
        return await pysilk.async_decode(silk_byte, to_wav=True)

    @staticmethod
    def wav_byte_to_amr_byte(wav_byte: bytes) -> bytes:
        """
        将 WAV 字节数据转换为 AMR 格式
        :param wav_byte: WAV格式的字节数据
        :return: AMR格式的字节数据
        """
        try:
            # 从字节数据创建 AudioSegment 对象
            audio = AudioSegment.from_wav(io.BytesIO(wav_byte))

            # 设置 AMR 编码的标准参数
            audio = audio.set_frame_rate(8000).set_channels(1)

            # 创建一个字节缓冲区来存储 AMR 数据
            output = io.BytesIO()

            # 导出为 AMR 格式
            audio.export(output, format="amr")

            # 获取字节数据
            return output.getvalue()

        except Exception as e:
            raise Exception(f"转换WAV到AMR失败: {str(e)}")

    @staticmethod
    def wav_byte_to_amr_base64(wav_byte: bytes) -> str:
        """
        将 WAV 字节数据转换为 AMR 格式的 base64 字符串
        :param wav_byte: WAV格式的字节数据
        :return: str AMR格式的 base64 字符串
        """
        return base64.b64encode(ToolMixin.wav_byte_to_amr_byte(wav_byte)).decode()

    @staticmethod
    async def wav_byte_to_silk_byte(wav_byte: bytes) -> bytes:
        # get pcm data
        audio = AudioSegment.from_wav(io.BytesIO(wav_byte))
        pcm = audio.raw_data
        return await pysilk.async_encode(pcm, data_rate=audio.frame_rate, sample_rate=audio.frame_rate)

    @staticmethod
    async def wav_byte_to_silk_base64(wav_byte: bytes) -> str:
        return base64.b64encode(await ToolMixin.wav_byte_to_silk_byte(wav_byte)).decode()

    @staticmethod
    async def silk_base64_to_wav_byte(silk_base64: str) -> bytes:
        return await ToolMixin.silk_byte_to_byte_wav_byte(base64.b64decode(silk_base64))

    @staticmethod
    def make_device_name() -> str:
        """
        生成一个随机的设备名
        :return: str
        """
        first_names = [
            "Oliver", "Emma", "Liam", "Ava", "Noah", "Sophia", "Elijah", "Isabella",
            "James", "Mia", "William", "Amelia", "Benjamin", "Harper", "Lucas", "Evelyn",
            "Henry", "Abigail", "Alexander", "Ella", "Jackson", "Scarlett", "Sebastian",
            "Grace", "Aiden", "Chloe", "Matthew", "Zoey", "Samuel", "Lily", "David",
            "Aria", "Joseph", "Riley", "Carter", "Nora", "Owen", "Luna", "Daniel",
            "Sofia", "Gabriel", "Ellie", "Matthew", "Avery", "Isaac", "Mila", "Leo",
            "Julian", "Layla"
        ]

        last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
            "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
            "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
            "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
            "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill",
            "Flores", "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell",
            "Mitchell", "Carter", "Roberts", "Gomez", "Phillips", "Evans"
        ]

        return choice(first_names) + " " + choice(last_names) + "'s Pad"
