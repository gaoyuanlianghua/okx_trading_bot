#!/usr/bin/env python3
"""
测试订单超时自动撤销功能
"""

import asyncio
import yaml
from core.api.okx_rest_client import OKXRESTClient

async def test_order_timeout():
    """测试订单超时自动撤销功能"""
    try:
        # 加载配置
        with open('config/config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        api_config = config['api']
        
        # 初始化客户端
        client = OKXRESTClient(
            api_key=api_config['api_key'],
            api_secret=api_config['api_secret'],
            passphrase=api_config['passphrase'],
            is_test=api_config['is_test']
        )
        
        print('API 客户端初始化完成')
        print('测试订单超时自动撤销功能...')
        
        # 获取当前价格
        ticker = await client.get_ticker("BTC-USDT")
        current_price = float(ticker.get("last", "66758.2"))
        print(f'当前 BTC-USDT 价格: {current_price}')
        
        # 下单（使用远离当前价格的限价单，确保不会立即成交）
        # 买单：价格低于当前价格1000 USDT
        buy_price = current_price - 1000
        print(f'\n下买单，价格: {buy_price} (低于当前价格1000 USDT)')
        
        order_id = await client.place_order(
            inst_id="BTC-USDT",
            side="buy",
            ord_type="limit",
            sz="0.00001",
            px=str(buy_price),
            td_mode="cash"
        )
        
        print(f'下单结果: {order_id}')
        
        if order_id:
            # 检查订单状态
            order = await client.get_order_info(inst_id="BTC-USDT", ord_id=order_id)
            print(f'订单状态: {order.get("state")}')
            
            # 等待65秒，让订单超时
            print('\n等待65秒，让订单超时...')
            await asyncio.sleep(65)
            
            # 再次检查订单状态
            order = await client.get_order_info(inst_id="BTC-USDT", ord_id=order_id)
            print(f'65秒后订单状态: {order.get("state")}')
            
            if order.get("state") == "canceled":
                print('✅ 测试成功：订单已自动撤销')
            else:
                print('❌ 测试失败：订单未自动撤销')
                # 手动撤销订单
                cancel_result = await client.cancel_order(inst_id="BTC-USDT", ord_id=order_id)
                print(f'手动撤单结果: {cancel_result}')
        
    except Exception as e:
        print(f'测试失败: {e}')
    finally:
        if 'client' in locals():
            await client.close()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_order_timeout())
