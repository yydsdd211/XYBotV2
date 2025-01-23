import tomllib
import traceback
from uuid import uuid4

import aiosqlite
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import START, MessagesState, StateGraph
from loguru import logger

from WechatAPI import WechatAPIClient
from database import BotDatabase
from utils.decorators import *
from utils.plugin_base import PluginBase


class ChatGPT(PluginBase):
    description = "ChatGPT插件"
    author = "HenryXiaoYang"
    version = "1.0.0"

    def __init__(self):
        super().__init__()

        with open("plugins/all_in_one_config.toml", "rb") as f:
            plugin_config = tomllib.load(f)

        with open("main_config.toml", "rb") as f:
            main_config = tomllib.load(f)

        config = plugin_config["ChatGPT"]
        openai_config = main_config["OpenAI"]

        # get all the command from other plugin
        self.other_command = []
        for plugin in plugin_config:
            if plugin != "ChatGPT":
                self.other_command.extend(plugin_config[plugin].get("command", []))
        self.other_command.extend(
            ["加积分", "减积分", "设置积分", "添加白名单", "移除白名单", "白名单列表", "天气", "五子棋", "五子棋创建",
             "五子棋邀请", "邀请五子棋", "接受", "加入", "下棋", "加载插件", "加载所有插件", "卸载插件", "卸载所有插件",
             "重载插件", "重载所有插件", "插件列表"])

        main_config = main_config["XYBot"]

        self.enable = config["enable"]
        self.command = config["command"]
        self.model = config["model"]
        self.temperature = config["temperature"]
        self.voice_model = config["voice-model"]
        self.max_history_messages = config["max_history_messages"]
        self.context_window = config["context_window"]
        self.system_prompt = config["system_prompt"]

        self.api_key = openai_config["api-key"]
        self.url_base = openai_config["url-base"]

        self.admins = main_config["admins"]
        self.database_url = main_config["database-url"]

        # 创建统一的 LLM 实例，支持文本和音频
        self.llm = ChatOpenAI(
            api_key=self.api_key,
            base_url=self.url_base,
            model=self.model,
            temperature=self.temperature,
            model_kwargs={
                "modalities": ["text", "audio"],
                "audio": {"voice": self.voice_model, "format": "wav"},
            }
        )

        workflow = StateGraph(state_schema=MessagesState)
        workflow.add_edge(START, "model")
        workflow.add_node("model", self.call_model)

        db_path = self.database_url.replace('sqlite:///', '')

        self.sqlite_conn = aiosqlite.connect(db_path)
        self.sqlite_saver = AsyncSqliteSaver(self.sqlite_conn)
        self.app = workflow.compile(checkpointer=self.sqlite_saver)

        self.db = BotDatabase()

    def __del__(self):
        """确保资源被正确释放"""
        try:
            if hasattr(self, 'sqlite_conn'):
                self.sqlite_conn.close()
        except Exception as e:
            logger.error(f"关闭数据库连接时出错: {str(e)}")

    async def call_model(self, state: MessagesState):
        """处理所有类型的消息"""
        messages = state["messages"]
        try:
            response = await self.llm.ainvoke(messages)
            return {"messages": response}
        except Exception as e:
            logger.error(f"模型调用出错: {str(e)}")
            raise

    @on_text_message
    async def handle_text(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return

        content = str(message["Content"]).strip()
        command = content.split(" ")

        if command[0] not in self.command and message["IsGroup"]:
            return
        elif command[0] in self.other_command:
            return

        if message["IsGroup"]:
            message["Content"] = content[len(command[0]):].strip()

        output_message = "\n" + await self.chatgpt(bot, message)

        await bot.send_at_message(
            message["FromWxid"],
            output_message,
            [message["SenderWxid"]]
        )

    @on_at_message
    async def handle_at(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return

        message["Content"] = str(message["Content"]).replace(f"@{bot.nickname}\u2005", "").strip()

        output_message = "\n" + await self.chatgpt(bot, message)

        await bot.send_at_message(
            message["FromWxid"],
            output_message,
            [message["SenderWxid"]]
        )


    @on_voice_message
    async def handle_voice(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return

        if message["IsGroup"]:
            return

        output_base64 = await self.chatgpt(bot, message)
        await bot.send_voice_message(message["FromWxid"], voice_base64=output_base64, format="wav")

    @on_image_message
    async def handle_image(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return

        if message["IsGroup"]:
            return

        await bot.send_text_message(
            message["FromWxid"],
            "抱歉，当前模型不支持图片处理功能。"
        )

    async def chatgpt(self, bot: WechatAPIClient, message: dict):
        from_wxid = message["FromWxid"]
        sender_wxid = message["SenderWxid"]
        user_input = message["Content"]
        is_voice = isinstance(message["Content"], bytes)

        if not user_input:
            await bot.send_text_message(sender_wxid, "-----XYBot-----\n请输入要询问的内容")
            return

        try:
            thread_id = self.db.get_llm_thread_id(sender_wxid)

            if not thread_id:
                thread_id = str(uuid4())
                self.db.save_llm_thread_id(sender_wxid, thread_id)

            configurable = {
                "configurable": {
                    "thread_id": thread_id,
                    "max_messages": self.max_history_messages,
                    "context_window": self.context_window
                }
            }

            if is_voice:
                # 语音输入
                wav_base64 = bot.byte_to_base64(user_input)
                input_message = [
                    HumanMessage(content=self.system_prompt),
                    HumanMessage(content=[
                        {"type": "input_audio", "input_audio": {"data": wav_base64, "format": "wav"}},
                    ])
                ]
            else:
                # 文本输入
                input_message = [
                    HumanMessage(content=self.system_prompt),
                    HumanMessage(content=user_input)
                ]

            # 使用 app 处理消息以保持上下文
            output = await self.app.ainvoke({"messages": input_message}, configurable)
            last_message = output["messages"][-1]

            # 根据消息类型返回相应的内容
            if is_voice and 'audio' in last_message.additional_kwargs:
                return last_message.additional_kwargs['audio']['data']
            else:
                return last_message.additional_kwargs['audio']['transcript']

        except Exception as e:
            logger.error(f"AI回复出错: {str(e)}")
            await bot.send_text_message(
                from_wxid,
                f"-----XYBot-----\n❌请求失败：{str(e)}"
            )
            logger.error(traceback.format_exc())

