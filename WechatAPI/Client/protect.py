import json
import os
from datetime import datetime


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Protect(metaclass=Singleton):
    def __init__(self):
        self.login_stat_path = os.path.join(os.path.dirname(__file__), "login_stat.json")

        if not os.path.exists(self.login_stat_path):
            default_config = {
                "login_time": 0,
                "device_id": ""
            }
            with open(self.login_stat_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(default_config, indent=4, ensure_ascii=False))
            self.login_stat = default_config
        else:
            with open(self.login_stat_path, "r", encoding="utf-8") as f:
                self.login_stat = json.loads(f.read())

        self.login_time = self.login_stat.get("login_time", 0)
        self.login_device_id = self.login_stat.get("device_id", "")

    def check(self, second: int) -> bool:
        now = datetime.now().timestamp()
        return now - self.login_time < second

    def update_login_status(self, device_id: str = ""):
        if device_id == self.login_device_id:
            return
        self.login_time = int(datetime.now().timestamp())
        self.login_stat["login_time"] = self.login_time
        self.login_stat["device_id"] = device_id
        with open(self.login_stat_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(self.login_stat, indent=4, ensure_ascii=False))


protector = Protect()
