#!/bin/bash

# SSH 无密码登录脚本
# 用于连接到 47.79.20.181 主机

HOST="47.79.20.181"
USER="root"
PASSWORD="w528329818.123"

# 检查 sshpass 是否安装
if ! command -v sshpass &> /dev/null; then
    echo "错误: sshpass 未安装，请先安装 sshpass"
    echo "Ubuntu/Debian: apt install sshpass"
    echo "CentOS/RHEL: yum install sshpass"
    exit 1
fi

# 连接到主机
echo "正在连接到 $HOST..."
sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no $USER@$HOST
