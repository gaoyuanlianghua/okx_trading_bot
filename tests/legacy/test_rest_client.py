#!/usr/bin/env python3
"""简单的REST客户端测试"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))


async def test_rest_client():
    """测试REST客户端"""
    print("=" * 60)
    print("测试REST客户端")
    print("=" * 60)
    
    # 1. 导入必要的模块
    print("\n1. 导入必要的模块...")
    try:
        from core.config.env_manager import env_manager
        from core import OKXRESTClient
        print("✅ 模块导入成功")
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 获取环境配置
    env_info = env_manager.get_env_info()
    api_config = env_manager.get_api_config()
    
    print(f"\n当前环境: {env_info['current_env']}")
    print(f"API Key: {api_config['api_key'][:8]}...")
    
    # 创建REST客户端
    print("\n创建REST客户端...")
    rest_client = OKXRESTClient(
        api_key=api_config['api_key'],
        api_secret=api_config['api_secret'],
        passphrase=api_config['passphrase'],
        is_test=api_config['is_test']
    )
    print("✅ REST客户端创建成功")
    
    # 测试获取ticker
    print("\n测试获取BTC-USDT的ticker...")
    try:
        ticker = await rest_client.get_ticker('BTC-USDT')
        if ticker:
            print(f"✅ 获取ticker成功:")
            print(f"   交易对: {ticker.get('instId')}")
            print(f"   最新价格: {ticker.get('last')}")
            print(f"   24h最高: {ticker.get('high24h')}")
            print(f"   24h最低: {ticker.get('low24h')}")
            print(f"   24h成交量: {ticker.get('vol24h')}")
        else:
            print("❌ 获取ticker失败: 返回None")
    except Exception as e:
        print(f"❌ 获取ticker失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试获取ETH-USDT的ticker
    print("\n测试获取ETH-USDT的ticker...")
    try:
        ticker = await rest_client.get_ticker('ETH-USDT')
        if ticker:
            print(f"✅ 获取ticker成功:")
            print(f"   交易对: {ticker.get('instId')}")
            print(f"   最新价格: {ticker.get('last')}")
        else:
            print("❌ 获取ticker失败: 返回None")
    except Exception as e:
        print(f"❌ 获取ticker失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(test_rest_client())
    finally:
        loop.close()
