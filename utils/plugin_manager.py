import importlib
import inspect
import os
import sys
from typing import Dict, Type, List

from loguru import logger

from .event_manager import EventManager
from .plugin_base import PluginBase


class PluginManager:
    def __init__(self):
        self.plugins: Dict[str, PluginBase] = {}
        self.plugin_classes: Dict[str, Type[PluginBase]] = {}

    async def load_plugin(self, bot, plugin_class: Type[PluginBase]) -> bool:
        """加载单个插件"""
        try:
            plugin_name = plugin_class.__name__
            if plugin_name in self.plugins:
                return False

            plugin = plugin_class()
            EventManager.bind_instance(plugin)
            await plugin.on_enable(bot)
            self.plugins[plugin_name] = plugin
            self.plugin_classes[plugin_name] = plugin_class
            return True
        except Exception as e:
            logger.error(f"加载插件 {plugin_class.__name__} 时发生错误: {e}")
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
            return True
        except Exception as e:
            logger.error(f"卸载插件 {plugin_name} 时发生错误: {e}")
            return False

    async def load_plugins_from_directory(self, bot, directory: str) -> List[str]:
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
                    logger.error(f"加载插件模块 {module_name} 时发生错误: {e}")

        return loaded_plugins

    async def unload_all_plugins(self) -> List[str]:
        """卸载所有插件"""
        unloaded_plugins = []
        for plugin_name in list(self.plugins.keys()):
            if await self.unload_plugin(plugin_name):
                unloaded_plugins.append(plugin_name)
        return unloaded_plugins

    async def reload_plugin(self, plugin_name: str) -> bool:
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
                    return await self.load_plugin(obj)

            return False
        except Exception as e:
            logger.error(f"重载插件 {plugin_name} 时发生错误: {e}")
            return False

    async def reload_all_plugins(self) -> List[str]:
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
            return await self.load_plugins_from_directory(plugin_dir)

        except Exception as e:
            logger.error(f"重载所有插件时发生错误: {e}")
            return []
