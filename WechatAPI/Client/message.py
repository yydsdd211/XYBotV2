import asyncio
import base64
from asyncio import Future
from asyncio import Queue, sleep
from io import BytesIO

import aiohttp
import moviepy as mp
import pysilk
from loguru import logger
from pydub import AudioSegment

from .base import *
from .protect import protector
from ..errors import *


class MessageMixin(WechatAPIClientBase):
    def __init__(self, ip: str, port: int):
        # 初始化消息队列
        super().__init__(ip, port)
        self._message_queue = Queue()
        self._is_processing = False

    async def _process_message_queue(self):
        """
        处理消息队列的异步方法
        """
        if self._is_processing:
            return

        self._is_processing = True
        while True:
            if self._message_queue.empty():
                self._is_processing = False
                break

            func, args, kwargs, future = await self._message_queue.get()
            try:
                result = await func(*args, **kwargs)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
            finally:
                self._message_queue.task_done()
                await sleep(0.5)  # 消息发送间隔0.5秒

    async def _queue_message(self, func, *args, **kwargs):
        """
        将消息添加到队列
        """
        future = Future()
        await self._message_queue.put((func, args, kwargs, future))

        if not self._is_processing:
            asyncio.create_task(self._process_message_queue())

        return await future

    async def revoke_message(self, wxid: str, client_msg_id: int, create_time: int, new_msg_id: int) -> bool:
        """
        撤回消息
        :param wxid: 接收人
        :param client_msg_id: 发送消息的返回值
        :param create_time: 发送消息的返回值
        :param new_msg_id: 发送消息的返回值
        :return: bool 成功返回True, 失败False或者报错
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")
        elif not self.ignore_protect and protector.check(14400):
            raise BanProtection("登录新设备后4小时内请不要操作以避免风控")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "ToWxid": wxid, "ClientMsgId": client_msg_id, "CreateTime": create_time,
                          "NewMsgId": new_msg_id}
            response = await session.post(f'http://{self.ip}:{self.port}/RevokeMsg', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                logger.info(f"消息撤回成功: {json_param}")
                return True
            else:
                self.error_handler(json_resp)

    async def send_text_message(self, wxid: str, content: str, at: list[str] = None) -> tuple[int, int, int]:
        """
        发送文本消息
        :param wxid: 接收人
        :param content: str
        :param at: list[str]
        :return: int, int, int (int: ClientMsgid, int: CreateTime, int: NewMsgId)
        """
        return await self._queue_message(self._send_text_message, wxid, content, at)

    async def _send_text_message(self, wxid: str, content: str, at: list[str] = None) -> tuple[int, int, int]:
        """
        实际发送文本消息的方法
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")
        elif not self.ignore_protect and protector.check(14400):
            raise BanProtection("登录新设备后4小时内请不要操作以避免风控")

        if at is None:
            at = []
        at_str = ",".join(at)

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "ToWxid": wxid, "Content": content, "Type": 1, "At": at_str}
            response = await session.post(f'http://{self.ip}:{self.port}/SendTextMsg', json=json_param)
            json_resp = await response.json()
            if json_resp.get("Success"):
                logger.info(f"发送文字消息: {json_param}")
                data = json_resp.get("Data")
                return data.get("List")[0].get("ClientMsgid"), data.get("List")[0].get("Createtime"), data.get("List")[
                    0].get("NewMsgId")
            else:
                self.error_handler(json_resp)

    async def send_image_message(self, wxid: str, image_path: str = "", image_base64: str = "") -> tuple[int, int, int]:
        """
        发送图片消息
        :param wxid: 接收人
        :param image_path: 与image_base64二选一
        :param image_base64: 与image_path二选一
        :return: str, int, int (str: ClientImgId, int: CreateTime, int: NewMsgId)
        """
        return await self._queue_message(self._send_image_message, wxid, image_path, image_base64)

    async def _send_image_message(self, wxid: str, image_path: str = "", image_base64: str = "") -> tuple[
        int, int, int]:
        if not self.wxid:
            raise UserLoggedOut("请先登录")
        elif not self.ignore_protect and protector.check(14400):
            raise BanProtection("登录新设备后4小时内请不要操作以避免风控")

        if bool(image_path) == bool(image_base64):
            raise ValueError("Please provide either image_path or image_base64")

        if image_path:
            with open(image_path, 'rb') as f:
                image_base64 = base64.b64encode(f.read()).decode()

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "ToWxid": wxid, "Base64": image_base64}
            response = await session.post(f'http://{self.ip}:{self.port}/SendImageMsg', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                json_param.pop('Base64')
                logger.info(f"发送图片消息: {json_param}")
                data = json_resp.get("Data")
                return data.get("ClientImgId").get("string"), data.get("CreateTime"), data.get("Newmsgid")
            else:
                self.error_handler(json_resp)

    async def send_video_message(self, wxid: str, video_base64: str = "", image_base64: str = "", video_path: str = "",
                                 image_path: str = "") -> tuple[int, int]:
        """
        发送视频消息
        :param wxid: 接受人
        :param video_base64: 与video_path二选一
        :param image_base64: 与image_path二选一
        :param video_path: 与video_base64二选一
        :param image_path: 与image_base64二选一
        :return: int, int (int: ClientMsgid, int: NewMsgId)
        """
        return await self._queue_message(self._send_video_message, wxid, video_base64, image_base64, video_path,
                                         image_path)

    async def _send_video_message(self, wxid: str, video_base64: str = "", image_base64: str = "", video_path: str = "",
                                  image_path: str = "") -> tuple[int, int, int]:
        if not self.wxid:
            raise UserLoggedOut("请先登录")
        elif not self.ignore_protect and protector.check(14400):
            raise BanProtection("登录新设备后4小时内请不要操作以避免风控")

        if bool(video_path) == bool(video_base64):
            raise ValueError("Please provide either video_path or video_base64")
        if bool(image_path) == bool(image_base64):
            raise ValueError("Please provide either image_path or image_base64")

        # get video base64, and get duration of video, 1000unit = 1 second
        if video_path:
            with open(video_path, "rb") as video_file:
                video_base64 = base64.b64encode(video_file.read()).decode()
            video = mp.VideoFileClip(video_path)
            duration = int(video.duration * 1000)
        elif video_base64:
            video = mp.VideoFileClip(BytesIO(base64.b64decode(video_base64)))
            duration = int(video.duration * 1000)
        else:
            raise ValueError("Please provide either video_path or video_base64")

        # get image base64
        if image_path:
            with open(image_path, 'rb') as f:
                image_base64 = base64.b64encode(f.read()).decode()

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "ToWxid": wxid, "Base64": video_base64, "ImageBase64": image_base64,
                          "PlayLength": duration}
            response = await session.post(f'http://{self.ip}:{self.port}/SendVideoMsg', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                json_param.pop('Base64')
                json_param.pop('ImageBase64')
                logger.info(f"发送视频消息: {json_param}")
                data = json_resp.get("Data")
                return int(data.get("clientMsgId")), data.get("newMsgId")
            else:
                self.error_handler(json_resp)

    async def send_voice_message(self, wxid: str, voice_base64: str = "", voice_path: str = "", format: str = "amr") -> \
    tuple[int, int, int]:
        """
        发送语音消息
        :param wxid: 接受人
        :param voice_base64: amr格式 与voice_path二选一
        :param voice_path: amr格式 与voice_base64二选一
        :param format: 语音格式 默认amr，支持wav，mp3
        :return: int, int, int (int: ClientMsgid, int: CreateTime, int: NewMsgId)
        """
        return await self._queue_message(self._send_voice_message, wxid, voice_base64, voice_path, format)

    async def _send_voice_message(self, wxid: str, voice_base64: str = "", voice_path: str = "", format: str = "amr") -> \
    tuple[int, int, int]:
        if not self.wxid:
            raise UserLoggedOut("请先登录")
        elif not self.ignore_protect and protector.check(14400):
            raise BanProtection("登录新设备后4小时内请不要操作以避免风控")
        elif bool(voice_path) == bool(voice_base64):
            raise ValueError("Please provide either voice_path or voice_base64")
        elif format not in ["amr", "wav", "mp3"]:
            raise ValueError("format must be one of amr, wav, mp3")

        duration = 0
        if format == "amr":
            if voice_path:
                with open(voice_path, 'rb') as f:
                    voice_base64 = base64.b64encode(f.read()).decode()
                audio = AudioSegment.from_file(voice_path, format="amr")
                duration = len(audio)
            elif voice_base64:
                audio = AudioSegment.from_file(BytesIO(base64.b64decode(voice_base64)), format="amr")
                duration = len(audio)
        elif format == "wav":
            if voice_path:
                audio = AudioSegment.from_wav(voice_path).set_channels(1)
                duration = len(audio)
                voice_base64 = base64.b64encode(await pysilk.async_encode(audio.raw_data, sample_rate=audio.frame_rate)).decode()
            elif voice_base64:
                audio = AudioSegment.from_wav(BytesIO(base64.b64decode(voice_base64)))
                duration = len(audio)
                voice_base64 = base64.b64encode(await pysilk.async_encode(audio.raw_data, sample_rate=audio.frame_rate)).decode()
        elif format == "mp3":
            if voice_path:
                audio = AudioSegment.from_mp3(voice_path).set_channels(1)
                duration = len(audio)
                voice_base64 = base64.b64encode(await pysilk.async_encode(audio.raw_data, sample_rate=audio.frame_rate)).decode()
            elif voice_base64:
                audio = AudioSegment.from_mp3(BytesIO(base64.b64decode(voice_base64)))
                duration = len(audio)
                voice_base64 = base64.b64encode(await pysilk.async_encode(audio.raw_data,  sample_rate=audio.frame_rate)).decode()
        else:
            raise ValueError("Please provide either voice_path or voice_base64")

        format_dict = {"amr": 0, "wav": 4, "mp3": 4}

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "ToWxid": wxid, "Base64": voice_base64, "VoiceTime": duration, "Type": format_dict[format]}
            response = await session.post(f'http://{self.ip}:{self.port}/SendVoiceMsg', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                json_param.pop('Base64')
                logger.info(f"发送语音消息: {json_param}")
                data = json_resp.get("Data")
                return int(data.get("ClientMsgId")), data.get("CreateTime"), data.get("NewMsgId")
            else:
                self.error_handler(json_resp)

    async def send_link_message(self, wxid: str, url: str, title: str = "", description: str = "",
                                thumb_url: str = "") -> tuple[str, int, int]:
        """
        发送链接
        :param wxid: 接受人
        :param url: 跳转链接
        :param title: 标题
        :param description: 描述
        :param thumburl: 缩略图链接
        :return: str, int, int (str: ClientMsgid, int: CreateTime, int: NewMsgId)
        """
        return await self._queue_message(self._send_link_message, wxid, url, title, description, thumb_url)

    async def _send_link_message(self, wxid: str, url: str, title: str = "", description: str = "",
                                 thumb_url: str = "") -> tuple[int, int, int]:
        if not self.wxid:
            raise UserLoggedOut("请先登录")
        elif not self.ignore_protect and protector.check(14400):
            raise BanProtection("登录新设备后4小时内请不要操作以避免风控")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "ToWxid": wxid, "Url": url, "Title": title, "Desc": description,
                          "ThumbUrl": thumb_url}
            response = await session.post(f'http://{self.ip}:{self.port}/SendShareLink', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                logger.info(f"发送链接消息: {json_param}")
                data = json_resp.get("Data")
                return data.get("clientMsgId"), data.get("createTime"), data.get("newMsgId")
            else:
                self.error_handler(json_resp)

    async def send_emoji_message(self, wxid: str, md5: str, total_length: int) -> list[dict]:
        """
        发送表情
        :param wxid: 接受人
        :param md5: 表情md5
        :param total_length: 表情总长度
        :return: list[dict] (list of emojiItem)
        """
        return await self._queue_message(self._send_emoji_message, wxid, md5, total_length)

    async def _send_emoji_message(self, wxid: str, md5: str, total_length: int) -> tuple[int, int, int]:
        if not self.wxid:
            raise UserLoggedOut("请先登录")
        elif not self.ignore_protect and protector.check(14400):
            raise BanProtection("登录新设备后4小时内请不要操作以避免风控")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "ToWxid": wxid, "Md5": md5, "TotalLen": total_length}
            response = await session.post(f'http://{self.ip}:{self.port}/SendEmojiMsg', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                logger.info(f"发送表情消息: {json_param}")
                return json_resp.get("Data").get("emojiItem")
            else:
                self.error_handler(json_resp)

    async def send_card_message(self, wxid: str, card_wxid: str, card_nickname: str, card_alias: str = "") -> tuple[
        int, int, int]:
        """
        发送名片
        :param wxid: 接受人
        :param card_wxid: 名片wxid
        :param card_alias: 名片备注
        :param card_nickname: 名片昵称
        :return: int, int, int (int: ClientMsgid, int: CreateTime, int: NewMsgId)
        """
        return await self._queue_message(self._send_card_message, wxid, card_wxid, card_nickname, card_alias)

    async def _send_card_message(self, wxid: str, card_wxid: str, card_nickname: str, card_alias: str = "") -> tuple[
        int, int, int]:
        if not self.wxid:
            raise UserLoggedOut("请先登录")
        elif not self.ignore_protect and protector.check(14400):
            raise BanProtection("登录新设备后4小时内请不要操作以避免风控")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "ToWxid": wxid, "CardWxid": card_wxid, "CardAlias": card_alias,
                          "CardNickname": card_nickname}
            response = await session.post(f'http://{self.ip}:{self.port}/SendCardMsg', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                logger.info(f"发送名片消息: {json_param}")
                data = json_resp.get("Data")
                return data.get("List")[0].get("ClientMsgid"), data.get("List")[0].get("Createtime"), data.get("List")[
                    0].get("NewMsgId")
            else:
                self.error_handler(json_resp)

    async def send_app_message(self, wxid: str, xml: str, type: int) -> tuple[str, int, int]:
        """
        发送app消息
        :param wxid: 接受人
        :param xml: app消息xml
        :param type: app消息类型
        :return: str, int, int (str: ClientMsgid, int: CreateTime, int: NewMsgId)
        """
        return await self._queue_message(self._send_app_message, wxid, xml, type)

    async def _send_app_message(self, wxid: str, xml: str, type: int) -> tuple[int, int, int]:
        if not self.wxid:
            raise UserLoggedOut("请先登录")
        elif not self.ignore_protect and protector.check(14400):
            raise BanProtection("登录新设备后4小时内请不要操作以避免风控")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "ToWxid": wxid, "Xml": xml, "Type": type}
            response = await session.post(f'http://{self.ip}:{self.port}/SendAppMsg', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                json_param["Xml"] = json_param["Xml"].replace("\n", "")
                logger.info(f"发送app消息: {json_param}")
                return json_resp.get("Data").get("clientMsgId"), json_resp.get("Data").get(
                    "createTime"), json_resp.get("Data").get("newMsgId")
            else:
                self.error_handler(json_resp)

    async def send_cdn_file_msg(self, wxid: str, xml: str) -> tuple[str, int, int]:
        """
        转发文件消息
        :param wxid: 接收人
        :param xml: 转发的文件，收到的消息xml
        :return: str, int, int (str: ClientMsgid, int: CreateTime, int: NewMsgId)
        """
        return await self._queue_message(self._send_cdn_file_msg, wxid, xml)

    async def _send_cdn_file_msg(self, wxid: str, xml: str) -> tuple[int, int, int]:
        if not self.wxid:
            raise UserLoggedOut("请先登录")
        elif not self.ignore_protect and protector.check(14400):
            raise BanProtection("登录新设备后4小时内请不要操作以避免风控")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "ToWxid": wxid, "Content": xml}
            response = await session.post(f'http://{self.ip}:{self.port}/SendCDNFileMsg', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                logger.info(f"转发文件消息: {json_param}")
                data = json_resp.get("Data")
                return data.get("clientMsgId"), data.get("createTime"), data.get("newMsgId")
            else:
                self.error_handler(json_resp)

    async def send_cdn_img_msg(self, wxid: str, xml: str) -> tuple[str, int, int]:
        """
        转发图片消息
        :param wxid: 接收人
        :param xml: 转发的图片，收到的消息xml
        :return: str, int, int (str: ClientImgId, int: CreateTime, int: NewMsgId)
        """
        return await self._queue_message(self._send_cdn_img_msg, wxid, xml)

    async def _send_cdn_img_msg(self, wxid: str, xml: str) -> tuple[int, int, int]:
        if not self.wxid:
            raise UserLoggedOut("请先登录")
        elif not self.ignore_protect and protector.check(14400):
            raise BanProtection("登录新设备后4小时内请不要操作以避免风控")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "ToWxid": wxid, "Content": xml}
            response = await session.post(f'http://{self.ip}:{self.port}/SendCDNImgMsg', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                logger.info(f"转发图片消息: {json_param}")
                data = json_resp.get("Data")
                return data.get("ClientImgId").get("string"), data.get("CreateTime"), data.get("Newmsgid")
            else:
                self.error_handler(json_resp)

    async def send_cdn_video_msg(self, wxid: str, xml: str) -> tuple[str, int]:
        """
        转发视频消息
        :param wxid: 接受人
        :param xml: 转发的视频，收到的消息xml
        :return: tuple[str, int] (str: ClientMsgid, int: NewMsgId)
        """
        return await self._queue_message(self._send_cdn_video_msg, wxid, wxid, xml)

    async def _send_cdn_video_msg(self, wxid: str, xml: str) -> tuple[int, int, int]:
        if not self.wxid:
            raise UserLoggedOut("请先登录")
        elif not self.ignore_protect and protector.check(14400):
            raise BanProtection("登录新设备后4小时内请不要操作以避免风控")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "ToWxid": wxid, "Content": xml}
            response = await session.post(f'http://{self.ip}:{self.port}/SendCDNVideoMsg', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                logger.info(f"转发视频消息: {json_param}")
                data = json_resp.get("Data")
                return data.get("clientMsgId"), data.get("newMsgId")
            else:
                self.error_handler(json_resp)

    async def sync_message(self) -> list[dict]:
        """
        同步消息
        :return: list[dict] (list of message)
        """
        if not self.wxid:
            raise UserLoggedOut("请先登录")

        async with aiohttp.ClientSession() as session:
            json_param = {"Wxid": self.wxid, "Scene": 0, "Synckey": ""}
            response = await session.post(f'http://{self.ip}:{self.port}/Sync', json=json_param)
            json_resp = await response.json()

            if json_resp.get("Success"):
                return json_resp.get("Data")
            else:
                self.error_handler(json_resp)
