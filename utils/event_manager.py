from typing import Callable, Dict, List, Any

class EventManager:
    _handlers: Dict[str, List[tuple[Callable, object]]] = {}
    
    @classmethod
    def bind_instance(cls, instance: object):
        """将实例绑定到对应的事件处理函数"""
        for method_name in dir(instance):
            method = getattr(instance, method_name)
            if hasattr(method, '_event_type'):
                event_type = getattr(method, '_event_type')
                if event_type not in cls._handlers:
                    cls._handlers[event_type] = []
                cls._handlers[event_type].append((method, instance))

    @classmethod
    async def emit(cls, event_type: str, *args, **kwargs) -> List[Any]:
        """触发事件"""
        if event_type not in cls._handlers:
            return []
        
        results = []
        for handler, instance in cls._handlers[event_type]:
            result = handler(*args, **kwargs)
            if hasattr(result, '__await__'):
                result = await result
            results.append(result)

        return results 