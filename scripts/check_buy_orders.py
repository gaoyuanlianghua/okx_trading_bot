#!/usr/bin/env python3
"""
检查OKX实际账户的买入订单数量
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

print('=' * 60)
print('检查OKX实际账户买入订单')
print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('=' * 60)

# 获取交易记录
timestamp = get_timestamp()
headers = get_headers(timestamp, 'GET', '/api/v5/trade/fills?limit=100')
response = requests.get('https://www.okx.com/api/v5/trade/fills?limit=100', headers=headers)
data = response.json()

if data.get('data'):
    all_orders = data['data']
    buy_orders = [order for order in all_orders if order.get('side') == 'buy']
    sell_orders = [order for order in all_orders if order.get('side') == 'sell']
    
    print(f'总交易记录数量: {len(all_orders)}')
    print(f'买入订单数量: {len(buy_orders)}')
    print(f'卖出订单数量: {len(sell_orders)}')
    print(f'API响应状态码: {response.status_code}')
    
    # 计算买入和卖出的BTC数量
    total_buy = 0.0
    total_sell = 0.0
    
    for order in all_orders:
        if order.get('instId') == 'BTC-USDT':
            side = order.get('side')
            sz = float(order.get('fillSz', '0') or '0')
            if side == 'buy':
                total_buy += sz
            elif side == 'sell':
                total_sell += sz
    
    net_position = total_buy - total_sell
    print(f'\nBTC交易统计:')
    print(f'  买入总量: {total_buy:.8f} BTC')
    print(f'  卖出总量: {total_sell:.8f} BTC')
    print(f'  净持仓: {net_position:.8f} BTC')
    
    # 显示最近的买入订单
    if buy_orders:
        print('\n最近5笔买入订单:')
        for i, order in enumerate(buy_orders[:5], 1):
            inst_id = order.get('instId')
            sz = order.get('fillSz')
            px = order.get('fillPx')
            fill_time = order.get('fillTime')
            print(f'  {i}. 买入 {sz} {inst_id} @ {px} USDT')
    else:
        print('\n无买入订单')
else:
    print('无法获取交易记录')
    print(f'API响应: {data}')

# 获取持仓信息
print('\n' + '-' * 40)
print('当前持仓信息:')
print('-' * 40)

timestamp = get_timestamp()
headers = get_headers(timestamp, 'GET', '/api/v5/account/positions?instType=MARGIN')
response = requests.get('https://www.okx.com/api/v5/account/positions?instType=MARGIN', headers=headers)
positions_data = response.json()

if positions_data.get('data'):
    positions = positions_data['data']
    active_positions = [p for p in positions if float(p.get('pos', '0') or '0') > 0]
    
    if active_positions:
        for position in active_positions:
            inst_id = position.get('instId')
            pos = position.get('pos')
            avg_px = position.get('avgPx')
            pos_side = position.get('posSide')
            print(f'{inst_id}: {pos} @ {avg_px} USDT ({pos_side})')
    else:
        print('无有效持仓')
else:
    print('无法获取持仓信息')

print('\n' + '=' * 60)