#!/usr/bin/env python3
"""
检查OKX API返回的持仓详细信息
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

print('=' * 80)
print('检查OKX API持仓详细信息')
print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('=' * 80)

# 获取原始持仓数据
positions_data = get_positions()
print('\n原始API响应:')
print('-' * 60)
print(positions_data)

print('\n' + '-' * 60)
print('详细分析:')
print('-' * 60)

if positions_data.get('data'):
    for position in positions_data['data']:
        print(f'\n交易对: {position.get("instId")}')
        print(f'持仓数量: {position.get("pos")}')
        print(f'持仓方向: {position.get("posSide")}')
        print(f'平均价格: {position.get("avgPx")}')
        print(f'未实现盈亏: {position.get("upl")}')
        print(f'已实现盈亏: {position.get("realizedPnl")}')
        print(f'杠杆倍数: {position.get("lever")}')
        print(f'保证金: {position.get("margin")}')
        print(f'维持保证金: {position.get("maintMargin")}')
        print(f'强平价格: {position.get("liqPx")}')
        print(f'标记价格: {position.get("markPx")}')
        print(f'当前价格: {position.get("last")}')
        
        # 计算价值
        pos = float(position.get('pos', '0') or '0')
        avg_px = float(position.get('avgPx', '0') or '0')
        last = float(position.get('last', '0') or '0')
        
        if pos > 0 and avg_px > 0:
            cost = pos * avg_px
            value = pos * last if last > 0 else cost
            pnl = value - cost
            print(f'\n计算结果:')
            print(f'持仓成本: {cost:.2f} USDT')
            print(f'持仓价值: {value:.2f} USDT')
            print(f'未实现收益: {pnl:.2f} USDT')
            print(f'收益率: {(pnl/cost*100):.2f}%')

print('\n' + '=' * 80)
print('分析完成！')
print('=' * 80)