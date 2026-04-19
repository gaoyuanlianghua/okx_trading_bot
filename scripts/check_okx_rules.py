#!/usr/bin/env python3
"""检查OKX交易规则"""

import json
import requests
import hmac
import hashlib
import base64
from datetime import datetime, timezone
import yaml

# 读取配置
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

api_key = config['api']['api_key']
api_secret = config['api']['api_secret']
passphrase = config['api']['passphrase']

# 获取时间戳
timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

# 获取交易产品信息
message = timestamp + 'GET' + '/api/v5/public/instruments?instType=SPOT&instId=BTC-USDT'
mac = hmac.new(api_secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256)
signature = base64.b64encode(mac.digest()).decode('utf-8')

headers = {
    'OK-ACCESS-KEY': api_key,
    'OK-ACCESS-SIGN': signature,
    'OK-ACCESS-TIMESTAMP': timestamp,
    'OK-ACCESS-PASSPHRASE': passphrase,
    'Content-Type': 'application/json'
}

response = requests.get('https://www.okx.com/api/v5/public/instruments?instType=SPOT&instId=BTC-USDT', headers=headers)
print('=== BTC-USDT 交易规则 ===')
data = response.json()
if data.get('data'):
    inst = data['data'][0]
    print(f'最小下单数量 (minSz): {inst.get("minSz")} BTC')
    print(f'数量精度 (lotSz): {inst.get("lotSz")}')
    print(f'最小下单金额 (minOrdAmt): {inst.get("minOrdAmt")} USDT')
    print(f'最大下单数量 (maxSz): {inst.get("maxSz")} BTC')
    print(f'合约乘数 (ctMult): {inst.get("ctMult")}')
    print(f'合约面值 (ctVal): {inst.get("ctVal")}')
    print(f'状态 (state): {inst.get("state")}')
