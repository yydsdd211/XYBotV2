import asyncio
import json
import os
import sys
import time
import tomllib
import traceback

from loguru import logger

import WechatAPI
from WechatAPI.errors import BanProtection
from database.database import BotDatabase
from utils.decorators import scheduler
from utils.plugin_manager import plugin_manager
from utils.xybot import XYBot


def is_api_message(record):
    return record["level"].name == "API"


@logger.catch
async def main():
    # 初始化路径和日志
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    logger.remove()

    logger.level("API", no=1, color="<cyan>")

    logger.add(
        "logs/XYBot_{time}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        encoding="utf-8",
        enqueue=True,
        retention="2 weeks",
        rotation="00:01",
        backtrace=True,
        diagnose=True,
        level="DEBUG",
    )
    logger.add(
        "logs/WechatAPI_{time}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        encoding="utf-8",
        enqueue=True,
        retention="2 weeks",
        rotation="00:01",
        filter=is_api_message,
        level="API",
    )
    logger.add(
        sys.stdout,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}",
        level="TRACE",
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )  # 日志设置

    # 读取主设置
    with open("main_config.toml", "rb") as f:
        main_config = tomllib.load(f)

    logger.success("读取主设置成功")

    # 启动WechatAPI服务
    server = WechatAPI.WechatAPIServer()

    api_config = main_config.get("WechatAPIServer", {})

    server.start(port=api_config.get("port", 9000),
                 mode=api_config.get("mode", "release"),
                 redis_host=api_config.get("redis-host", "127.0.0.1"),
                 redis_port=api_config.get("redis-port", 6379),
                 redis_password=api_config.get("redis-password", ""),
                 redis_db=api_config.get("redis-db", 0))

    # 实例化WechatAPI客户端
    bot = WechatAPI.WechatAPIClient("127.0.0.1", api_config.get("port", 9000))
    bot.ignore_protect = main_config.get("XYBot", {}).get("ignore-protection", False)

    # 等待WechatAPI服务启动
    time_out = 10
    while not await bot.is_running() and time_out > 0:
        logger.info("等待WechatAPI启动中")
        await asyncio.sleep(2)
        time_out -= 2

    if time_out <= 0:
        logger.error("WechatAPI服务启动超时")
        return

    if not await bot.check_database():
        logger.error("Redis或Dragonfly连接失败，请检查Redis或Dragonfly是否在运行中，Redis或Dragonfly的配置")
        return

    logger.success("WechatAPI服务已启动")

    # ==========登陆==========

    # 检查并创建robot_stat.json文件
    robot_stat_path = "resource/robot_stat.json"
    if not os.path.exists(robot_stat_path):
        default_config = {
            "wxid": "",
            "device_name": "",
            "device_id": ""
        }
        os.makedirs(os.path.dirname(robot_stat_path), exist_ok=True)
        with open(robot_stat_path, "w") as f:
            json.dump(default_config, f)
        robot_stat = default_config
    else:
        with open(robot_stat_path, "r") as f:
            robot_stat = json.load(f)

    wxid = robot_stat.get("wxid", None)
    device_name = robot_stat.get("device_name", None)
    device_id = robot_stat.get("device_id", None)

    if not await bot.is_logged_in(wxid):
        # 需要登录
        try:
            if await bot.get_cached_info(wxid):
                # 尝试唤醒登录
                uuid = await bot.awaken_login(wxid)
                logger.success("获取到登录uuid: {}", uuid)
            else:
                # 二维码登录
                if not device_name:
                    device_name = bot.create_device_name()
                if not device_id:
                    device_id = bot.create_device_id()
                uuid, url = await bot.get_qr_code(device_id=device_id, device_name=device_name, print_qr=True)
                logger.success("获取到登录uuid: {}", uuid)
                logger.success("获取到登录二维码: {}", url)
        except:
            # 二维码登录
            if not device_name:
                device_name = bot.create_device_name()
            if not device_id:
                device_id = bot.create_device_id()
            uuid, url = await bot.get_qr_code(device_id=device_id, device_name=device_name, print_qr=True)
            logger.success("获取到登录uuid: {}", uuid)
            logger.success("获取到登录二维码: {}", url)

        while True:
            stat, data = await bot.check_login_uuid(uuid, device_id=device_id)
            if stat:
                break
            logger.info("等待登录中，过期倒计时：{}", data)
            await asyncio.sleep(5)

        # 保存登录信息
        robot_stat["wxid"] = bot.wxid
        robot_stat["device_name"] = device_name
        robot_stat["device_id"] = device_id
        with open("resource/robot_stat.json", "w") as f:
            json.dump(robot_stat, f)

        # 获取登录账号信息
        bot.wxid = data.get("acctSectResp").get("userName")
        bot.nickname = data.get("acctSectResp").get("nickName")
        bot.alias = data.get("acctSectResp").get("alias")
        bot.phone = data.get("acctSectResp").get("bindMobile")

        logger.info("登录账号信息: wxid: {}  昵称: {}  微信号: {}  手机号: {}", bot.wxid, bot.nickname, bot.alias,
                    bot.phone)

    else:  # 已登录
        bot.wxid = wxid
        profile = await bot.get_profile()

        bot.nickname = profile.get("NickName").get("string")
        bot.alias = profile.get("Alias")
        bot.phone = profile.get("BindMobile").get("string")

        logger.info("登录账号信息: wxid: {}  昵称: {}  微信号: {}  手机号: {}", bot.wxid, bot.nickname, bot.alias,
                    bot.phone)

    logger.info("登录设备信息: device_name: {}  device_id: {}", device_name, device_id)

    logger.success("登录成功")

    # ========== 登录完毕 开始初始化 ========== #

    # 开启自动心跳
    success = await bot.start_auto_heartbeat()
    if success:
        logger.success("已开启自动心跳")
    else:
        logger.error("开启自动心跳失败")

    # 初始化机器人
    xybot = XYBot(bot)
    xybot.update_profile(bot.wxid, bot.nickname, bot.alias, bot.phone)

    # 初始化数据库
    BotDatabase()

    # 启动调度器
    scheduler.start()
    logger.success("定时任务已启动")

    # 加载插件目录下的所有插件
    loaded_plugins = await plugin_manager.load_plugins_from_directory(bot, load_disabled_plugin=False)
    logger.success(f"已加载插件: {loaded_plugins}")

    # ========== 开始接受消息 ========== #

    # 开启自动消息接收
    ws_port = await bot.start_websocket()
    ws = await bot.connect_websocket(ws_port)
    logger.success("已连接到WechatAPI WebSocket，开始接受消息")

    # 先接受10秒的消息，之前的消息有堆积
    logger.info("处理堆积消息中")
    now = time.time()
    while time.time() - now < 10:
        data = await bot.sync_message()
        data = data.get("AddMsgs")
        if not data:
            break
        logger.debug("接受到 {} 条消息", len(data))
        await asyncio.sleep(1)
    logger.success("处理堆积消息完毕")

    # 开始接受消息
    logger.success("开始处理消息")
    while True:
        recv = await ws.recv()
        msg_list = json.loads(recv).get("Data")

        for msg in msg_list:
            try:
                asyncio.create_task(xybot.process_message(msg))  # 为了同时处理多个消息，不等待协程运行完毕
            except BanProtection:
                logger.warning("登录新设备后4小时内请不要操作以避免风控")
            except:
                logger.error(traceback.format_exc())


