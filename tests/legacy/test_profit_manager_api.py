#!/usr/bin/env python3
"""
测试收益器的API功能
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.utils.profit_growth_manager import profit_growth_manager
from datetime import datetime

print('=' * 80)
print('测试收益器的API功能')
print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('=' * 80)

# 测试1: 获取当前价格
print('\n' + '-' * 60)
print('测试1: 获取当前价格')
print('-' * 60)
try:
    current_price = profit_growth_manager.get_current_price()
    print(f'当前BTC-USDT价格: {current_price:.2f} USDT')
except Exception as e:
    print(f'获取价格失败: {e}')

# 测试2: 获取持仓信息
print('\n' + '-' * 60)
print('测试2: 获取持仓信息')
print('-' * 60)
try:
    positions = profit_growth_manager.get_positions()
    if positions.get('data'):
        print(f'获取到 {len(positions["data"])} 个持仓')
        for position in positions['data']:
            inst_id = position.get('instId')
            pos = position.get('pos')
            avg_px = position.get('avgPx')
            if float(pos) > 0:
                print(f'{inst_id}: {pos} @ {avg_px} USDT')
    else:
        print('无持仓信息')
except Exception as e:
    print(f'获取持仓失败: {e}')

# 测试3: 获取账户余额
print('\n' + '-' * 60)
print('测试3: 获取账户余额')
print('-' * 60)
try:
    balance = profit_growth_manager.get_account_balance()
    if balance.get('data'):
        data = balance['data'][0]
        total_eq = data.get('totalEq', '0')
        print(f'账户总权益: {total_eq} USDT')
        details = data.get('details', [])
        for detail in details:
            ccy = detail.get('ccy')
            avail_bal = detail.get('availBal', '0')
            cash_bal = detail.get('cashBal', '0')
            if float(avail_bal) > 0 or float(cash_bal) > 0:
                print(f'{ccy}: 可用 {avail_bal}, 现金 {cash_bal}')
    else:
        print('无余额信息')
except Exception as e:
    print(f'获取余额失败: {e}')

# 测试4: 获取持仓收益
print('\n' + '-' * 60)
print('测试4: 获取持仓收益')
print('-' * 60)
try:
    pnl_data = profit_growth_manager.get_position_pnl()
    if pnl_data.get('data'):
        print(f'获取到 {len(pnl_data["data"])} 个持仓收益')
        for position in pnl_data['data']:
            inst_id = position.get('instId')
            pos = position.get('pos')
            upl = position.get('upl', '0')
            realized_pnl = position.get('realizedPnl', '0')
            if float(pos) > 0:
                print(f'{inst_id}: 未实现盈亏 {upl} USDT, 已实现盈亏 {realized_pnl} USDT')
    else:
        print('无持仓收益信息')
except Exception as e:
    print(f'获取持仓收益失败: {e}')

# 测试5: 与API同步数据
print('\n' + '-' * 60)
print('测试5: 与API同步数据')
print('-' * 60)
try:
    success = profit_growth_manager.sync_with_api()
    if success:
        print('✅ API同步成功')
        print(f'同步后持有BTC: {profit_growth_manager.get_total_btc_held():.8f} BTC')
        print(f'同步后平均买入价格: {profit_growth_manager.get_avg_buy_price():.2f} USDT')
    else:
        print('❌ API同步失败')
except Exception as e:
    print(f'同步失败: {e}')

# 测试6: 获取API持仓统计信息
print('\n' + '-' * 60)
print('测试6: 获取API持仓统计信息')
print('-' * 60)
try:
    stats = profit_growth_manager.get_api_position_stats()
    if stats:
        print(f'当前价格: {stats.get("current_price", 0):.2f} USDT')
        print(f'总价值: {stats.get("total_value", 0):.2f} USDT')
        print(f'总收益: {stats.get("total_pnl", 0):.2f} USDT')
        positions = stats.get('positions', [])
        for pos in positions:
            print(f'\n{pos["inst_id"]}:')
            print(f'  持仓类型: {pos["position_type"]}')
            print(f'  杠杆倍数: {pos["leverage"]}x')
            print(f'  持仓价值: {pos["amount_usdt"]:.8f} USDT')
            print(f'  实际BTC数量: {pos["amount_btc"]:.8f} BTC')
            print(f'  平均价格: {pos["avg_price"]:.2f} USDT/BTC')
            print(f'  当前价格: {pos["current_price"]:.2f} USDT/BTC')
            print(f'  当前价值: {pos["value"]:.2f} USDT')
            print(f'  收益: {pos["pnl"]:.2f} USDT')
            print(f'  杠杆收益: {pos["leveraged_pnl"]:.2f} USDT')
            print(f'  收益率: {pos["pnl_rate"]:.2f}%')
            print(f'  杠杆收益率: {pos["leveraged_pnl_rate"]:.2f}%')
    else:
        print('无统计信息')
except Exception as e:
    print(f'获取统计信息失败: {e}')

# 测试7: 检查收益器基本功能
print('\n' + '-' * 60)
print('测试7: 收益器基本功能')
print('-' * 60)
try:
    stats = profit_growth_manager.get_stats()
    print(f'累计盈利: {stats["total_profit_usdt"]:.4f} USDT, {stats["total_profit_btc"]:.8f} BTC')
    print(f'交易次数: {stats["trade_count"]}')
    print(f'最小盈利率: {stats["min_profit_rate"] * 100:.2f}%')
    if stats["last_sell_price"]:
        print(f'上次卖出价格: {stats["last_sell_price"]:.2f} USDT')
    if stats["avg_buy_price"] > 0:
        print(f'平均买入价格: {stats["avg_buy_price"]:.2f} USDT')
    print(f'持有BTC数量: {stats["total_btc_held"]:.8f} BTC')
except Exception as e:
    print(f'获取收益器统计信息失败: {e}')

print('\n' + '=' * 80)
print('测试完成！')
print('=' * 80)