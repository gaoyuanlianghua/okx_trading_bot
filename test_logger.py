#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试日志分组显示功能
"""

import time
from commons.logger_config import get_logger

# 获取不同区域的日志记录器
logger_strategy = get_logger(region="Strategy")
logger_market = get_logger(region="MarketData")
logger_order = get_logger(region="Order")
logger_decision = get_logger(region="Decision")

# 生成一些日志
print("开始测试日志分组显示...")
print("="*80)

# 生成Strategy区域的日志
for i in range(4):
    logger_strategy.warning(f"策略执行日志 {i+1}")
    time.sleep(0.1)

# 生成MarketData区域的日志
for i in range(3):
    logger_market.warning(f"市场数据日志 {i+1}")
    time.sleep(0.1)

# 生成Order区域的日志
for i in range(5):
    logger_order.warning(f"订单操作日志 {i+1}")
    time.sleep(0.1)

# 生成Decision区域的日志
for i in range(2):
    logger_decision.warning(f"决策协调日志 {i+1}")
    time.sleep(0.1)

# 刷新缓冲区，显示剩余的日志
from commons.logger_config import global_logger_config
global_logger_config.flush_buffers()

print("\n" + "="*80)
print("日志分组显示测试完成")
