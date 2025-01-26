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


class Ai(PluginBase):
    description = "AI插件"
    author = "HenryXiaoYang"
    version = "1.0.0"

    def __init__(self):
        super().__init__()

        with open("plugins/all_in_one_config.toml", "rb") as f:
            plugin_config = tomllib.load(f)

        with open("main_config.toml", "rb") as f:
            main_config = tomllib.load(f)

        config = plugin_config["Ai"]
        openai_config = main_config["OpenAI"]

        # get all the command from other plugin
        self.other_command = []
        for plugin in plugin_config:
            if plugin != "Ai":
                self.other_command.extend(plugin_config[plugin].get("command", []))
        self.other_command.extend(
            ["加积分", "减积分", "设置积分", "添加白名单", "移除白名单", "白名单列表", "天气", "五子棋", "五子棋创建",
             "五子棋邀请", "邀请五子棋", "接受", "加入", "下棋", "加载插件", "加载所有插件", "卸载插件", "卸载所有插件",
             "重载插件", "重载所有插件", "插件列表"])

        main_config = main_config["XYBot"]

        self.enable = config["enable"]
        self.enable_command = config["enable-command"]
        self.enable_at = config["enable-at"]
        self.enable_private = config["enable-private"]

        self.command = config["command"]

        self.base_url = config["base-url"] if config["base-url"] else openai_config["base-url"]
        self.api_key = config["api-key"] if config["api-key"] else openai_config["api-key"]

        self.model_name = config["model-name"]

        self.text_input = config["text-input"]
        self.image_input = config["image-input"]
        self.voice_input = config["voice-input"]

        self.text_output = config["text-output"]
        self.image_output = config["image-output"]
        self.voice_output = config["voice-output"]

        self.temperature = config["temperature"]
        self.max_history_messages = config["max-history-messages"]
        self.model_kwargs = config["model_kwargs"]

        self.prompt = config["prompt"]

        self.admins = main_config["admins"]
        self.database_url = main_config["database-url"]

        modalities = []
        if self.text_output:
            modalities.append("text")
        if self.image_output:
            modalities.append("image")
        if self.voice_output:
            modalities.append("audio")
            if not self.model_kwargs.get("audio", None):
                self.model_kwargs["audio"] = {}
            self.model_kwargs["audio"]["format"] = "wav"

        self.model_kwargs["modalities"] = modalities

        self.llm = ChatOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model_name,
            temperature=self.temperature,
            model_kwargs=self.model_kwargs
        )

        self.db = BotDatabase()

        self.sqlite_conn = None
        self.sqlite_saver = None
        self.ai = None

        self.inited = False

    async def async_init(self):
        if not self.inited:
            db_path = self.database_url.replace('sqlite:///', '')
            self.sqlite_conn = await aiosqlite.connect(db_path)
            self.sqlite_saver = AsyncSqliteSaver(self.sqlite_conn)

            workflow = StateGraph(state_schema=MessagesState)
            workflow.add_edge(START, "model")
            workflow.add_node("model", self.call_model)

            self.ai = workflow.compile(checkpointer=self.sqlite_saver)

            self.inited = True

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

        if not self.text_input:
            return

        await self.async_init()

        content = str(message["Content"]).strip()
        command = content.split(" ")

        is_command = command[0] in self.command and self.enable_command
        is_private = not message["IsGroup"] and self.enable_private
        if not is_command and not is_private:
            return
        elif command[0] in self.other_command:
            return

        if message["IsGroup"]:
            message["Content"] = content[len(command[0]):].strip()

        if "清除历史记录" in message["Content"] or "清除记录" in message["Content"]:
            return await self.delete_user_thread_id(bot, message)
        elif "清除所有人历史记录" in message["Content"] or "清除所有历史记录" in message["Content"] or "清除所有记录" in \
                message["Content"]:
            if message["SenderWxid"] not in self.admins:
                await bot.send_at_message(
                    message["FromWxid"],
                    f"\n-----XYBot-----\n😠你没有这样做的权限！",
                    [message["SenderWxid"]]
                )
                return

            result = await self.delete_all_user_thread_id()
            if result:
                await bot.send_at_message(
                    message["FromWxid"],
                    f"\n-----XYBot-----\n🗑️清除成功✅",
                    [message["SenderWxid"]]
                )
            else:
                await bot.send_at_message(
                    message["FromWxid"],
                    f"\n-----XYBot-----\n清除失败，请查看日志",
                    [message["SenderWxid"]]
                )

        result = await self.get_ai_response(bot, message)
        if not result:
            logger.warning("AI插件有问题")
            return
        output_message = "\n" + await self.get_ai_response(bot, message)

        await bot.send_at_message(
            message["FromWxid"],
            output_message,
            [message["SenderWxid"]]
        )

    @on_at_message
    async def handle_at(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return

        if not self.text_input:
            return

        await self.async_init()

        message["Content"] = str(message["Content"]).replace(f"@{bot.nickname}\u2005", "").strip()

        result = await self.get_ai_response(bot, message)

        if not result:
            logger.warning("AI插件有问题")
            return

        output_message = "\n" + await self.get_ai_response(bot, message)

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

        if not self.voice_input:
            return

        await self.async_init()

        result = await self.get_ai_response(bot, message)
        if not result:
            logger.warning("AI插件有问题")
            return

        output_base64 = await self.get_ai_response(bot, message)
        await bot.send_voice_message(message["FromWxid"], voice_base64=output_base64, format="wav")

    @on_image_message
    async def handle_image(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return

        if message["IsGroup"]:
            return

        if not self.image_input:
            return

        await self.async_init()

        result = await self.get_ai_response(bot, message)
        if not result:
            logger.warning("AI插件有问题")
            return
        output_message = "\n" + await self.get_ai_response(bot, message)

        await bot.send_at_message(
            message["FromWxid"],
            output_message,
            [message["SenderWxid"]]
        )

    @schedule('cron', hour=5)
    async def reset_chat_history(self, bot: WechatAPIClient):
        await self.async_init()

        r = await self.delete_all_user_thread_id()
        if r:
            logger.success("数据库：清除AI上下文成功")
        else:
            logger.error("数据库：清除AI上下文失败")

    async def get_ai_response(self, bot: WechatAPIClient, message: dict):
        from_wxid = message["FromWxid"]
        sender_wxid = message["SenderWxid"]
        user_input = message["Content"]

        if not user_input:
            await bot.send_at_message(from_wxid, "\n-----XYBot-----\n你还没输入呀！🤔", [sender_wxid])
            return

        try:
            # 上下文
            thread_id = self.db.get_llm_thread_id(sender_wxid, self.model_name)
            if not thread_id:
                thread_id = str(uuid4())
                self.db.save_llm_thread_id(sender_wxid, thread_id, self.model_name)
            configurable = {
                "configurable": {
                    "thread_id": thread_id,
                    "max_messages": self.max_history_messages,
                }
            }

            # 消息类型
            if message["MsgType"] == 1 and self.text_input:  # 文本输入
                input_message = [
                    HumanMessage(content=self.prompt),
                    HumanMessage(content=user_input)
                ]
            elif message["MsgType"] == 3 and self.image_input:  # 图片输入
                image_base64 = user_input
                input_message = [
                    HumanMessage(content=self.prompt),
                    HumanMessage(content=[
                        {"type": "image_url", "image_url": {"url": f"data:image;base64,{image_base64}"}},
                    ])
                ]
            elif message["MsgType"] == 34 and self.voice_input:  # 语音输入
                wav_base64 = bot.byte_to_base64(user_input)
                input_message = [
                    HumanMessage(content=self.prompt),
                    HumanMessage(content=[
                        {"type": "input_audio", "input_audio": {"data": wav_base64, "format": "wav"}},
                    ])
                ]
            else:
                raise ValueError("未知的输入格式！")

            # 请求API
            logger.debug("请求AI的API, thread id: {}", thread_id)
            output = await self.ai.ainvoke({"messages": input_message}, configurable)
            last_message = output["messages"][-1]

            # 什么类型输入，什么类型输出
            if message["MsgType"] == 1 and self.text_output:
                if "audio" in last_message.additional_kwargs:
                    return last_message.additional_kwargs['audio']['transcript']
                return last_message.content

            elif message["MsgType"] == 3 and self.image_output:
                return last_message.content

            elif message["MsgType"] == 34 and self.voice_output:
                if "audio" in last_message.additional_kwargs:
                    return last_message.additional_kwargs['audio']['data']
                return last_message.content

            else:  # fallback
                return last_message.content

        except Exception as e:
            await bot.send_at_message(
                from_wxid,
                f"-----XYBot-----\n❌请求失败：{str(e)}",
                [sender_wxid]
            )
            logger.error(traceback.format_exc())

    async def delete_user_thread_id(self, bot: WechatAPIClient, message: dict):
        thread_id_dict = dict(self.db.get_llm_thread_id(message["SenderWxid"]))
        cursor = await self.sqlite_conn.cursor()
        try:
            for value in thread_id_dict.values():
                cursor.execute("DELETE FROM checkpoints WHERE thread_id = ?", (value,))
                cursor.execute("DELETE FROM writes WHERE thread_id = ?", (value,))
            await self.sqlite_conn.commit()
        except Exception as e:
            await bot.send_at_message(
                message["FromWxid"],
                f"-----XYBot-----\n❌删除失败：{str(e)}",
                [message["SenderWxid"]]
            )
            logger.error(traceback.format_exc())
            return
        finally:
            cursor.close()

        self.db.save_llm_thread_id(message["SenderWxid"], "", self.model_name)
        await bot.send_at_message(
            message["FromWxid"],
            f"\n-----XYBot-----\n🗑️清除成功✅",
            [message["SenderWxid"]]
        )
        return

    async def delete_all_user_thread_id(self) -> bool:
        self.db.delete_all_llm_thread_id()

        cursor = await self.sqlite_conn.cursor()
        try:
            await cursor.execute("DELETE FROM checkpoints")
            await cursor.execute("DELETE FROM writes")
            await cursor.execute("VACUUM")
            await self.sqlite_conn.commit()
        except Exception as e:
            logger.error(traceback.format_exc())
            return False
        finally:
            cursor.close()

        return True
