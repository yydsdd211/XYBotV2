import tomllib
from datetime import datetime
from random import randint

import pytz

from WechatAPI import WechatAPIClient
from database import BotDatabase
from utils.decorators import *
from utils.plugin_base import PluginBase


class SignIn(PluginBase):
    description = "每日签到"
    author = "HenryXiaoYang"
    version = "1.0.0"

    def __init__(self):
        super().__init__()

        with open("plugins/all_in_one_config.toml", "rb") as f:
            plugin_config = tomllib.load(f)

        with open("main_config.toml", "rb") as f:
            main_config = tomllib.load(f)

        config = plugin_config["SignIn"]
        main_config = main_config["XYBot"]

        self.enable = config["enable"]
        self.command = config["command"]
        self.min_points = config["min-point"]
        self.max_points = config["max-point"]
        self.streak_cycle = config["streak-cycle"]
        self.max_streak_point = config["max-streak-point"]

        self.timezone = main_config["timezone"]

        self.db = BotDatabase()

    @on_text_message
    async def handle_text(self, bot: WechatAPIClient, message: dict):
        if not self.enable:
            return

        content = str(message["Content"]).strip()
        command = content.split(" ")

        if not len(command) or command[0] not in self.command:
            return

        sign_wxid = message["SenderWxid"]

        last_sign = self.db.get_signin_stat(sign_wxid)
        now = datetime.now(tz=pytz.timezone(self.timezone)).replace(hour=0, minute=0, second=0, microsecond=0)

        # 确保 last_sign 用了时区
        if last_sign and last_sign.tzinfo is None:
            last_sign = pytz.timezone(self.timezone).localize(last_sign)
        last_sign = last_sign.replace(hour=0, minute=0, second=0, microsecond=0)

        if last_sign and (now - last_sign).days < 1:
            output = "\n-----XYBot-----\n你今天已经签到过了！😠"
            await bot.send_at_message(message["FromWxid"], output, [sign_wxid])
            return

        self.db.set_signin_stat(sign_wxid, now)

        signin_points = randint(self.min_points, self.max_points)  # 随机积分

        streak = self.db.get_signin_streak(sign_wxid) + 1  # 获取连续签到天数
        self.db.set_signin_streak(sign_wxid, streak)  # 设置连续签到天数
        streak_points = min(streak // self.streak_cycle, self.max_streak_point)  # 计算连续签到奖励

        self.db.add_points(sign_wxid, signin_points + streak_points)  # 增加积分

        output = ("\n"
                  f"-----XYBot-----\n"
                  f"签到成功！你领到了 {signin_points} 个积分！✅\n")

        if streak > 1:
            output += f"你连续签到了 {streak} 天！"

        if streak_points > 0:
            output += f" 奖励 {streak_points} 积分！"

        if streak > 1:
            output += "[爱心]"

        await bot.send_at_message(message["FromWxid"], output, [sign_wxid])
