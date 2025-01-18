from functools import wraps
from typing import Callable

def on_text_message(func: Callable):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        return func(self, *args, **kwargs)
    setattr(wrapper, '_event_type', 'text_message')
    return wrapper

def on_image_message(func: Callable):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        return func(self, *args, **kwargs)
    setattr(wrapper, '_event_type', 'image_message')
    return wrapper

def on_voice_message(func: Callable):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        return func(self, *args, **kwargs)
    setattr(wrapper, '_event_type', 'voice_message')
    return wrapper

def on_emoji_message(func: Callable):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        return func(self, *args, **kwargs)
    setattr(wrapper, '_event_type', 'voice_message')
    return wrapper

def on_file_message(func: Callable):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        return func(self, *args, **kwargs)
    setattr(wrapper, '_event_type', 'file_message')
    return wrapper

def on_quote_message(func: Callable):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        return func(self, *args, **kwargs)
    setattr(wrapper, '_event_type', 'quote_message')
    return wrapper

def on_video_message(func: Callable):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        return func(self, *args, **kwargs)
    setattr(wrapper, '_event_type', 'video_message')
    return wrapper

def on_pat_message(func: Callable):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        return func(self, *args, **kwargs)
    setattr(wrapper, '_event_type', 'pat_message')
    return wrapper