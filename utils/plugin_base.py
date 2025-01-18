from abc import ABC

class PluginBase(ABC):
    """插件基类"""
    def __init__(self):
        self.enabled = False
        
    async def on_enable(self):
        """插件启用时调用"""
        self.enabled = True
    
    async def on_disable(self):
        """插件禁用时调用"""
        self.enabled = False 