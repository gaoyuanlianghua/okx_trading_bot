#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成触发预期交易和API定时返回的收益率当日logs
"""

import os
import time
import logging
from datetime import datetime
import json

# 配置日志
log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs', 'trade')
os.makedirs(log_dir, exist_ok=True)

# 当日日期
current_date = datetime.now().strftime('%Y-%m-%d')
log_file = os.path.join(log_dir, f'trade_logs_{current_date}.log')

# 配置日志记录器
trade_logger = logging.getLogger('TradeLogger')
trade_logger.setLevel(logging.INFO)

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
trade_logger.addHandler(file_handler)
trade_logger.addHandler(console_handler)

class TradeLogger:
    """交易日志记录器"""
    
    def __init__(self):
        self.trade_count = 0
        self.api_call_count = 0
        self.start_time = time.time()
        trade_logger.info(f"=== 交易日志监控开始 ===")
        trade_logger.info(f"监控时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    def log_trade(self, trade_info):
        """记录触发的预期交易 - 只记录API返回的已完成订单"""
        # 检查是否为API返回的已完成订单
        is_api_filled = trade_info.get('is_api_filled', False)
        order_state = trade_info.get('state', '')
        
        # 只记录API返回的已完成订单（state为filled）
        if not is_api_filled or order_state != 'filled':
            return
        
        self.trade_count += 1
        trade_logger.info(f"[触发交易 #{self.trade_count}]")
        
        # 策略
        strategy = trade_info.get('strategy', 'NuclearDynamicsStrategy')
        trade_logger.info(f"  策略: {strategy}")
        
        # 方向
        side = trade_info.get('side', 'none')
        trade_logger.info(f"  方向: {side}")
        
        # 价格
        price = trade_info.get('price', 0)
        try:
            price = float(price)
            trade_logger.info(f"  价格: {price:.2f} USDT")
        except (ValueError, TypeError):
            trade_logger.info(f"  价格: {price} USDT")
        
        # 数量
        size = trade_info.get('size', 0)
        try:
            size = float(size)
            trade_logger.info(f"  数量: {size:.8f} BTC")
        except (ValueError, TypeError):
            trade_logger.info(f"  数量: {size} BTC")
        
        # 预期收益
        expected_return = trade_info.get('expected_return', 0)
        trade_logger.info(f"  预期收益: {expected_return * 100:.2f}%")
        
        # 信号级别
        signal_level = trade_info.get('signal_level', 'none')
        trade_logger.info(f"  信号级别: {signal_level}")
        
        # 信号强度
        signal_strength = trade_info.get('signal_strength', 0)
        trade_logger.info(f"  信号强度: {signal_strength:.2f}")
        
        # 信号得分
        signal_score = trade_info.get('signal_score', 0)
        trade_logger.info(f"  信号得分: {signal_score:.0f}")
        
        # 状态
        status = trade_info.get('status', 'success')
        trade_logger.info(f"  状态: {status}")
        
        # 原因
        reason = trade_info.get('reason', 'none')
        trade_logger.info(f"  原因: {reason}")
        
        # 错误
        error = trade_info.get('error', 'none')
        trade_logger.info(f"  错误: {error}")
        
        # 订单ID
        order_id = trade_info.get('order_id', 'none')
        trade_logger.info(f"  订单ID: {order_id}")
        
        # 产品
        inst_id = trade_info.get('inst_id', 'BTC-USDT')
        trade_logger.info(f"  产品: {inst_id}")
        
        # 时间戳
        timestamp = trade_info.get('timestamp', datetime.now().isoformat())
        trade_logger.info(f"  时间戳: {timestamp}")
        
        # API返回标识
        trade_logger.info(f"  API返回订单: ✓")
        
        trade_logger.info("  " + "-" * 50)
    
    def log_api_return(self, api_info):
        """记录API定时返回的收益率"""
        self.api_call_count += 1
        return_rate = api_info.get('return_rate', 0)
        trade_logger.info(f"[API返回 #{self.api_call_count}]")
        trade_logger.info(f"  接口: {api_info.get('endpoint', 'Unknown')}")
        trade_logger.info(f"  收益率: {return_rate * 100:.2f}%")
        trade_logger.info(f"  数据: {json.dumps(api_info.get('data', {}), indent=4)}")
        trade_logger.info(f"  响应时间: {api_info.get('response_time', 0):.2f}ms")
        trade_logger.info("  " + "-" * 50)
    
    def log_summary(self):
        """记录监控摘要"""
        elapsed_time = time.time() - self.start_time
        trade_logger.info("=== 交易日志监控摘要 ===")
        trade_logger.info(f"监控时长: {elapsed_time:.2f}秒")
        trade_logger.info(f"触发交易次数: {self.trade_count}")
        trade_logger.info(f"API调用次数: {self.api_call_count}")
        trade_logger.info(f"日志文件: {log_file}")
        trade_logger.info("=== 监控结束 ===")

if __name__ == "__main__":
    # 测试日志记录
    trade_logger_instance = TradeLogger()
    
    # 模拟触发交易
    test_trade = {
        "strategy": "NuclearDynamicsStrategy",
        "side": "sell",
        "price": 71000.50,
        "size": 0.00001,
        "expected_return": 0.25,  # 大于20%的收益
        "signal_level": "SS",
        "signal_strength": 0.7,
        "signal_score": 55,
        "timestamp": datetime.now().isoformat()
    }
    trade_logger_instance.log_trade(test_trade)
    
    # 模拟API返回
    test_api = {
        "endpoint": "/api/v5/account/balance",
        "return_rate": 0.25,  # 大于20%的收益
        "data": {
            "BTC": 0.00000005,
            "USDT": 0.02
        },
        "response_time": 150.5
    }
    trade_logger_instance.log_api_return(test_api)
    
    trade_logger_instance.log_summary()
    
    print(f"日志已生成到: {log_file}")
