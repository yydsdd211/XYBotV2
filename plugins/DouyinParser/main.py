import re
import tomllib
from typing import Dict, Any

import aiohttp
from loguru import logger

from WechatAPI import WechatAPIClient
from utils.decorators import on_text_message
from utils.plugin_base import PluginBase


class DouyinParserError(Exception):
    """抖音解析器自定义异常基类"""
    pass


class DouyinParser(PluginBase):
    description = "抖音无水印解析插件"
    author = "姜不吃先生"  # 群友太给力了！
    version = "1.0.2"

    def __init__(self):
        super().__init__()
        self.url_pattern = re.compile(r'https?://v\.douyin\.com/\w+/?')

        # 读取代理配置
        with open("plugins/DouyinParser/config.toml", "rb") as f:
            config = tomllib.load(f)
            self.http_proxy = config.get("DouyinParser", {}).get("http-proxy", None)

    def _clean_response_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """清理响应数据"""
        if not data:
            return data

        # 使用固定的抖音图标作为封面
        data[
            'cover'] = "https://is1-ssl.mzstatic.com/image/thumb/Purple221/v4/7c/49/e1/7c49e1af-ce92-d1c4-9a93-0a316e47ba94/AppIcon_TikTok-0-0-1x_U007epad-0-1-0-0-85-220.png/512x512bb.jpg"

        return data

    async def _get_real_video_url(self, video_url: str) -> str:
        """获取真实视频链接"""
        try:
            async with aiohttp.ClientSession(proxy=self.http_proxy) as session:
                async with session.get(video_url, allow_redirects=True, timeout=30) as response:
                    if response.status == 200:
                        return str(response.url)
                    else:
                        logger.error(f"获取视频真实链接失败: {response.status}")
                        return video_url
        except Exception as e:
            logger.error(f"获取视频真实链接时出错: {str(e)}")
            return video_url

    async def _parse_douyin(self, url: str) -> Dict[str, Any]:
        """调用抖音解析API"""
        try:
            api_url = "https://apih.kfcgw50.me/api/douyin"
            params = {
                'url': url,
                'type': 'json'
            }

            logger.debug(f"开始解析抖音链接: {url}")
            logger.debug(f"请求API: {api_url}, 参数: {params}")

            async with aiohttp.ClientSession() as session:  # 解析不使用代理
                async with session.get(api_url, params=params, timeout=30) as response:
                    if response.status != 200:
                        raise DouyinParserError(f"API请求失败，状态码: {response.status}")

                    data = await response.json()
                    logger.debug(f"原始API响应数据: {data}")

                    if data.get("code") == 200:
                        result = data.get("data", {})

                        # 获取真实视频链接
                        if result.get('video'):
                            # 使用代理访问视频链接获取真实URL
                            result['video'] = await self._get_real_video_url(result['video'])

                        result = self._clean_response_data(result)
                        logger.debug(f"清理后的数据: {result}")
                        return result
                    else:
                        raise DouyinParserError(data.get("message", "未知错误"))

        except aiohttp.ClientTimeout:
            logger.error(f"API请求超时: {api_url}")
            raise DouyinParserError("解析超时，请稍后重试")
        except aiohttp.ClientError as e:
            logger.error(f"API请求错误: {str(e)}")
            raise DouyinParserError(f"网络请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"解析过程发生错误: {str(e)}, URL: {url}")
            raise DouyinParserError(f"解析失败: {str(e)}")

    async def _send_test_card(self, bot: WechatAPIClient, chat_id: str, sender: str):
        """发送测试卡片消息"""
        try:
            # 测试数据
            test_data = {
                'video': 'https://v11-cold.douyinvod.com/c183ceff049f008265680819dbd8ac0a/67b206c0/video/tos/cn/tos-cn-ve-15/ok8JumeiqAI3pJ2nAiQE9rBiTfm1KtADABlBgV/?a=1128&ch=0&cr=0&dr=0&cd=0%7C0%7C0%7C0&cv=1&br=532&bt=532&cs=0&ds=3&ft=H4NIyvvBQx9Uf8ym8Z.6TQjSYE7OYMDtGkd~P4Aq8_45a&mime_type=video_mp4&qs=0&rc=ZzU5NTRnNDw1aGc5aDloZkBpanE4M3Y5cjNkeDMzNGkzM0AuLy1fLWFhXjQxNjFgYzRiYSNmXzZlMmRjcmdgLS1kLTBzcw%3D%3D&btag=80010e000ad000&cquery=100y&dy_q=1739716635&feature_id=aa7df520beeae8e397df15f38df0454c&l=20250216223715047FF68C05B9F67E1F19',
                'title': '测试视频标题',
                'name': '测试作者',
                'cover': 'https://is1-ssl.mzstatic.com/image/thumb/Purple221/v4/7c/49/e1/7c49e1af-ce92-d1c4-9a93-0a316e47ba94/AppIcon_TikTok-0-0-1x_U007epad-0-1-0-0-85-220.png/512x512bb.jpg'
            }

            logger.info("开始发送测试卡片")
            logger.debug(f"测试数据: {test_data}")

            # 发送测试卡片
            await bot.send_link_message(
                wxid=chat_id,
                url=test_data['video'],
                title=f"{test_data['title'][:30]} - {test_data['name'][:10]}",
                description="这是一个测试卡片消息",
                thumb_url=test_data['cover']
            )

            logger.info("测试卡片发送成功")

            # 发送详细信息
            debug_msg = (
                "🔍 测试卡片详情:\n"
                f"视频链接: {test_data['video']}\n"
                f"封面链接: {test_data['cover']}\n"
                f"标题: {test_data['title']} - {test_data['name']}"
            )
            await bot.send_text_message(
                wxid=chat_id,
                content=debug_msg,
                at=[sender]
            )

        except Exception as e:
            error_msg = f"测试卡片发送失败: {str(e)}"
            logger.error(error_msg)
            await bot.send_text_message(
                wxid=chat_id,
                content=error_msg,
                at=[sender]
            )

    @on_text_message
    async def handle_douyin_links(self, bot: WechatAPIClient, message: dict):
        content = message['Content']
        sender = message['SenderWxid']
        chat_id = message['FromWxid']

        # 添加测试命令识别
        if content.strip() == "测试卡片":
            await self._send_test_card(bot, chat_id, sender)
            return

        try:
            # 提取抖音链接
            match = self.url_pattern.search(content)
            if not match:
                return

            original_url = match.group(0)
            logger.info(f"发现抖音链接: {original_url}")

            # 解析视频信息
            video_info = await self._parse_douyin(original_url)

            if not video_info:
                raise DouyinParserError("无法获取视频信息")

            # 获取视频信息
            video_url = video_info.get('video', '')
            title = video_info.get('title', '无标题')
            author = video_info.get('name', '未知作者')
            cover = video_info.get('cover', '')

            if not video_url:
                raise DouyinParserError("无法获取视频地址")

            # 发送文字版消息
            text_msg = (
                f"🎬 解析成功\n"
                f"标题：{title}\n"
                f"作者：{author}\n"
                f"封面：{cover}\n"
                f"无水印链接：{video_url}"
            )
            await bot.send_text_message(
                wxid=chat_id,
                content=text_msg,
                at=[sender]
            )

            # 发送卡片版消息
            await bot.send_link_message(
                wxid=chat_id,
                url=video_url,
                title=f"{title[:30]} - {author[:10]}" if author else title[:40],
                description="点击观看无水印视频",
                thumb_url=cover
            )

            logger.info(f"已发送解析结果: 标题[{title}] 作者[{author}]")

        except (DouyinParserError, Exception) as e:
            error_msg = str(e) if str(e) else "未知错误"
            logger.error(f"抖音解析失败: {error_msg}")
            await bot.send_text_message(
                wxid=chat_id,
                content=f"视频解析失败: {error_msg}",
                at=[sender]
            )
