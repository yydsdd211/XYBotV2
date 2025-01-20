import importlib
import inspect
import os
import sys
import tomllib
import traceback
from typing import Dict, Type, List, Union

from loguru import logger

from WechatAPI import WechatAPIClient
from .event_manager import EventManager
from .plugin_base import PluginBase


class PluginManager:
    def __init__(self):
        self.plugins: Dict[str, PluginBase] = {}
        self.plugin_classes: Dict[str, Type[PluginBase]] = {}
        self.plugin_info: Dict[str, dict] = {}  # 新增：存储所有插件信息

        with open("main_config.toml", "rb") as f:
            main_config = tomllib.load(f)

        self.excluded_plugins = main_config["XYBot"]["disabled-plugins"]

    async def load_plugin(self, bot: WechatAPIClient, plugin_class: Type[PluginBase]) -> bool:
        """加载单个插件"""
        try:
            plugin_name = plugin_class.__name__
            # 记录插件信息，即使插件被禁用也会记录
            self.plugin_info[plugin_name] = {
                "name": plugin_name,
                "description": plugin_class.description,
                "author": plugin_class.author,
                "version": plugin_class.version,
                "enabled": False,
                "class": plugin_class
            }
            
            if plugin_name in self.plugins or plugin_name in self.excluded_plugins:
                return False

            plugin = plugin_class()
            EventManager.bind_instance(plugin)
            await plugin.on_enable(bot)
            self.plugins[plugin_name] = plugin
            self.plugin_classes[plugin_name] = plugin_class
            self.plugin_info[plugin_name]["enabled"] = True
            return True
        except Exception as e:
            logger.error(f"加载插件 {plugin_class.__name__} 时发生错误: {traceback.format_exc()}")
            return False

    async def unload_plugin(self, plugin_name: str) -> bool:
        """卸载单个插件"""
        if plugin_name not in self.plugins:
            return False

        try:
            plugin = self.plugins[plugin_name]
            await plugin.on_disable()
            del self.plugins[plugin_name]
            del self.plugin_classes[plugin_name]
            if plugin_name in self.plugin_info:
                self.plugin_info[plugin_name]["enabled"] = False
            return True
        except Exception as e:
            logger.error(f"卸载插件 {plugin_name} 时发生错误: {traceback.format_exc()}")
            return False

    async def load_plugins_from_directory(self, bot: WechatAPIClient, directory: str) -> List[str]:
        """从目录批量加载插件"""
        loaded_plugins = []

        for filename in os.listdir(directory):
            if filename.endswith('.py') and not filename.startswith('__'):
                module_name = filename[:-3]
                try:
                    module = importlib.import_module(f"plugins.{module_name}")
                    for name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and issubclass(obj, PluginBase) and obj != PluginBase:
                            if await self.load_plugin(bot, obj):
                                loaded_plugins.append(obj.__name__)
                except Exception as e:
                    logger.error(f"加载插件模块 {module_name} 时发生错误: {traceback.format_exc()}")

        return loaded_plugins

    async def unload_all_plugins(self) -> List[str]:
        """卸载所有插件"""
        unloaded_plugins = []
        for plugin_name in list(self.plugins.keys()):
            if await self.unload_plugin(plugin_name):
                unloaded_plugins.append(plugin_name)
        return unloaded_plugins

    async def reload_plugin(self, bot: WechatAPIClient, plugin_name: str) -> bool:
        """重载单个插件
        
        Args:
            plugin_name: 要重载的插件名称
            
        Returns:
            bool: 重载是否成功
        """
        if plugin_name not in self.plugin_classes:
            return False

        try:
            # 获取插件类所在的模块
            plugin_class = self.plugin_classes[plugin_name]
            module_name = plugin_class.__module__

            # 先卸载插件
            if not await self.unload_plugin(plugin_name):
                return False

            # 重新导入模块
            module = importlib.import_module(module_name)
            importlib.reload(module)

            # 从重新加载的模块中获取插件类
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj,
                                                       PluginBase) and obj != PluginBase and obj.__name__ == plugin_name:
                    # 加载新的插件类
                    return await self.load_plugin(bot, plugin_class)

            return False
        except Exception as e:
            logger.error(f"重载插件 {plugin_name} 时发生错误: {e}")
            return False

    async def reload_all_plugins(self, bot: WechatAPIClient) -> List[str]:
        """重载所有插件
        
        Returns:
            List[str]: 成功重载的插件名称列表
        """
        try:
            # 记录当前加载的插件名称
            original_plugins = list(self.plugins.keys())

            # 获取插件目录路径（假设所有插件都在同一目录下）
            if not self.plugins:
                return []
            sample_plugin = next(iter(self.plugin_classes.values()))
            plugin_dir = os.path.dirname(inspect.getfile(sample_plugin))

            # 卸载所有插件
            await self.unload_all_plugins()

            # 重新加载所有模块
            for module_name in list(sys.modules.keys()):
                if module_name.startswith('plugins.'):
                    del sys.modules[module_name]

            # 从目录重新加载插件
            return await self.load_plugins_from_directory(bot, plugin_dir)

        except Exception as e:
            logger.error(f"重载所有插件时发生错误: {traceback.format_exc()}")
            return []

    def get_plugin_info(self, plugin_name: str = None) -> Union[dict, List[dict]]:
        """获取插件信息
        
        Args:
            plugin_name: 插件名称，如果为None则返回所有插件信息
            
        Returns:
            如果指定插件名，返回单个插件信息字典；否则返回所有插件信息列表
        """
        if plugin_name:
            return self.plugin_info.get(plugin_name)
        return list(self.plugin_info.values())

    def get_plugin_info_by_name(self, plugin_name: str) -> dict:
        """获取指定插件的信息"""
        return self.plugin_info.get(plugin_name)


plugin_manager = PluginManager()
