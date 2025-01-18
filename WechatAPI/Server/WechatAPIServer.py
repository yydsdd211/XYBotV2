import os
import platform
import subprocess
import threading
import time

from loguru import logger


class WechatAPIServer:
    def __init__(self):
        self.log_process = None
        self.process = None
        self.server_process = None
        self.macos_arm_executable_path = "../core/XYWechatPad-macos-arm"
        self.macos_x86_executable_path = "../core/XYWechatPad-macos-x86"
        self.linux_x86_executable_path = "../core/XYWechatPad-linux-x86"
        self.windows_executable_path = "./WechatAPI/core/XYWechatPad-windows.exe"

        self.arguments = ["--port", "9000", "--mode", "release", "--redis-host", "127.0.0.1", "--redis-port", "6379",
                          "--redis-password", "", "--redis-db", "0"]

    def __del__(self):
        self.stop()

    def start(self):
        # check platform
        if platform.system() == "Darwin":
            if platform.processor() == "arm":
                command = [self.macos_arm_executable_path] + self.arguments
            else:
                command = [self.macos_x86_executable_path] + self.arguments
        elif platform.system() == "Linux":
            command = [self.linux_x86_executable_path] + self.arguments
        else:
            command = [self.windows_executable_path] + self.arguments

        self.process = subprocess.Popen(command, cwd=os.path.dirname(os.path.abspath(__file__)), stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
        time.sleep(3)
        self.log_process = threading.Thread(target=self.process_stdout_to_log, daemon=True)
        self.log_process.start()

    def stop(self):
        self.process.terminate()
        self.log_process.join()

    def process_stdout_to_log(self):
        while True:
            if self.process.poll() is None:
                logger.error("WechatAPI服务已停止")
                return

            line = self.process.stdout.readline()
            if not line:
                break

            logger.log("API", line.decode("utf-8").strip())

    def set_arguments(self, port: int = 9000, mode: str = "release", redis_host: str = "127.0.0.1",
                      redis_port: int = 6379, redis_password: str = "", redis_db: int = 0):

        if mode not in ["debug", "release"]:
            raise ValueError("mode must be 'debug' or 'release'")

        self.arguments = ["--port", str(port), "--mode", mode, "--redis-host", redis_host, "--redis-port",
                          str(redis_port), "--redis-db", str(redis_db)]

        if redis_password:
            self.arguments.extend(["--redis-password", redis_password])
