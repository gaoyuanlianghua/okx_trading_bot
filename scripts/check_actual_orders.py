#!/usr/bin/env python3
"""
检查OKX实际账户的订单数量
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
print('检查OKX实际账户订单数量')
print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('=' * 60)

# 获取交易记录
timestamp = get_timestamp()
headers = get_headers(timestamp, 'GET', '/api/v5/trade/fills?limit=100')
response = requests.get('https://www.okx.com/api/v5/trade/fills?limit=100', headers=headers)
data = response.json()

if data.get('data'):
    order_count = len(data['data'])
    print(f'实际账户交易记录数量: {order_count}')
    print(f'API响应状态码: {response.status_code}')
    
    # 显示前5笔交易
    print('\n最近5笔交易:')
    for i, order in enumerate(data['data'][:5], 1):
        inst_id = order.get('instId')
        side = order.get('side')
        sz = order.get('fillSz')
        px = order.get('fillPx')
        fill_time = order.get('fillTime')
        print(f'  {i}. {side.upper()} {sz} {inst_id} @ {px} USDT')
else:
    print('无法获取交易记录')
    print(f'API响应: {data}')

print('\n' + '=' * 60)