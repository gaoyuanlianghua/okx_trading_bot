#!/usr/bin/env python3
"""
分析OKX账户中19.7789 BTC持仓对应的订单信息
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

def get_trade_history(limit=200, after=None):
    """获取交易历史"""
    timestamp = get_timestamp()
    url = f'/api/v5/trade/fills?limit={limit}'
    if after:
        url += f'&after={after}'
    headers = get_headers(timestamp, 'GET', url)
    response = requests.get(f'https://www.okx.com{url}', headers=headers)
    return response.json()

print('=' * 80)
print('分析19.7789 BTC持仓对应的订单信息')
print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('=' * 80)

# 获取交易历史
trade_history = []
current_after = None

print('获取交易历史记录...')
for i in range(5):  # 获取5页，每页200条，共1000条记录
    print(f'  获取第{i+1}页交易记录...')
    result = get_trade_history(200, current_after)
    if result.get('data'):
        trades = result['data']
        trade_history.extend(trades)
        if trades:
            current_after = trades[-1].get('fillTime')
        else:
            break
    else:
        break

print(f'共获取到 {len(trade_history)} 条交易记录')

# 筛选BTC-USDT交易
btc_trades = [trade for trade in trade_history if trade.get('instId') == 'BTC-USDT']
print(f'BTC-USDT交易记录: {len(btc_trades)} 条')

# 计算累计持仓
print('\n' + '-' * 60)
print('分析BTC持仓变化:')
print('-' * 60)

cumulative_position = 0.0
buy_orders = []
sell_orders = []

for trade in btc_trades:
    side = trade.get('side')
    sz = float(trade.get('fillSz', '0') or '0')
    px = float(trade.get('fillPx', '0') or '0')
    fill_time = trade.get('fillTime')
    ord_id = trade.get('ordId')
    
    if side == 'buy':
        cumulative_position += sz
        buy_orders.append({
            'ord_id': ord_id,
            'time': fill_time,
            'size': sz,
            'price': px,
            'cumulative': cumulative_position
        })
    elif side == 'sell':
        cumulative_position -= sz
        sell_orders.append({
            'ord_id': ord_id,
            'time': fill_time,
            'size': sz,
            'price': px,
            'cumulative': cumulative_position
        })

print(f'最终累计持仓: {cumulative_position:.8f} BTC')
print(f'买入订单数量: {len(buy_orders)}')
print(f'卖出订单数量: {len(sell_orders)}')

# 查找形成19.7789 BTC持仓的主要买入订单
print('\n' + '-' * 60)
print('形成19.7789 BTC持仓的主要买入订单:')
print('-' * 60)

# 按买入时间排序（从早到晚）
buy_orders_sorted = sorted(buy_orders, key=lambda x: x['time'])

# 找出累计持仓接近19.7789的买入订单
print('主要买入订单:')
for i, order in enumerate(buy_orders_sorted[-10:], 1):  # 显示最近的10笔主要买入订单
    print(f'  {i}. 时间: {order["time"]}, 数量: {order["size"]:.8f} BTC, 价格: {order["price"]:.2f} USDT, 累计: {order["cumulative"]:.8f} BTC')

# 分析最近的交易趋势
print('\n' + '-' * 60)
print('最近交易趋势:')
print('-' * 60)

recent_buys = sum(float(order['size']) for order in buy_orders[-20:])
recent_sells = sum(float(order['size']) for order in sell_orders[-20:])

print(f'最近20笔交易:')
print(f'  买入: {recent_buys:.8f} BTC')
print(f'  卖出: {recent_sells:.8f} BTC')
print(f'  净: {(recent_buys - recent_sells):.8f} BTC')

# 获取当前持仓信息
print('\n' + '-' * 60)
print('当前持仓信息:')
print('-' * 60)

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

print('\n' + '=' * 80)