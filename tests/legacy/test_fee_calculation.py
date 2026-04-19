#!/usr/bin/env python3
"""
测试买入卖出两次币种转换的手续费计算
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.utils.profit_growth_manager import profit_growth_manager
from datetime import datetime

print('=' * 80)
print('测试买入卖出两次币种转换的手续费计算')
print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('=' * 80)

# 测试用例1: 不同杠杆倍数的手续费计算
print('\n' + '-' * 60)
print('测试用例1: 不同杠杆倍数的手续费计算')
print('-' * 60)
try:
    buy_amount = 0.0001  # 买入0.0001 BTC
    buy_price = 70000  # 买入价格70000 USDT
    sell_amount = 0.0001  # 卖出0.0001 BTC
    sell_price = 71000  # 卖出价格71000 USDT
    
    # 测试不同杠杆倍数
    for leverage in [1.0, 2.0, 3.0]:
        fees = profit_growth_manager.calculate_total_fees(
            buy_amount=buy_amount,
            buy_price=buy_price,
            sell_amount=sell_amount,
            sell_price=sell_price,
            buy_fee_currency='USDT',
            sell_fee_currency='USDT',
            leverage=leverage
        )
        
        print(f'\n杠杆倍数: {leverage}x')
        print(f'买入: {buy_amount:.4f} BTC @ {buy_price:.2f} USDT')
        print(f'卖出: {sell_amount:.4f} BTC @ {sell_price:.2f} USDT')
        print(f'买入手续费: {fees["buy_fee"]:.8f} {fees["buy_fee_currency"]}')
        print(f'卖出手续费: {fees["sell_fee"]:.8f} {fees["sell_fee_currency"]}')
        print(f'总手续费(USDT): {fees["total_fee_usdt"]:.8f} USDT')
        
        # 计算预期收益
        expected_profit = (sell_price - buy_price) * sell_amount * leverage - fees["total_fee_usdt"]
        print(f'预期收益: {expected_profit:.4f} USDT')
        
        # 计算收益率
        cost = buy_price * buy_amount * leverage
        roi = (expected_profit / cost) * 100
        print(f'收益率: {roi:.4f}%')
    

except Exception as e:
    print(f'测试失败: {e}')

# 测试用例2: 买入用BTC计价手续费，卖出用USDT计价（不同杠杆）
print('\n' + '-' * 60)
print('测试用例2: 买入用BTC计价手续费，卖出用USDT计价（不同杠杆）')
print('-' * 60)
try:
    buy_amount = 0.0001  # 买入0.0001 BTC
    buy_price = 70000  # 买入价格70000 USDT
    sell_amount = 0.0001  # 卖出0.0001 BTC
    sell_price = 71000  # 卖出价格71000 USDT
    
    # 测试2倍杠杆
    leverage = 2.0
    fees = profit_growth_manager.calculate_total_fees(
        buy_amount=buy_amount,
        buy_price=buy_price,
        sell_amount=sell_amount,
        sell_price=sell_price,
        buy_fee_currency='BTC',
        sell_fee_currency='USDT',
        leverage=leverage
    )
    
    print(f'杠杆倍数: {leverage}x')
    print(f'买入: {buy_amount:.4f} BTC @ {buy_price:.2f} USDT')
    print(f'卖出: {sell_amount:.4f} BTC @ {sell_price:.2f} USDT')
    print(f'买入手续费: {fees["buy_fee"]:.8f} {fees["buy_fee_currency"]}')
    print(f'卖出手续费: {fees["sell_fee"]:.8f} {fees["sell_fee_currency"]}')
    print(f'买入手续费(USDT): {fees["buy_fee_usdt"]:.8f} USDT')
    print(f'卖出手续费(USDT): {fees["sell_fee_usdt"]:.8f} USDT')
    print(f'总手续费(USDT): {fees["total_fee_usdt"]:.8f} USDT')
    
    # 计算预期收益（考虑杠杆）
    expected_profit = (sell_price - buy_price) * sell_amount * leverage - fees["total_fee_usdt"]
    print(f'预期收益: {expected_profit:.4f} USDT')
    
    # 计算收益率
    cost = buy_price * buy_amount * leverage
    roi = (expected_profit / cost) * 100
    print(f'收益率: {roi:.4f}%')
except Exception as e:
    print(f'测试失败: {e}')

# 测试用例3: 实际交易场景（2倍杠杆）
print('\n' + '-' * 60)
print('测试用例3: 实际交易场景（2倍杠杆）')
print('-' * 60)
try:
    # 模拟实际交易
    buy_amount = 0.00001  # 小批量交易
    buy_price = 70709.65  # 开仓均价
    sell_amount = 0.00001  # 小批量卖出
    sell_price = 71101.50  # 当前价格
    leverage = 2.0  # 实际使用的2倍杠杆
    
    fees = profit_growth_manager.calculate_total_fees(
        buy_amount=buy_amount,
        buy_price=buy_price,
        sell_amount=sell_amount,
        sell_price=sell_price,
        buy_fee_currency='BTC',  # 买入时用BTC计价
        sell_fee_currency='USDT',  # 卖出时用USDT计价
        leverage=leverage
    )
    
    print(f'杠杆倍数: {leverage}x')
    print(f'买入: {buy_amount:.6f} BTC @ {buy_price:.2f} USDT')
    print(f'卖出: {sell_amount:.6f} BTC @ {sell_price:.2f} USDT')
    print(f'买入手续费: {fees["buy_fee"]:.8f} {fees["buy_fee_currency"]}')
    print(f'卖出手续费: {fees["sell_fee"]:.8f} {fees["sell_fee_currency"]}')
    print(f'总手续费(USDT): {fees["total_fee_usdt"]:.8f} USDT')
    
    # 计算预期收益（考虑杠杆）
    expected_profit = (sell_price - buy_price) * sell_amount * leverage - fees["total_fee_usdt"]
    print(f'预期收益: {expected_profit:.6f} USDT')
    
    # 计算收益率
    cost = buy_price * buy_amount * leverage
    roi = (expected_profit / cost) * 100
    print(f'收益率: {roi:.4f}%')
except Exception as e:
    print(f'测试失败: {e}')

print('\n' + '=' * 80)
print('测试完成！')
print('=' * 80)