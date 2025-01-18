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
        with open(self.login_stat_path, "r", encoding="utf-8") as f:
            self.login_stat = json.loads(f.read())

        self.login_time = self.login_stat.get("login_time", 0)

    def check(self, second: int) -> bool:
        # check if login_time+second < now
        now = datetime.now().timestamp()
        return self.login_time + second < now

    def update_login_time(self, awaken_login: bool = False):
        if awaken_login:
            return
        self.login_time = int(datetime.now().timestamp())
        self.login_stat["login_time"] = self.login_time
        with open(self.login_stat_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(self.login_stat, indent=4, ensure_ascii=False))


protector = Protect()
