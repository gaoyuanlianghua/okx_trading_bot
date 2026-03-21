#!/usr/bin/env python3
"""
交易机器人无GUI模式启动脚本

此脚本用于在无图形界面的服务器上启动交易机器人
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入交易机器人
from main import TradingBot

if __name__ == "__main__":
    # 创建交易机器人实例
    trading_bot = TradingBot()
    
    # 以无GUI模式启动交易机器人
    exit_code = trading_bot.start(use_gui=False)
    
    print(f"交易机器人退出，退出码: {exit_code}")
    sys.exit(exit_code)
