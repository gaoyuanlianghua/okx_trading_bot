#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
记录策略值变化的logs
"""

import os
import time
import logging
from datetime import datetime
import json

# 配置日志
log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs', 'strategy')
os.makedirs(log_dir, exist_ok=True)

# 当日日期
current_date = datetime.now().strftime('%Y-%m-%d')
log_file = os.path.join(log_dir, f'strategy_changes_{current_date}.log')

# 配置日志记录器
logger = logging.getLogger('StrategyLogger')
logger.setLevel(logging.INFO)

# 创建文件处理器
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)

# 创建控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# 设置日志格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# 添加处理器
logger.addHandler(file_handler)
logger.addHandler(console_handler)

class StrategyChangeLogger:
    """策略变化日志记录器"""
    
    def __init__(self):
        self.change_count = 0
        self.start_time = time.time()
        self.previous_params = {}
        self.previous_signal = {}
        logger.info(f"=== 策略变化日志监控开始 ===")
        logger.info(f"监控时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    def log_parameter_change(self, params):
        """记录策略参数变化"""
        # 检查参数是否有变化
        changes = {}
        for key, value in params.items():
            if key not in self.previous_params or self.previous_params[key] != value:
                changes[key] = {
                    'old': self.previous_params.get(key),
                    'new': value,
                    'change': value - self.previous_params.get(key, 0) if isinstance(value, (int, float)) else 'changed'
                }
        
        if changes:
            self.change_count += 1
            logger.info(f"[参数变化 #{self.change_count}]")
            for key, change_info in changes.items():
                logger.info(f"  {key}:")
                logger.info(f"    旧值: {change_info['old']}")
                logger.info(f"    新值: {change_info['new']}")
                if isinstance(change_info['change'], (int, float)):
                    logger.info(f"    变化: {change_info['change']:.6f}")
            logger.info("  " + "-" * 50)
            
            # 更新之前的参数
            self.previous_params = params.copy()
    
    def log_signal_change(self, signal):
        """记录策略信号变化"""
        # 检查信号是否有变化
        changes = {}
        for key, value in signal.items():
            if key not in self.previous_signal or self.previous_signal[key] != value:
                changes[key] = {
                    'old': self.previous_signal.get(key),
                    'new': value
                }
        
        if changes:
            self.change_count += 1
            logger.info(f"[信号变化 #{self.change_count}]")
            for key, change_info in changes.items():
                logger.info(f"  {key}:")
                logger.info(f"    旧值: {change_info['old']}")
                logger.info(f"    新值: {change_info['new']}")
            logger.info("  " + "-" * 50)
            
            # 更新之前的信号
            self.previous_signal = signal.copy()
    
    def log_strategy_execution(self, execution_info):
        """记录策略执行情况"""
        self.change_count += 1
        logger.info(f"[策略执行 #{self.change_count}]")
        logger.info(f"  策略名称: {execution_info.get('strategy_name', 'Unknown')}")
        logger.info(f"  执行时间: {execution_info.get('timestamp', datetime.now().isoformat())}")
        logger.info(f"  市场数据: {json.dumps(execution_info.get('market_data', {}), indent=4)}")
        logger.info(f"  订单数据: {json.dumps(execution_info.get('order_data', {}), indent=4)}")
        logger.info(f"  计算指标: {json.dumps(execution_info.get('indicators', {}), indent=4)}")
        logger.info("  " + "-" * 50)
    
    def log_summary(self):
        """记录监控摘要"""
        elapsed_time = time.time() - self.start_time
        logger.info("=== 策略变化日志监控摘要 ===")
        logger.info(f"监控时长: {elapsed_time:.2f}秒")
        logger.info(f"变化记录次数: {self.change_count}")
        logger.info(f"日志文件: {log_file}")
        logger.info("=== 监控结束 ===")

if __name__ == "__main__":
    # 测试日志记录
    logger = StrategyChangeLogger()
    
    # 模拟参数变化
    test_params = {
        'fall_threshold': 0.02,
        'drift_threshold': 0.001,
        'roc_period': 20,
        'pairing_half_life_window': 60,
        'phase_sync_threshold': 0.3
    }
    logger.log_parameter_change(test_params)
    
    # 模拟参数变化
    test_params['fall_threshold'] = 0.021
    test_params['drift_threshold'] = 0.0011
    logger.log_parameter_change(test_params)
    
    # 模拟信号变化
    test_signal = {
        'side': 'sell',
        'price': 71000.50,
        'signal_strength': 0.7,
        'signal_level': 'SS',
        'signal_score': 55
    }
    logger.log_signal_change(test_signal)
    
    # 模拟策略执行
    test_execution = {
        'strategy_name': 'NuclearDynamicsStrategy',
        'timestamp': datetime.now().isoformat(),
        'market_data': {'price': 71000.50, 'volume': 1000},
        'order_data': {'trade_history': 100, 'pending_orders': 5},
        'indicators': {'spring_drift': 0.005, 'angular_momentum': 0.01}
    }
    logger.log_strategy_execution(test_execution)
    
    logger.log_summary()
    
    print(f"策略变化日志已生成到: {log_file}")
