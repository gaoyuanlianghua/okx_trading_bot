#!/usr/bin/env python3
"""
测试订单取消功能
"""

import asyncio
import yaml
from core.api.okx_rest_client import OKXRESTClient

async def test_order_cancel():
    # 加载配置
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # 初始化REST客户端
    rest_client = OKXRESTClient(
        api_key=config['api']['api_key'],
        api_secret=config['api']['api_secret'],
        passphrase=config['api']['passphrase']
    )
    
    # 获取当前行情
    ticker = await rest_client.get_ticker('BTC-USDT')
    if not ticker:
        print("获取行情失败，无法挂单")
        return
    
    last_price = float(ticker.get('last', 0))
    if last_price == 0:
        print("获取价格失败，无法挂单")
        return
    
    # 计算挂单价格
    buy_price = last_price * 0.997  # 0.3%的盈利空间
    
    # 最小交易单位
    min_size = "0.00001"
    
    print(f"当前价格: {last_price:.2f} USDT")
    print(f"挂单价格: {buy_price:.2f} USDT")
    
    # 放置买入挂单
    print("开始放置买入挂单...")
    order_id = await rest_client.place_order(
        inst_id='BTC-USDT',
        side='buy',
        ord_type='limit',
        sz=min_size,
        px=str(buy_price),
        td_mode='cross',
        lever='2'
    )
    
    if order_id:
        print(f"已放置买入挂单，订单ID: {order_id}")
        
        # 等待5秒
        print("等待5秒后撤单...")
        await asyncio.sleep(5)
        
        # 撤单
        print(f"开始撤销订单: {order_id}")
        success = await rest_client.cancel_order('BTC-USDT', order_id)
        if success:
            print(f"已成功撤销订单: {order_id}")
        else:
            print(f"撤销订单失败: {order_id}")
    else:
        print("放置挂单失败")

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_order_cancel())
    loop.close()
