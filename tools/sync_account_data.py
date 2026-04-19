#!/usr/bin/env python3
"""
同步OKX账户数据
解决持仓数量与实际余额不匹配的问题
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

# 获取账户余额
timestamp = get_timestamp()
headers = get_headers(timestamp, 'GET', '/api/v5/account/balance')
response = requests.get('https://www.okx.com/api/v5/account/balance', headers=headers)
balance_data = response.json()

print('=== 账户余额 ===')
if balance_data.get('data'):
    for detail in balance_data['data'][0].get('details', []):
        ccy = detail.get('ccy')
        avail_bal = float(detail.get('availBal', 0))
        cash_bal = float(detail.get('cashBal', 0))
        eq = float(detail.get('eq', 0))
        
        if avail_bal > 0 or cash_bal > 0:
            print(f'{ccy}:')
            print(f'  可用余额: {avail_bal}')
            print(f'  现金余额: {cash_bal}')
            print(f'  资产估值: {eq}')

# 获取持仓信息
timestamp = get_timestamp()
headers = get_headers(timestamp, 'GET', '/api/v5/account/positions')
response = requests.get('https://www.okx.com/api/v5/account/positions', headers=headers)
positions_data = response.json()

print('\n=== 持仓信息 ===')
if positions_data.get('data'):
    for pos in positions_data['data']:
        inst_id = pos.get('instId')
        pos_side = pos.get('posSide')
        pos_val = float(pos.get('pos', 0))
        if pos_val != 0:
            print(f'{inst_id} ({pos_side}): {pos_val}')
else:
    print('无持仓')

# 获取未成交订单
timestamp = get_timestamp()
headers = get_headers(timestamp, 'GET', '/api/v5/trade/orders-pending')
response = requests.get('https://www.okx.com/api/v5/trade/orders-pending', headers=headers)
orders_data = response.json()

print('\n=== 未成交订单 ===')
if orders_data.get('data'):
    for order in orders_data['data']:
        print(f"订单 {order.get('ordId')}: {order.get('instId')} {order.get('side')} {order.get('sz')} @ {order.get('px')}")
else:
    print('无未成交订单')

# 同步到本地数据文件
print('\n=== 同步到本地数据 ===')

# 读取现有的order_agent_state.json
data_file = 'data/order_agent_state.json'
if os.path.exists(data_file):
    with open(data_file, 'r') as f:
        local_data = json.load(f)
    
    # 获取实际的BTC余额
    btc_avail = 0
    for detail in balance_data['data'][0].get('details', []):
        if detail.get('ccy') == 'BTC':
            btc_avail = float(detail.get('availBal', 0))
            break
    
    # 更新持仓数据
    if 'positions' not in local_data:
        local_data['positions'] = {}
    
    local_data['positions']['BTC'] = {
        'available': btc_avail,
        'total': btc_avail,
        'last_sync': datetime.now().isoformat()
    }
    
    # 保存更新后的数据
    with open(data_file, 'w') as f:
        json.dump(local_data, f, indent=2)
    
    print(f'✅ 已更新持仓数据: BTC = {btc_avail}')
else:
    print('⚠️ 本地数据文件不存在')
