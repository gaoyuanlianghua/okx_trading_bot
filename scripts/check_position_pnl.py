#!/usr/bin/env python3
"""
查看OKX API的持仓订单和收益数据
"""

import yaml
import requests
import hmac
import hashlib
import base64
from datetime import datetime, timezone

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

def get_positions():
    """获取持仓信息"""
    timestamp = get_timestamp()
    headers = get_headers(timestamp, 'GET', '/api/v5/account/positions?instType=MARGIN')
    response = requests.get('https://www.okx.com/api/v5/account/positions?instType=MARGIN', headers=headers)
    return response.json()

def get_account_balance():
    """获取账户余额"""
    timestamp = get_timestamp()
    headers = get_headers(timestamp, 'GET', '/api/v5/account/balance')
    response = requests.get('https://www.okx.com/api/v5/account/balance', headers=headers)
    return response.json()

def get_position_pnl():
    """获取持仓收益"""
    timestamp = get_timestamp()
    headers = get_headers(timestamp, 'GET', '/api/v5/account/positions?instType=MARGIN&pnl=true')
    response = requests.get('https://www.okx.com/api/v5/account/positions?instType=MARGIN&pnl=true', headers=headers)
    return response.json()

def get_current_price(inst_id):
    """获取当前价格"""
    timestamp = get_timestamp()
    headers = get_headers(timestamp, 'GET', f'/api/v5/market/ticker?instId={inst_id}')
    response = requests.get(f'https://www.okx.com/api/v5/market/ticker?instId={inst_id}', headers=headers)
    data = response.json()
    if data.get('data'):
        return float(data['data'][0].get('last', '0') or '0')
    return 0

print('=' * 80)
print('查看OKX API的持仓订单和收益数据')
print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('=' * 80)

# 获取持仓信息
print('\n' + '-' * 60)
print('持仓信息:')
print('-' * 60)

positions_data = get_positions()
if positions_data.get('data'):
    positions = positions_data['data']
    active_positions = [p for p in positions if float(p.get('pos', '0') or '0') > 0]
    
    if active_positions:
        for position in active_positions:
            inst_id = position.get('instId')
            pos = position.get('pos')
            avg_px = position.get('avgPx')
            pos_side = position.get('posSide')
            
            # 获取当前价格
            current_price = get_current_price(inst_id)
            
            # 计算收益
            if current_price > 0 and float(avg_px) > 0:
                pos_float = float(pos)
                avg_px_float = float(avg_px)
                pnl = pos_float * (current_price - avg_px_float)
                pnl_rate = (current_price - avg_px_float) / avg_px_float * 100
                
                print(f'{inst_id}:')
                print(f'  持仓数量: {pos}')
                print(f'  平均价格: {avg_px} USDT')
                print(f'  当前价格: {current_price:.2f} USDT')
                print(f'  持仓方向: {pos_side}')
                print(f'  未实现收益: {pnl:.2f} USDT')
                print(f'  收益率: {pnl_rate:.2f}%')
            else:
                print(f'{inst_id}:')
                print(f'  持仓数量: {pos}')
                print(f'  平均价格: {avg_px} USDT')
                print(f'  持仓方向: {pos_side}')
    else:
        print('无有效持仓')
else:
    print('无法获取持仓信息')
    print(f'API响应: {positions_data}')

# 获取持仓收益详细数据
print('\n' + '-' * 60)
print('持仓收益详细数据:')
print('-' * 60)

position_pnl_data = get_position_pnl()
if position_pnl_data.get('data'):
    positions = position_pnl_data['data']
    active_positions = [p for p in positions if float(p.get('pos', '0') or '0') > 0]
    
    if active_positions:
        for position in active_positions:
            inst_id = position.get('instId')
            pos = position.get('pos')
            avg_px = position.get('avgPx')
            pos_side = position.get('posSide')
            upl = position.get('upl', '0')  # 未实现盈亏
            realized_pnl = position.get('realizedPnl', '0')  # 已实现盈亏
            
            print(f'{inst_id}:')
            print(f'  持仓数量: {pos}')
            print(f'  平均价格: {avg_px} USDT')
            print(f'  持仓方向: {pos_side}')
            print(f'  未实现盈亏: {upl} USDT')
            print(f'  已实现盈亏: {realized_pnl} USDT')
    else:
        print('无有效持仓')
else:
    print('无法获取持仓收益数据')
    print(f'API响应: {position_pnl_data}')

# 获取账户余额
print('\n' + '-' * 60)
print('账户余额:')
print('-' * 60)

balance_data = get_account_balance()
if balance_data.get('data'):
    data = balance_data['data'][0]
    total_eq = data.get('totalEq', '0')  # 账户总权益
    avail_eq = data.get('availEq', '0')  # 可用权益
    
    print(f'账户总权益: {total_eq} USDT')
    print(f'可用权益: {avail_eq} USDT')
    
    # 显示各币种余额
    details = data.get('details', [])
    for detail in details:
        ccy = detail.get('ccy')
        avail_bal = detail.get('availBal', '0')
        cash_bal = detail.get('cashBal', '0')
        eq = detail.get('eq', '0')
        
        if float(avail_bal) > 0 or float(cash_bal) > 0:
            print(f'{ccy}:')
            print(f'  可用余额: {avail_bal}')
            print(f'  现金余额: {cash_bal}')
            print(f'  权益: {eq}')
else:
    print('无法获取账户余额')
    print(f'API响应: {balance_data}')

print('\n' + '=' * 80)