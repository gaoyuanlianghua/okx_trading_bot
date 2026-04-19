#!/usr/bin/env python3
"""
完整账户数据同步脚本
同步OKX实际账户数据到本地系统，解决信息不对称问题
"""

import json
import requests
import hmac
import hashlib
import base64
from datetime import datetime, timezone
import yaml
import os

# 读取配置
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

api_key = config['api']['api_key']
api_secret = config['api']['api_secret']
passphrase = config['api']['passphrase']

def get_timestamp():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

def get_signature(timestamp, method, path, body=''):
    message = timestamp + method + path + body
    mac = hmac.new(api_secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode('utf-8')

def get_headers(timestamp, method, path, body=''):
    return {
        'OK-ACCESS-KEY': api_key,
        'OK-ACCESS-SIGN': get_signature(timestamp, method, path, body),
        'OK-ACCESS-TIMESTAMP': timestamp,
        'OK-ACCESS-PASSPHRASE': passphrase,
        'Content-Type': 'application/json'
    }

print('=' * 60)
print('完整账户数据同步')
print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('=' * 60)

# 1. 获取账户余额
timestamp = get_timestamp()
headers = get_headers(timestamp, 'GET', '/api/v5/account/balance')
response = requests.get('https://www.okx.com/api/v5/account/balance', headers=headers)
balance_data = response.json()

# 打印完整的账户余额响应，用于调试
print('\n🔍 账户余额API响应调试信息')
print(f'  状态码: {response.status_code}')
print(f'  响应内容: {balance_data}')

print('\n📊 实际账户余额（OKX）')
actual_balances = {}
actual_liabilities = {}
if balance_data.get('data'):
    for detail in balance_data['data'][0].get('details', []):
        ccy = detail.get('ccy')
        avail_bal = float(detail.get('availBal', '0') or '0')
        cash_bal = float(detail.get('cashBal', '0') or '0')
        eq = float(detail.get('eq', '0') or '0')
        
        # 获取借币相关信息
        liab = float(detail.get('liab', '0') or '0')  # 币种负债额
        interest = float(detail.get('interest', '0') or '0')  # 计息，应扣未扣利息
        max_loan = float(detail.get('maxLoan', '0') or '0')  # 币种最大可借
        cross_liab = float(detail.get('crossLiab', '0') or '0')  # 币种全仓负债额
        iso_liab = float(detail.get('isoLiab', '0') or '0')  # 币种逐仓负债额
        
        if avail_bal > 0 or cash_bal > 0:
            actual_balances[ccy] = {
                'available': avail_bal,
                'cash': cash_bal,
                'equity': eq
            }
            print(f'  {ccy}:')
            print(f'    可用: {avail_bal:.8f}')
            print(f'    现金: {cash_bal:.8f}')
            print(f'    估值: {eq:.8f}')
        
        # 显示借币信息
        if liab > 0:
            print(f'    负债: {liab:.8f}')
        if interest > 0:
            print(f'    未付利息: {interest:.8f}')
        if max_loan > 0:
            print(f'    最大可借: {max_loan:.8f}')
        
        # 保存借币信息
        if liab > 0 or interest > 0:
            actual_liabilities[ccy] = {
                'liab': liab,  # 负债额
                'interest': interest,  # 应扣未扣利息
                'max_loan': max_loan,  # 最大可借
                'cross_liab': cross_liab,  # 全仓负债
                'iso_liab': iso_liab  # 逐仓负债
            }

# 2. 获取持仓信息
timestamp = get_timestamp()
# 尝试获取SPOT和MARGIN类型的持仓
inst_types = ['SPOT', 'MARGIN']
actual_positions = {}

for inst_type in inst_types:
    headers = get_headers(timestamp, 'GET', f'/api/v5/account/positions?instType={inst_type}')
    response = requests.get(f'https://www.okx.com/api/v5/account/positions?instType={inst_type}', headers=headers)
    positions_data = response.json()
    
    # 打印持仓API响应，用于调试
    print(f'\n🔍 {inst_type} 持仓API响应调试信息')
    print(f'  状态码: {response.status_code}')
    print(f'  响应内容: {positions_data}')
    
    # 处理持仓信息
    if positions_data.get('data'):
        for position in positions_data['data']:
            inst_id = position.get('instId')
            pos_side = position.get('posSide')
            pos = float(position.get('pos', '0') or '0')  # 持仓数量
            avg_px = float(position.get('avgPx', '0') or '0')  # 平均持仓价格
            
            if pos > 0:
                actual_positions[inst_id] = {
                    'pos': pos,
                    'avg_px': avg_px,
                    'pos_side': pos_side,
                    'inst_type': inst_type
                }
                print(f'  持仓: {inst_id}')
                print(f'    类型: {inst_type}')
                print(f'    数量: {pos:.8f}')
                print(f'    平均价格: {avg_px:.2f} USDT')
                print(f'    方向: {pos_side}')

if not actual_positions:
    print('\n  无持仓记录')

# 3. 获取交易记录
timestamp = get_timestamp()
# 使用交易记录API端点，获取最近的交易，limit参数改为100
headers = get_headers(timestamp, 'GET', '/api/v5/trade/fills?limit=100')
response = requests.get('https://www.okx.com/api/v5/trade/fills?limit=100', headers=headers)
orders_data = response.json()

# 打印API响应，用于调试
print('\n🔍 API响应调试信息')
print(f'  状态码: {response.status_code}')
print(f'  响应内容: {orders_data}')

print('\n📜 最近交易历史（OKX）')
actual_trades = []
if orders_data.get('data'):
    for order in orders_data['data'][:15]:  # 显示最近15笔交易
        inst_id = order.get('instId')
        side = order.get('side')
        sz = order.get('fillSz')  # 使用fillSz字段获取成交数量
        px = order.get('fillPx')  # 使用fillPx字段获取成交价格
        fill_time = order.get('fillTime')
        fee = order.get('fee')
        fee_ccy = order.get('feeCcy')
        
        # 直接添加所有交易记录，因为/api/v5/trade/fills返回的都是已成交的交易
        actual_trades.append({
            'inst_id': inst_id,
            'side': side,
            'size': sz,
            'price': px,
            'time': fill_time,
            'fee': fee,
            'fee_ccy': fee_ccy
        })
        print(f'  {side.upper()} {sz} {inst_id} @ {px} USDT (手续费: {fee} {fee_ccy})')

# 3. 读取本地数据
print('\n💾 本地系统数据')
local_data_file = 'data/order_agent_state.json'
local_trade_history = []
local_positions = {}

if os.path.exists(local_data_file):
    with open(local_data_file, 'r') as f:
        local_data = json.load(f)
    
    local_trade_history = local_data.get('trade_history', [])
    local_positions = local_data.get('positions', {})
    
    print(f'  本地交易记录: {len(local_trade_history)} 笔')
    print(f'  本地持仓: {local_positions}')
else:
    print('  本地数据文件不存在')
    local_data = {}

# 4. 对比并同步
print('\n🔄 数据对比与同步')

# 显示借币信息
print('\n💸 借币信息')
if actual_liabilities:
    for ccy, liability in actual_liabilities.items():
        print(f'  {ccy}:')
        print(f'    负债: {liability["liab"]:.8f}')
        if liability["interest"] > 0:
            print(f'    未付利息: {liability["interest"]:.8f}')
        if liability["max_loan"] > 0:
            print(f'    最大可借: {liability["max_loan"]:.8f}')
        if liability["cross_liab"] > 0:
            print(f'    全仓负债: {liability["cross_liab"]:.8f}')
        if liability["iso_liab"] > 0:
            print(f'    逐仓负债: {liability["iso_liab"]:.8f}')
else:
    print('  无借币记录')

# 计算交易历史中的BTC持仓
btc_bought = 0.0
btc_sold = 0.0
if orders_data.get('data'):
    for order in orders_data['data']:
        if order.get('instId') == 'BTC-USDT':
            side = order.get('side')
            fill_sz = float(order.get('fillSz', '0') or '0')
            if side == 'buy':
                btc_bought += fill_sz
            elif side == 'sell':
                btc_sold += fill_sz

calculated_btc = btc_bought - btc_sold
print(f'\n📊 交易历史分析')
print(f'  买入BTC: {btc_bought:.8f}')
print(f'  卖出BTC: {btc_sold:.8f}')
print(f'  计算持仓: {calculated_btc:.8f}')

# 确保positions键存在
if 'positions' not in local_data:
    local_data['positions'] = {}

# 对比BTC持仓
# 实际账户BTC余额（包括可用和冻结）
actual_btc_available = actual_balances.get('BTC', {}).get('available', 0)
actual_btc_cash = actual_balances.get('BTC', {}).get('cash', 0)
actual_btc_total = actual_btc_available + actual_btc_cash

# 本地系统BTC余额
local_btc = local_positions.get('BTC', {}).get('available', 0)

# 交易历史计算的BTC持仓
btc_diff = actual_btc_total - local_btc
print(f'  BTC持仓对比:')
print(f'    实际账户(可用): {actual_btc_available:.8f} BTC')
print(f'    实际账户(现金): {actual_btc_cash:.8f} BTC')
print(f'    实际账户(总计): {actual_btc_total:.8f} BTC')
print(f'    交易历史计算: {calculated_btc:.8f} BTC')
print(f'    本地系统: {local_btc:.8f} BTC')
print(f'    差异: {btc_diff:.8f} BTC')

if abs(actual_btc_total - local_btc) > 0.00000001:
    print(f'    ⚠️ 差异较大，需要同步')
    # 更新本地数据
    local_data['positions']['BTC'] = {
        'available': actual_btc_total,
        'total': actual_btc_total,
        'last_sync': datetime.now().isoformat()
    }
    print(f'    ✅ 已更新本地BTC持仓为: {actual_btc_total:.8f}')

# 对比USDT余额
actual_usdt = actual_balances.get('USDT', {}).get('available', 0)
local_usdt = local_positions.get('USDT', {}).get('available', 0)

print(f'\n  USDT余额对比:')
print(f'    实际账户: {actual_usdt:.2f} USDT')
print(f'    本地系统: {local_usdt:.2f} USDT')
print(f'    差异: {actual_usdt - local_usdt:.2f} USDT')

if abs(actual_usdt - local_usdt) > 0.01:
    print(f'    ⚠️ 差异较大，需要同步')
    local_data['positions']['USDT'] = {
        'available': actual_usdt,
        'total': actual_usdt,
        'last_sync': datetime.now().isoformat()
    }
    print(f'    ✅ 已更新本地USDT余额为: {actual_usdt:.2f}')

# 5. 同步交易历史
print(f'\n  交易历史对比:')
print(f'    OKX历史订单: {len(actual_trades)} 笔')
print(f'    本地交易记录: {len(local_trade_history)} 笔')

# 如果本地记录与OKX差异太大，建议重置
if len(local_trade_history) > len(actual_trades) + 5:
    print(f'    ⚠️ 本地记录比OKX多很多，可能存在脏数据')
    print(f'    💡 建议: 重置本地交易历史，从OKX重新同步')

# 6. 保存同步后的数据
print('\n💾 保存同步数据')
with open(local_data_file, 'w') as f:
    json.dump(local_data, f, indent=2)
print(f'  ✅ 数据已保存到: {local_data_file}')

# 7. 同步到OSS
try:
    from core.utils.persistence import persistence_manager
    if persistence_manager.oss_manager:
        persistence_manager.oss_manager.save_to_oss('order_agent_state.json', local_data)
        print(f'  ✅ 数据已同步到OSS')
except Exception as e:
    print(f'  ⚠️ OSS同步失败: {e}')

print('\n' + '=' * 60)
print('同步完成！')
print('=' * 60)
