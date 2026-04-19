#!/usr/bin/env python3
"""
测试订单参数格式
"""

import asyncio
import yaml
from core.api.okx_rest_client import OKXRESTClient

async def test_order_format():
    """测试订单参数格式"""
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
        print('测试订单参数格式...')
        
        # 测试不同格式的 sz 参数
        test_cases = [
            # (sz, expected_format, description)
            (0.00001, "0.00001", "最小交易单位"),
            (0.000015, "0.00002", "四舍五入到5位小数"),
            (0.0001, "0.00010", "4位小数"),
            (0.001, "0.00100", "3位小数"),
        ]
        
        for sz, expected_format, description in test_cases:
            # 确保数量精度（BTC现货最小单位为0.00001）
            sz_rounded = round(sz, 5)
            # 确保 sz 格式正确，避免科学计数法
            sz_str = "{0:.5f}".format(sz_rounded)
            
            print(f'\n测试 {description}:')
            print(f'原始 sz: {sz}')
            print(f'四舍五入后: {sz_rounded}')
            print(f'格式化后: {sz_str}')
            print(f'预期格式: {expected_format}')
            print(f'格式是否正确: {sz_str == expected_format}')
            
            # 测试下单
            print('测试下单...')
            order_id = await client.place_order(
                inst_id="BTC-USDT",
                side="buy",
                ord_type="limit",
                sz=sz_str,
                px="66772.6",
                td_mode="cash"
            )
            print(f'下单结果: {order_id}')
            
            # 测试获取订单
            if order_id:
                print('测试获取订单...')
                order = await client.get_order_info(inst_id="BTC-USDT", ord_id=order_id)
                print(f'订单信息: {order}')
                
                # 测试撤单
                print('测试撤单...')
                cancel_result = await client.cancel_order(inst_id="BTC-USDT", ord_id=order_id)
                print(f'撤单结果: {cancel_result}')
        
    except Exception as e:
        print(f'测试失败: {e}')
    finally:
        if 'client' in locals():
            await client.close()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_order_format())
