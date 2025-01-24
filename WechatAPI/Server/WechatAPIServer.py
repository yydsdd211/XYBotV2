import os
import platform
import subprocess
import threading

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

    def start(self, port: int = 9000, mode: str = "release", redis_host: str = None, redis_port: int = 6379,
              redis_password: str = "", redis_db: int = 0):
        """
        Start WechatAPI server
        :param port:
        :param mode:
        :param redis_host:
        :param redis_port:
        :param redis_password:
        :param redis_db:
        :return:
        """

        if redis_host is None:
            redis_host = get_redis_host()

        arguments = ["--port", str(port), "--mode", mode, "--redis-host", redis_host, "--redis-port", str(redis_port),
                     "--redis-password", redis_password, "--redis-db", str(redis_db)]

        # check platform
        if platform.system() == "Darwin":
            if platform.processor() == "arm":
                command = [self.macos_arm_executable_path] + arguments
            else:
                command = [self.macos_x86_executable_path] + arguments
        elif platform.system() == "Linux":
            command = [self.linux_x86_executable_path] + arguments
        else:
            command = [self.windows_executable_path] + arguments

        self.process = subprocess.Popen(command, cwd=os.path.dirname(os.path.abspath(__file__)), stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
        self.log_process = threading.Thread(target=self.process_stdout_to_log, daemon=True)
        self.log_process.start()

    def stop(self):
        self.process.terminate()
        self.log_process.join()

    def process_stdout_to_log(self):
        while True:
            line = self.process.stdout.readline()
            if not line:
                break

            logger.log("API", line.decode("utf-8").strip())


def is_running_in_docker():
    """检查是否在 Docker 容器中运行"""
    try:
        with open('/proc/1/cgroup', 'r') as f:
            return 'docker' in f.read() or 'kubepods' in f.read()
    except:
        return False


def get_redis_host():
    """根据运行环境返回 Redis 主机地址"""
    if is_running_in_docker():
        return "dragonfly"  # Docker 环境使用容器名
    return "127.0.0.1"
