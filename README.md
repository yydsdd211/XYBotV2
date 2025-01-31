# XYBot V2

XYBot V2 是一个功能丰富的微信机器人框架,支持多种互动功能和游戏玩法。

## 主要功能

### 基础功能

- 🤖 AI聊天 - 支持文字、图片、语音等多模态交互
- 📰 每日新闻 - 自动推送每日新闻
- 🎵 点歌系统 - 支持在线点歌
- 🌤️ 天气查询 - 查询全国各地天气
- 🎮 游戏功能 - 五子棋、战争雷霆玩家查询等

### 积分系统

- 📝 每日签到 - 支持连续签到奖励
- 🎲 抽奖系统 - 多种抽奖玩法
- 🧧 红包系统 - 群内发积分红包
- 💰 积分交易 - 用户间积分转账
- 📊 积分排行 - 查看积分排名

### 管理功能

- ⚙️ 插件管理 - 动态加载/卸载插件
- 👥 白名单管理 - 控制机器人使用权限
- 📊 积分管理 - 管理员可调整用户积分
- 🔄 签到重置 - 重置所有用户签到状态

## 插件系统

XYBot V2 采用插件化设计,所有功能都以插件形式实现。主要插件包括:

- AdminPoint - 积分管理
- AdminSignInReset - 签到重置
- AdminWhitelist - 白名单管理
- Ai - AI聊天
- BotStatus - 机器人状态
- GetContact - 获取通讯录
- GetWeather - 天气查询
- Gomoku - 五子棋游戏
- GoodMorning - 早安问候
- Leaderboard - 积分排行
- LuckyDraw - 幸运抽奖
- Menu - 菜单系统
- Music - 点歌系统
- News - 新闻推送
- PointTrade - 积分交易
- QueryPoint - 积分查询
- RandomMember - 随机群成员
- RandomPicture - 随机图片
- RedPacket - 红包系统
- SignIn - 每日签到
- Warthunder - 战争雷霆查询

## 开发说明

### 插件开发

所有插件需继承 `PluginBase` 类,实现相应的处理方法。示例:

```python
from loguru import logger

from WechatAPI import WechatAPIClient
from utils.decorators import *
from utils.plugin_base import PluginBase


class ExamplePlugin(PluginBase):
    description = "示例插件"
    author = "HenryXiaoYang"
    version = "1.0.0"

    def __init__(self):
        super().__init__()

    @on_text_message
    async def handle_text(self, bot: WechatAPIClient, message: dict):
        logger.info("收到了文本消息")

    @on_at_message
    async def handle_at(self, bot: WechatAPIClient, message: dict):
        logger.info("收到了被@消息")

    @on_voice_message
    async def handle_voice(self, bot: WechatAPIClient, message: dict):
        logger.info("收到了语音消息")

    @on_image_message
    async def handle_image(self, bot: WechatAPIClient, message: dict):
        logger.info("收到了图片消息")

    @on_video_message
    async def handle_video(self, bot: WechatAPIClient, message: dict):
        logger.info("收到了视频消息")

    @on_file_message
    async def handle_file(self, bot: WechatAPIClient, message: dict):
        logger.info("收到了文件消息")

    @on_quote_message
    async def handle_quote(self, bot: WechatAPIClient, message: dict):
        logger.info("收到了引用消息")

    @on_pat_message
    async def handle_pat(self, bot: WechatAPIClient, message: dict):
        logger.info("收到了拍一拍消息")

    @on_emoji_message
    async def handle_emoji(self, bot: WechatAPIClient, message: dict):
        logger.info("收到了表情消息")

    @schedule('interval', seconds=5)
    async def periodic_task(self, bot: WechatAPIClient):
        logger.info("我每5秒执行一次")

    @schedule('cron', hour=8, minute=30, second=30)
    async def daily_task(self, bot: WechatAPIClient):
        logger.info("我每天早上8点30分30秒执行")

    @schedule('date', run_date='2025-01-29 00:00:00')
    async def new_year_task(self, bot: WechatAPIClient):
        logger.info("我在2025年1月29日执行")
```

## 部署说明

### Docker 部署（推荐）

1. 准备环境

需要安装 Docker 和 Docker Compose:

- Docker 安装: https://docs.docker.com/get-started/get-docker/
- Docker Compose 安装: https://docs.docker.com/compose/install/

2. 拉取最新镜像

```bash
# 克隆项目
git clone https://github.com/HenryXiaoYang/XYBotV2.git
cd XYBotV2

# 拉取镜像
docker-compose pull
```

3. 启动容器

```bash
# 首次启动
docker-compose up -d

# 查看容器状态
docker-compose ps
```

4. 查看日志然后登录微信

```bash
# 查看日志获取登录二维码
docker-compose logs -f xybotv2
```

扫描终端显示的二维码完成登录。（如果扫不出来，可以打开链接扫码）。首次登录成功后,需要挂机4小时。之后机器人就会自动开始正常运行。

5. 配置文件修改

```bash
# 查看数据卷位置
docker volume inspect xybotv2

# 编辑对应目录下的配置文件
xybotv2-volumes-dir/_data/main_config.toml
xybotv2-volumes-dir/_data/plugins/all_in_one_config.toml
```

修改配置后需要重启容器使配置生效:

```bash
docker-compose restart xybotv2
```

### 常见问题

1. Redis 连接失败

- 检查 DragonFly 服务是否正常运行
- 确认 main_config.toml 中的 redis-host 配置是否正确

2. 配置文件修改未生效

- 重启容器: `docker-compose restart xybotv2`
- 检查配置文件权限是否正确

3. 日志查看

```bash
# 查看实时日志
docker-compose logs -f xybotv2

# 查看最近100行日志
docker-compose logs --tail=100 xybotv2
```