if __name__ == "__main__":
    # 防止低版本Python运行
    if sys.version_info.major != 3 and sys.version_info.minor != 11:
        print("请使用Python3.11")
        sys.exit(1)
    print(
        "░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓███████▓▒░ ░▒▓██████▓▒░▒▓████████▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓███████▓▒░  \n"
        "░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░          ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ \n"
        "░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░           ░▒▓█▓▒▒▓█▓▒░       ░▒▓█▓▒░ \n"
        " ░▒▓██████▓▒░ ░▒▓██████▓▒░░▒▓███████▓▒░░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░           ░▒▓█▓▒▒▓█▓▒░ ░▒▓██████▓▒░  \n"
        "░▒▓█▓▒░░▒▓█▓▒░  ░▒▓█▓▒░   ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░            ░▒▓█▓▓█▓▒░ ░▒▓█▓▒░        \n"
        "░▒▓█▓▒░░▒▓█▓▒░  ░▒▓█▓▒░   ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░            ░▒▓█▓▓█▓▒░ ░▒▓█▓▒░        \n"
        "░▒▓█▓▒░░▒▓█▓▒░  ░▒▓█▓▒░   ░▒▓███████▓▒░ ░▒▓██████▓▒░  ░▒▓█▓▒░             ░▒▓██▓▒░  ░▒▓████████▓▒░\n")

    asyncio.run(main())
