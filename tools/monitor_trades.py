#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# monitor_trades.py
# 监控和记录触发的多空交易订单

import time
import logging
import json
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('trade_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TradeMonitor:
    """交易监控器"""
    
    def __init__(self):
        """初始化监控器"""
        self.trade_logs = []
        self.last_check_time = time.time()
    
    def monitor_trades(self):
        """监控交易订单"""
        logger.info("开始监控交易订单...")
        
        try:
            while True:
                # 读取交易机器人日志
                try:
                    with open('logs/trading_bot_bg.log', 'r') as f:
                        lines = f.readlines()
                except Exception as e:
                    logger.error(f"读取日志文件失败: {e}")
                    time.sleep(5)
                    continue
                
                # 分析日志，查找交易订单
                for line in lines:
                    if "下单成功" in line:
                        # 提取订单信息
                        order_id = line.split("下单成功: ")[1].strip()
                        timestamp = line.split(" - ")[0]
                        
                        # 检查是否是新订单
                        if not any(log['order_id'] == order_id for log in self.trade_logs):
                            trade_info = {
                                'timestamp': timestamp,
                                'order_id': order_id,
                                'status': 'success',
                                'direction': 'unknown',  # 需要从上下文推断
                                'price': 'unknown',
                                'amount': 'unknown'
                            }
                            
                            # 尝试从上下文推断交易方向
                            # 这里可以根据实际日志格式进行调整
                            
                            self.trade_logs.append(trade_info)
                            logger.info(f"新订单: {trade_info}")
                            
                            # 保存到文件
                            self.save_trades()
                    
                    elif "拒绝交易" in line:
                        # 提取拒绝交易的信息
                        reason = line.split("拒绝交易: ")[1].strip()
                        timestamp = line.split(" - ")[0]
                        
                        trade_info = {
                            'timestamp': timestamp,
                            'order_id': 'N/A',
                            'status': 'rejected',
                            'reason': reason
                        }
                        
                        self.trade_logs.append(trade_info)
                        logger.info(f"拒绝交易: {trade_info}")
                        
                        # 保存到文件
                        self.save_trades()
                
                # 每5秒检查一次
                time.sleep(5)
                
        except KeyboardInterrupt:
            logger.info("监控停止")
        except Exception as e:
            logger.error(f"监控过程中出错: {e}")
    
    def save_trades(self):
        """保存交易记录"""
        try:
            with open('trade_records.json', 'w') as f:
                json.dump(self.trade_logs, f, indent=2, ensure_ascii=False)
            logger.info(f"交易记录已保存，共 {len(self.trade_logs)} 条")
        except Exception as e:
            logger.error(f"保存交易记录失败: {e}")

if __name__ == "__main__":
    monitor = TradeMonitor()
    monitor.monitor_trades()
