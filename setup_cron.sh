#!/bin/bash
# 设置定时任务，每5分钟同步一次数据到OSS

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 添加定时任务到crontab
(crontab -l 2>/dev/null; echo "*/5 * * * * cd ${SCRIPT_DIR} && python3 sync_to_oss.py sync >> logs/oss_sync.log 2>&1") | crontab -

echo "✅ 定时任务已设置"
echo "每5分钟自动同步数据到OSS"
echo "日志位置: ${SCRIPT_DIR}/logs/oss_sync.log"

# 创建日志目录
mkdir -p "${SCRIPT_DIR}/logs"

# 显示当前定时任务
echo ""
echo "当前定时任务:"
crontab -l | grep sync_to_oss
