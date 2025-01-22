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
        main_config = main_config["XYBot"]

        self.enable = config["enable"]
        self.command = config["command"]
        self.model = config["model"]
        self.temperature = config["temperature"]
        self.max_history_messages = config["max_history_messages"]
        self.context_window = config["context_window"]

        self.api_key = openai_config["api-key"]
        self.url_base = openai_config["url-base"]

        self.admins = main_config["admins"]
        self.database_url = main_config["database-url"]

        self.llm = ChatOpenAI(
            api_key=self.api_key,
            base_url=self.url_base,
            model=self.model,
            temperature=self.temperature
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
        response = await self.llm.ainvoke(state["messages"])
        return {"messages": response}

    @on_text_message
    async def handle_text(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return

        content = str(message["Content"]).strip()
        command = content.split(" ")

        if not len(command) or command[0] not in self.command and message["IsGroup"]:
            return

        message["Content"] = content[len(command[0]):].strip()

        await self.chatgpt(bot, message)
        return

    @on_at_message
    async def handle_at(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return

        message["Content"] = str(message["Content"]).replace(f"@{bot.nickname}\u2005", "").strip()
        await self.chatgpt(bot, message)

    @on_voice_message
    async def handle_voice(self, bot: WechatAPIClient, message: dict):
        logger.info("收到了语音消息")

    @on_image_message
    async def handle_image(self, bot: WechatAPIClient, message: dict):
        logger.info("收到了图片消息")

    async def chatgpt(self, bot: WechatAPIClient, message: dict):
        from_wxid = message["FromWxid"]
        sender_wxid = message["SenderWxid"]
        user_input = message["Content"]

        if not user_input:
            await bot.send_text_message(sender_wxid, "-----XYBot-----\n请输入要询问的内容")
            return

        try:
            thread_id = self.db.get_llm_thread_id(sender_wxid)

            if not thread_id:
                thread_id = str(uuid4())

            configurable = {"configurable": {"thread_id": thread_id}}

            self.db.save_llm_thread_id(sender_wxid, thread_id)

            input_message = [HumanMessage(user_input)]
            output_message = await self.app.ainvoke({"messages": input_message}, configurable)
            output_message = f"\n{output_message['messages'][-1].content}"

            await bot.send_at_message(
                from_wxid,
                output_message,
                [sender_wxid]
            )

        except Exception as e:
            logger.error(f"AI回复出错: {str(e)}")
            await bot.send_text_message(
                from_wxid,
                f"-----XYBot-----\n❌请求失败：{str(e)}"
            )
            logger.error(traceback.format_exc())
