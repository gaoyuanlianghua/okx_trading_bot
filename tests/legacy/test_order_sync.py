#!/usr/bin/env python3
"""
测试订单同步功能
"""

import asyncio
import yaml
from core.api.okx_rest_client import OKXRESTClient

async def test_order_sync():
    # 加载配置
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # 初始化REST客户端
    rest_client = OKXRESTClient(
        api_key=config['api']['api_key'],
        api_secret=config['api']['api_secret'],
        passphrase=config['api']['passphrase']
    )
    
    # 获取现货未成交订单
    spot_pending_orders = await rest_client.get_pending_orders(inst_type="SPOT")
    print('现货未成交订单数量:', len(spot_pending_orders) if spot_pending_orders else 0)
    
    # 获取杠杆未成交订单
    margin_pending_orders = await rest_client.get_pending_orders(inst_type="MARGIN")
    print('杠杆未成交订单数量:', len(margin_pending_orders) if margin_pending_orders else 0)
    
    # 合并未成交订单
    pending_orders = []
    if spot_pending_orders:
        pending_orders.extend(spot_pending_orders)
    if margin_pending_orders:
        pending_orders.extend(margin_pending_orders)
    
    print('总未成交订单数量:', len(pending_orders) if pending_orders else 0)
    
    if pending_orders:
        print('未成交订单:')
        for order in pending_orders:
            print(f"  订单ID: {order.get('ordId')}, 产品: {order.get('instId')}, 方向: {order.get('side')}, 价格: {order.get('px')}, 数量: {order.get('sz')}, 状态: {order.get('state')}")
    else:
        print('当前没有未成交订单')

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_order_sync())
    loop.close()
