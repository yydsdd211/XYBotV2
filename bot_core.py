import asyncio
import json
import os
import time
import tomllib
import traceback
from pathlib import Path

import websockets
from loguru import logger

import WechatAPI
from WechatAPI.errors import BanProtection
from database.database import BotDatabase
from utils.decorators import scheduler
from utils.plugin_manager import plugin_manager
from utils.xybot import XYBot


async def handle_message(xybot, msg):
    """处理单条消息"""
    try:
        await xybot.process_message(msg)
    except BanProtection:
        logger.warning("登录新设备后4小时内请不要操作以避免风控")
    except Exception:
        logger.error(traceback.format_exc())


async def process_websocket_messages(ws, xybot):
    """处理WebSocket接收到的消息"""
    try:
        # 增加接收超时时间
        recv = await asyncio.wait_for(
            ws.recv(),
            timeout=90  # 增加到90秒
        )

        try:
            message = json.loads(recv)
            msg_list = message.get("Data", [])

            if not msg_list:
                return

            for msg in msg_list:
                asyncio.create_task(handle_message(xybot, msg))

        except json.JSONDecodeError as e:
            logger.error(f"JSON解析错误: {e}, 原始消息: {recv}")
            return

    except asyncio.TimeoutError:
        logger.debug("接收消息超时，发送心跳包...")
        try:
            await asyncio.wait_for(ws.ping(), timeout=5)  # 减少到5秒
            # logger.debug("心跳包发送成功")
        except Exception as e:
            logger.error(f"心跳包发送失败: {e}")
            raise  # 重新抛出异常以触发重连
        return

    except websockets.exceptions.ConnectionClosed as e:
        logger.warning(f"WebSocket连接已断开 (code: {e.code}, reason: {e.reason})")
        raise
        
    except Exception as e:
        logger.error(f"处理消息时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise  # 重新抛出异常以触发重连


async def websocket_client_loop(bot, ws_port, xybot):
    """WebSocket客户端主循环"""
    while True:
        try:
            # 建立WebSocket连接
            ws = await bot.connect_websocket(ws_port)
            logger.success("已连接到WechatAPI WebSocket，开始接受消息")

            # 设置pong处理器
            ws.pong_handler = lambda _: logger.debug("收到服务器pong响应")
            
            # 启动心跳任务
            ping_task = asyncio.create_task(keep_alive(ws))

            try:
                # 消息处理循环
                while True:
                    if ws.state != websockets.protocol.State.OPEN:
                        logger.warning("WebSocket连接已断开，准备重连...")
                        break
                    await process_websocket_messages(ws, xybot)
            finally:
                ping_task.cancel()
                if ws.state == websockets.protocol.State.OPEN:
                    try:
                        await ws.close()
                    except:
                        pass

        except Exception as e:
            logger.error(f"WebSocket连接发生错误: {str(e)}")
            await asyncio.sleep(5)  # 固定5秒后重连
            logger.info("尝试重新连接WebSocket...")


async def keep_alive(websocket):
    """保持WebSocket连接的心跳函数"""
    try:
        while True:
            await asyncio.sleep(30)  # 每30秒发送一次ping
            try:
                # 减少ping超时时间
                await asyncio.wait_for(
                    websocket.ping(),
                    timeout=5  # 减少到5秒
                )
                logger.debug("心跳包发送成功")
            except asyncio.TimeoutError:
                logger.warning("心跳包发送超时")
                break
            except Exception as e:
                logger.warning(f"心跳包发送失败: {str(e)}")
                break
    except asyncio.CancelledError:
        pass

async def bot_core():
    # 设置工作目录
    script_dir = Path(__file__).resolve().parent

    # 读取主设置
    config_path = script_dir / "main_config.toml"
    with open(config_path, "rb") as f:
        main_config = tomllib.load(f)

    logger.success("读取主设置成功")

    # 启动WechatAPI服务
    server = WechatAPI.WechatAPIServer()

    api_config = main_config.get("WechatAPIServer", {})

    redis_host = os.getenv("REDIS_HOST", api_config.get("redis-host"))

    logger.debug("最终使用的 Redis 主机地址: {}", redis_host)

    server.start(port=api_config.get("port", 9000),
                 mode=api_config.get("mode", "release"),
                 redis_host=redis_host,
                 redis_port=api_config.get("redis-port", 6379),
                 redis_password=api_config.get("redis-password", ""),
                 redis_db=api_config.get("redis-db", 0))

    # 实例化WechatAPI客户端
    bot = WechatAPI.WechatAPIClient("localhost", api_config.get("port", 9000))
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
    robot_stat_path = script_dir / "resource" / "robot_stat.json"
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
        while not await bot.is_logged_in(wxid):
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

    # 开启自动消息接收
    ws_port = await bot.start_websocket()
    await asyncio.sleep(0.5)

    # 启动WebSocket客户端
    await websocket_client_loop(bot, ws_port, xybot)
