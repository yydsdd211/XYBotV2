#!/bin/bash
# 启动Redis服务
service redis-server start
# 执行主程序
exec python main.py