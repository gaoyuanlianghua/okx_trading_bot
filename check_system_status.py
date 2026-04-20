#!/usr/bin/env python3
"""
查看交易系统状态
"""
import json
import os
from datetime import datetime

print("=" * 80)
print("交易系统状态报告")
print("=" * 80)
print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# 1. 协调智能体状态
print("[1] 协调智能体状态")
print("-" * 80)
try:
    with open("data/coordinator_agent_state.json", "r") as f:
        coord_state = json.load(f)
    print(f"总交易金额: {coord_state.get('total_trade_amount', 0)} USDT")
    print(f"总盈亏: {coord_state.get('total_pnl', 0)} USDT")
    print(f"总交易次数: {coord_state.get('total_trades', 0)}")
    print(f"盈利交易次数: {coord_state.get('winning_trades', 0)}")
    if "symbol_profit" in coord_state:
        print()
        print(f"各交易对累计收益:")
        for symbol, profit in coord_state["symbol_profit"].items():
            limit = 10 + profit
            limit = max(5, min(limit, 50))
            print(f"  {symbol}: {profit:.4f} USDT (保证金限制: {limit:.2f} USDT")
except FileNotFoundError:
    print("  未找到coordinator_agent_state.json")
except Exception as e:
    print(f"  错误: {e}")
print()

# 2. 盈利增长管理器状态
print("[2] 盈利增长管理器状态")
print("-" * 80)
try:
    with open("data/profit_growth_state.json", "r") as f:
        profit_state = json.load(f)
    print(f"累计盈利 (USDT): {profit_state.get('total_profit_usdt', 0):.4f}")
    print(f"累计盈利 (BTC): {profit_state.get('total_profit_btc', 0):.8f}")
    print(f"交易总数: {profit_state.get('trade_count', 0)}")
    print(f"上次卖出价格: {profit_state.get('last_sell_price', 0)}")
    print(f"平均买入价格: {profit_state.get('avg_buy_price', 0)}")
    print(f"持有BTC数量: {profit_state.get('total_btc_held', 0):.8f}")
    print(f"最后更新: {profit_state.get('last_update', 'N/A')}")
except FileNotFoundError:
    print("  未找到profit_growth_state.json")
except Exception as e:
    print(f"  错误: {e}")
print()

# 3. 持仓订单状态
print("[3] 订单缓存")
print("-" * 80)
try:
    with open("data/order_agent_state.json", "r") as f:
        order_state = json.load(f)
    orders_cache = order_state.get("orders_cache", {})
    print(f"订单缓存数量: {len(orders_cache)}")
    if orders_cache:
        print("最近订单:")
        # 获取最近的订单
        for i, (order_id, order_info) in enumerate(list(orders_cache.items())[-5:], 1):
            print(f"  [{i}] {order_info.get('instId')} {order_info.get('side')} {order_info.get('sz')}")
except FileNotFoundError:
    print("  未找到order_agent_state.json")
except Exception as e:
    print(f"  错误: {e}")
print()

# 4. 日志和磁盘空间
print("[4] 系统状态")
print("-" * 80)
try:
    # 检查日志大小
    def get_size(path):
        size = 0
        if os.path.isfile(path):
            size = os.path.getsize(path)
        elif os.path.isdir(path):
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.isfile(filepath):
                        size += os.path.getsize(filepath)
        return size

    logs_size = get_size("logs")
    print(f"日志目录大小: {logs_size / (1024 * 1024 * 1024):.2f} GB")
    data_size = get_size("data")
    print(f"数据目录大小: {data_size / (1024 * 1024):.2f} MB")
    
    # 检查磁盘空间
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        print(f"磁盘总空间: {total / (1024 * 1024 * 1024):.2f} GB")
        print(f"已使用空间: {used / (1024 * 1024 * 1024):.2f} GB")
        print(f"剩余空间: {free / (1024 * 1024 * 1024):.2f} GB")
    except Exception:
        pass
except Exception as e:
    print(f"  错误: {e}")

print()
print("=" * 80)
print("状态检查完成")
print("=" * 80)
