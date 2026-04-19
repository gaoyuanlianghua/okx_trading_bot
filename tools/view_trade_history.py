#!/usr/bin/env python3
"""
查看交易记录脚本

用于查看和分析交易历史记录
"""

import json
import os
from datetime import datetime
from core.storage.data_persistence import data_persistence


def print_trade_summary(trades):
    """打印交易摘要"""
    if not trades:
        print("没有交易记录")
        return
    
    total_trades = len(trades)
    total_profit = sum(trade.get('profit', 0) for trade in trades)
    total_fee = sum(trade.get('fee', 0) for trade in trades)
    
    print(f"交易摘要:")
    print(f"总交易次数: {total_trades}")
    print(f"总收益: {total_profit:.4f}")
    print(f"总手续费: {total_fee:.4f}")
    print(f"净收益: {total_profit - total_fee:.4f}")
    print()


def print_trade_details(trades, limit=50):
    """打印交易详情"""
    if not trades:
        return
    
    print("最近的交易记录:")
    print("-" * 120)
    print(f"{'时间':<25} {'交易ID':<20} {'交易对':<15} {'方向':<8} {'价格':<10} {'数量':<10} {'收益':<10} {'手续费':<10} {'状态':<10}")
    print("-" * 120)
    
    # 按时间排序，最新的在前
    sorted_trades = sorted(trades, key=lambda x: x.get('timestamp', ''), reverse=True)
    
    for trade in sorted_trades[:limit]:
        timestamp = trade.get('timestamp', '')
        if isinstance(timestamp, str) and len(timestamp) > 10:
            try:
                timestamp = datetime.fromisoformat(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            except:
                pass
        
        trade_id = trade.get('trade_id', 'N/A')
        inst_id = trade.get('inst_id', 'N/A')
        side = trade.get('side', 'N/A')
        price = trade.get('price', 0)
        amount = trade.get('amount', 0)
        profit = trade.get('profit', 0)
        fee = trade.get('fee', 0)
        status = trade.get('status', 'N/A')
        
        print(f"{timestamp:<25} {trade_id:<20} {inst_id:<15} {side:<8} {price:<10.2f} {amount:<10.6f} {profit:<10.4f} {fee:<10.4f} {status:<10}")
    
    print("-" * 120)


def load_all_trade_logs():
    """加载所有策略的交易日志"""
    all_trades = []
    
    # 查找data目录下的所有交易日志文件
    data_dir = "data"
    if os.path.exists(data_dir):
        for filename in os.listdir(data_dir):
            if filename.endswith('_trades.json'):
                strategy_name = filename.replace('_trades.json', '')
                trades = data_persistence.load_trade_logs(strategy_name)
                all_trades.extend(trades)
    
    return all_trades


def main():
    """主函数"""
    print("===== 交易记录查看器 =====")
    print()
    
    # 加载所有交易记录
    all_trades = load_all_trade_logs()
    
    # 打印交易摘要
    print_trade_summary(all_trades)
    
    # 打印交易详情
    print_trade_details(all_trades)
    
    print()
    print("提示:")
    print("1. 交易记录存储在 data/ 目录下的策略名_trades.json 文件中")
    print("2. 可以修改脚本中的 limit 参数来查看更多交易记录")
    print("3. 交易记录按时间倒序排列，最新的交易在前")


if __name__ == "__main__":
    main()
