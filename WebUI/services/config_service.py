import os
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Union

import tomlkit
from loguru import logger

from WebUI.utils.singleton import Singleton

# 确保可以导入根目录模块
ROOT_DIR = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, str(ROOT_DIR))


class ConfigService(metaclass=Singleton):
    """配置服务类，提供配置文件管理功能
    
    负责读取、保存和验证XYBotV2系统配置，使用TOML格式存储配置信息。
    支持字段验证、默认值和表单模式生成，方便Web界面的配置编辑。
    """

    def __init__(self):
        """初始化配置服务
        
        设置配置文件路径，定义默认配置结构、字段选项和验证规则。
        """
        self.config_path = ROOT_DIR / "main_config.toml"

        # 默认配置结构
        self.default_config = {
            "WechatAPIServer": {
                "port": 9000,
                "mode": "release",
                "redis-host": "127.0.0.1",
                "redis-port": 6379,
                "redis-password": "",
                "redis-db": 0
            },
            "XYBot": {
                "version": "v1.0.0",
                "ignore-protection": False,
                "XYBotDB-url": "sqlite:///database/xybot.db",
                "msgDB-url": "sqlite+aiosqlite:///database/message.db",
                "keyvalDB-url": "sqlite+aiosqlite:///database/keyval.db",
                "admins": ["admin-wxid"],
                "disabled-plugins": ["ExamplePlugin"],
                "timezone": "Asia/Shanghai",
                "ignore-mode": "None"
            },
            "WebUI": {
                "admin-username": "admin",
                "admin-password": "admin123",
                "session-timeout": 30
            }
        }

        # 字段选项（用于表单下拉选择）
        self.field_options = {
            "WechatAPIServer.mode": ["release", "debug"],
            "XYBot.ignore-mode": ["None", "Whitelist", "Blacklist"]
        }

        # 字段验证规则
        self.field_validators = {
            "WechatAPIServer.port": lambda v: isinstance(v, int) and 1 <= v <= 65535,
            "WechatAPIServer.redis-port": lambda v: isinstance(v, int) and 1 <= v <= 65535,
            "WebUI.session-timeout": lambda v: isinstance(v, int) and v > 0
        }

        logger.log('WEBUI', "配置服务初始化完成")

    def get_config(self) -> Dict[str, Any]:
        """获取完整配置
        
        从配置文件读取完整配置，如果文件不存在或读取失败则返回默认配置。
        
        Returns:
            Dict[str, Any]: 配置数据字典
        """
        if not self.config_path.exists():
            logger.log('WEBUI', f"配置文件不存在，将使用默认配置: {self.config_path}")
            return self.default_config

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return tomlkit.parse(f.read())
        except Exception as e:
            logger.log('WEBUI', f"读取配置文件出错: {str(e)}")
            return self.default_config

    def get_toml_doc(self) -> Optional[Union[tomlkit.TOMLDocument, dict]]:
        """获取TOML文档对象，保留所有格式和注释
        
        与get_config不同，此方法返回原始TOML文档对象，保留所有格式和注释。
        
        Returns:
            Optional[Union[tomlkit.TOMLDocument, dict]]: TOML文档对象或None（如果读取失败）
        """
        if not self.config_path.exists():
            logger.log('WEBUI', f"TOML文档不存在: {self.config_path}")
            return None

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return tomlkit.parse(f.read())
        except Exception as e:
            logger.log('WEBUI', f"读取TOML文档出错: {str(e)}")
            return None

    def extract_comments(self) -> Dict[str, str]:
        """从TOML文件中提取注释
        
        解析TOML文件，提取每个配置字段的注释，用于生成表单时提供帮助文本。
        
        Returns:
            Dict[str, str]: 字段路径到注释的映射，格式为 {"section.key": "注释内容"}
        """
        comments = {}

        try:
            # 如果文件不存在，直接返回空字典
            if not self.config_path.exists():
                logger.log('WEBUI', "无法提取注释：配置文件不存在")
                return comments

            # 读取原始文件内容
            with open(self.config_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 按行解析并提取注释
            lines = content.split('\n')
            current_section = ""

            for line in lines:
                line = line.strip()

                # 跳过空行
                if not line:
                    continue

                # 检查是否是节定义行
                section_match = re.match(r'^\[([^\]]+)\]', line)
                if section_match:
                    current_section = section_match.group(1)
                    continue

                # 解析带注释的键值对（key = value # comment）
                kv_comment_match = re.match(r'^([^=]+)=([^#]*)#(.+)$', line)
                if kv_comment_match:
                    key = kv_comment_match.group(1).strip()
                    comment = kv_comment_match.group(3).strip()
                    field_path = f"{current_section}.{key}"
                    comments[field_path] = comment
                    continue

                # 检查键值对后面没有注释的情况（查找前一行是否为注释）
                kv_match = re.match(r'^([^=]+)=(.*)$', line)
                if kv_match:
                    key = kv_match.group(1).strip()
                    # 寻找前一行是否是该字段的注释
                    i = lines.index(line) - 1
                    if i >= 0 and lines[i].strip().startswith('#'):
                        comment = lines[i].strip()[1:].strip()
                        field_path = f"{current_section}.{key}"
                        comments[field_path] = comment

            logger.log('WEBUI', f"成功提取配置注释 {len(comments)} 条")
            return comments
        except Exception as e:
            logger.log('WEBUI', f"提取注释出错: {str(e)}")
            return {}

    def save_config(self, config: Dict[str, Any]) -> bool:
        """保存配置到文件
        
        将配置保存到TOML文件，会尝试保留现有的注释和格式。
        
        Args:
            config: 要保存的配置数据
            
        Returns:
            bool: 是否成功保存
        """
        try:
            # 如果配置文件已存在，先读取它以保留注释和格式
            doc = tomlkit.document()
            if self.config_path.exists():
                try:
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        doc = tomlkit.parse(f.read())
                except Exception as e:
                    logger.log('WEBUI', f"读取现有配置文件失败，将创建新文件: {str(e)}")
                    # 如果读取失败，创建新文档
                    doc = tomlkit.document()

            # 更新配置
            for section_name, section_data in config.items():
                if section_name not in doc:
                    doc[section_name] = tomlkit.table()

                for key, value in section_data.items():
                    doc[section_name][key] = value

            # 保存配置
            with open(self.config_path, "w", encoding="utf-8") as f:
                f.write(tomlkit.dumps(doc))

            logger.log('WEBUI', "配置已成功保存")
            return True
        except Exception as e:
            logger.log('WEBUI', f"保存配置文件出错: {str(e)}")
            return False

    def get_form_schema(self) -> Dict[str, Any]:
        """获取表单架构，用于Web界面动态生成配置表单
        
        根据当前配置和字段元数据生成符合前端需求的表单架构。
        
        Returns:
            Dict[str, Any]: 表单架构，格式为 {section_name: {title, description, properties}}
        """
        config = self.get_config()

        # 从TOML文件中提取注释
        comments = self.extract_comments()

        # 创建符合前端预期的schema格式
        schemas = {}

        # 遍历配置节
        for section_name, section_data in config.items():
            # 创建该配置节的schema
            section_schema = {
                "title": section_name,
                "description": "",  # 可以为配置节添加描述信息
                "properties": {}
            }

            # 遍历字段
            for field_name, field_value in section_data.items():
                field_path = f"{section_name}.{field_name}"
                field_type = self._get_field_type(field_value)

                # 从TOML注释中获取字段描述
                field_description = comments.get(field_path, "")

                # 创建字段的schema
                field_schema = {
                    "title": field_name,
                    "type": field_type,
                    "description": field_description,
                }

                # 添加选项（如果有）
                if self.field_options.get(field_path):
                    field_schema["enum"] = self.field_options.get(field_path, [])

                # 如果是数组类型，添加items描述
                if field_type == "array":
                    # 确定数组元素类型
                    items_type = "string"  # 默认为字符串类型
                    if field_value and len(field_value) > 0:
                        items_type = self._get_field_type(field_value[0])

                    field_schema["items"] = {"type": items_type}

                # 将字段schema添加到配置节properties中
                section_schema["properties"][field_name] = field_schema

            # 将配置节schema添加到总schema中
            schemas[section_name] = section_schema

        logger.log('WEBUI', f"已生成配置表单架构，包含 {len(schemas)} 个配置节")
        return schemas

    def validate_config(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """验证配置是否符合规则
        
        检查配置中的字段是否符合预定义的验证规则。
        
        Args:
            config: 要验证的配置数据
            
        Returns:
            Tuple[bool, List[str]]: (是否验证通过, 错误信息列表)
        """
        errors = []

        for section_name, section_data in config.items():
            for field_name, field_value in section_data.items():
                field_path = f"{section_name}.{field_name}"

                # 如果有验证器，则进行验证
                if field_path in self.field_validators:
                    validator = self.field_validators[field_path]
                    if not validator(field_value):
                        errors.append(f"字段 '{field_path}' 的值 '{field_value}' 无效")

        if errors:
            logger.log('WEBUI', f"配置验证失败，发现 {len(errors)} 个错误")
            for error in errors:
                logger.log('WEBUI', f"配置错误: {error}")
        else:
            logger.log('WEBUI', "配置验证通过")

        return len(errors) == 0, errors

    def _dict_to_toml(self, data: Dict[str, Any]) -> str:
        """将字典转换为TOML字符串
        
        内部工具方法，将配置字典转换为格式化的TOML字符串。
        
        Args:
            data: 要转换的字典数据
            
        Returns:
            str: 格式化的TOML字符串
        """
        doc = tomlkit.document()

        for section_name, section_data in data.items():
            table = tomlkit.table()

            for key, value in section_data.items():
                table.add(key, value)

            doc.add(section_name, table)

        return tomlkit.dumps(doc)

    def _get_field_type(self, value: Any) -> str:
        """推断字段值的数据类型
        
        根据字段值推断适合的JSON Schema类型名称。
        
        Args:
            value: 字段值
            
        Returns:
            str: 字段类型名称（如"boolean", "integer", "string"等）
        """
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "number"
        elif isinstance(value, list):
            return "array"
        elif isinstance(value, dict):
            return "object"
        elif isinstance(value, str):
            return "string"
        else:
            return "string"  # 默认为字符串类型

    def get_version(self) -> str:
        """获取XYBot版本号
        
        从配置中提取XYBot的版本号。
        
        Returns:
            str: 版本号，如果未找到则返回"未知"
        """
        config = self.get_config()
        try:
            return config.get("XYBot", {}).get("version", "未知")
        except Exception as e:
            logger.log('WEBUI', f"获取版本号失败: {str(e)}")
            return "未知"


# 创建配置服务实例
config_service = ConfigService()
