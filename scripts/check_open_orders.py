#!/usr/bin/env python3
"""
检查OKX实际账户的未平仓订单数量
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
print('检查OKX实际账户未平仓订单')
print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('=' * 60)

# 获取未平仓订单
timestamp = get_timestamp()
headers = get_headers(timestamp, 'GET', '/api/v5/trade/orders-pending?limit=100')
response = requests.get('https://www.okx.com/api/v5/trade/orders-pending?limit=100', headers=headers)
data = response.json()

if data.get('data'):
    open_orders = data['data']
    open_order_count = len(open_orders)
    print(f'未平仓订单数量: {open_order_count}')
    print(f'API响应状态码: {response.status_code}')
    
    if open_orders:
        print('\n未平仓订单详情:')
        for i, order in enumerate(open_orders, 1):
            inst_id = order.get('instId')
            side = order.get('side')
            ord_type = order.get('ordType')
            sz = order.get('sz')
            px = order.get('px')
            state = order.get('state')
            c_time = order.get('cTime')
            print(f'  {i}. {side.upper()} {sz} {inst_id} @ {px} USDT ({state})')
else:
    print('无法获取未平仓订单')
    print(f'API响应: {data}')

# 获取持仓信息
print('\n' + '-' * 40)
print('持仓信息:')
print('-' * 40)

timestamp = get_timestamp()
headers = get_headers(timestamp, 'GET', '/api/v5/account/positions?instType=MARGIN')
response = requests.get('https://www.okx.com/api/v5/account/positions?instType=MARGIN', headers=headers)
positions_data = response.json()

if positions_data.get('data'):
    positions = positions_data['data']
    active_positions = [p for p in positions if float(p.get('pos', '0') or '0') > 0]
    print(f'有效持仓数量: {len(active_positions)}')
    
    if active_positions:
        print('\n持仓详情:')
        for i, position in enumerate(active_positions, 1):
            inst_id = position.get('instId')
            pos = position.get('pos')
            avg_px = position.get('avgPx')
            pos_side = position.get('posSide')
            print(f'  {i}. {inst_id}: {pos} @ {avg_px} USDT ({pos_side})')
    else:
        print('无有效持仓')
else:
    print('无法获取持仓信息')
    print(f'API响应: {positions_data}')

print('\n' + '=' * 60)