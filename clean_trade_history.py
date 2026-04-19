#!/usr/bin/env python3
"""
清理本地交易历史中的脏数据，只保留API返回的有效交易记录
"""

import json
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

def get_valid_trades():
    """从API获取有效交易记录"""
    timestamp = get_timestamp()
    headers = get_headers(timestamp, 'GET', '/api/v5/trade/fills?limit=100')
    response = requests.get('https://www.okx.com/api/v5/trade/fills?limit=100', headers=headers)
    data = response.json()
    
    if data.get('data'):
        return data['data']
    return []

def clean_trade_history():
    """清理本地交易历史"""
    local_data_file = 'data/order_agent_state.json'
    
    # 读取本地数据
    try:
        with open(local_data_file, 'r') as f:
            local_data = json.load(f)
    except Exception as e:
        print(f"读取本地数据失败: {e}")
        return
    
    # 从API获取有效交易记录
    valid_trades = get_valid_trades()
    print(f"从API获取到 {len(valid_trades)} 条有效交易记录")
    
    if not valid_trades:
        print("未获取到有效交易记录，跳过清理")
        return
    
    # 提取有效交易的订单ID
    valid_order_ids = set()
    for trade in valid_trades:
        order_id = trade.get('ordId')
        if order_id:
            valid_order_ids.add(order_id)
    
    print(f"有效订单ID数量: {len(valid_order_ids)}")
    
    # 清理本地交易历史
    original_trade_count = len(local_data.get('trade_history', []))
    
    # 只保留API返回的有效交易记录
    cleaned_trades = []
    for trade in local_data.get('trade_history', []):
        trade_id = trade.get('trade_id')
        if trade_id in valid_order_ids:
            cleaned_trades.append(trade)
    
    # 也可以直接使用API返回的交易记录
    api_trades = []
    for trade in valid_trades:
        api_trade = {
            "trade_id": trade.get('ordId'),
            "inst_id": trade.get('instId'),
            "side": trade.get('side'),
            "ord_type": trade.get('ordType', 'market'),
            "price": float(trade.get('fillPx', '0') or '0'),
            "size": float(trade.get('sz', '0') or '0'),
            "filled_size": float(trade.get('fillSz', '0') or '0'),
            "fee": float(trade.get('fee', '0') or '0'),
            "state": "filled",
            "timestamp": trade.get('fillTime'),
            "fill_time": trade.get('fillTime'),
            "td_mode": trade.get('tdMode', 'cross'),
            "source": "API"
        }
        api_trades.append(api_trade)
    
    # 替换为API返回的交易记录
    local_data['trade_history'] = api_trades
    
    cleaned_count = len(local_data['trade_history'])
    removed_count = original_trade_count - cleaned_count
    
    print(f"清理前交易记录数量: {original_trade_count}")
    print(f"清理后交易记录数量: {cleaned_count}")
    print(f"移除脏数据数量: {removed_count}")
    
    # 保存清理后的数据
    try:
        with open(local_data_file, 'w') as f:
            json.dump(local_data, f, indent=2)
        print(f"✅ 清理完成，数据已保存到: {local_data_file}")
    except Exception as e:
        print(f"保存数据失败: {e}")

def setup_cron_job():
    """设置定期同步任务"""
    cron_content = """
# 每30分钟运行一次账户同步
*/30 * * * * cd /root/okx_trading_bot && python3 full_sync_account.py >> /root/okx_trading_bot/logs/sync_cron.log 2>&1

# 每天凌晨2点清理交易历史
0 2 * * * cd /root/okx_trading_bot && python3 clean_trade_history.py >> /root/okx_trading_bot/logs/clean_cron.log 2>&1
"""
    
    try:
        with open('sync_cron.txt', 'w') as f:
            f.write(cron_content)
        print("✅ 定时任务配置已生成: sync_cron.txt")
        print("请使用以下命令添加到crontab:")
        print("crontab sync_cron.txt")
    except Exception as e:
        print(f"生成定时任务配置失败: {e}")

if __name__ == "__main__":
    print('=' * 60)
    print('清理本地交易历史中的脏数据')
    print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 60)
    
    clean_trade_history()
    
    print('\n' + '=' * 60)
    print('设置定期同步任务')
    print('=' * 60)
    setup_cron_job()
    
    print('\n' + '=' * 60)
    print('操作完成！')
    print('=' * 60)