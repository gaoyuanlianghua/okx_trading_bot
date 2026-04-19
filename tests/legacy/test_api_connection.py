#!/usr/bin/env python3
"""
测试OKX API连接
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from core.config.env_manager import env_manager
from core import OKXRESTClient


async def test_api_connection():
    """测试API连接"""
    print("测试OKX API连接...")
    
    # 获取API配置
    api_config = env_manager.get_api_config()
    
    # 创建REST客户端
    client = OKXRESTClient(
        api_key=api_config['api_key'],
        api_secret=api_config['api_secret'],
        passphrase=api_config['passphrase'],
        is_test=api_config['is_test']
    )
    
    try:
        # 测试服务器时间
        print("1. 测试服务器时间...")
        server_time = await client.get_server_time()
        print(f"   ✅ 服务器时间: {server_time}")
        
        # 测试行情数据
        print("2. 测试行情数据...")
        ticker = await client.get_ticker('BTC-USDT')
        if ticker:
            print(f"   ✅ BTC-USDT价格: {ticker.get('last')} USDT")
        else:
            print("   ❌ 行情数据获取失败")
        
        # 测试账户余额
        print("3. 测试账户余额...")
        balance = await client.get_account_balance()
        if balance:
            total_eq = balance.get('totalEq', 'N/A')
            print(f"   ✅ 总权益: {total_eq} USDT")
        else:
            print("   ❌ 账户余额获取失败")
        
        # 测试未成交订单
        print("4. 测试未成交订单...")
        try:
            pending_orders = await client.get_pending_orders(inst_id='BTC-USDT')
            if pending_orders is not None:
                print(f"   ✅ 未成交订单数量: {len(pending_orders)}")
            else:
                print("   ⚠️  未成交订单获取结果为None")
        except Exception as e:
            print(f"   ⚠️  获取未成交订单时出错: {e}")
        
        print("\n✅ API连接测试完成")
        
    except Exception as e:
        print(f"\n❌ API测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 关闭客户端
        if hasattr(client, 'session') and client.session:
            await client.session.close()


if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(test_api_connection())
    except Exception as e:
        print(f"运行出错: {e}")
        import traceback
        traceback.print_exc()
