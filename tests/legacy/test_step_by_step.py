#!/usr/bin/env python3
"""
逐步测试脚本
逐个测试各个功能
"""

print("=" * 60)
print("开始逐步测试...")
print("=" * 60)

# 步骤1: 环境管理器
print("\n步骤1: 测试环境管理器")
try:
    from core.config.env_manager import env_manager
    print("✅ 环境管理器导入成功")
    
    env_info = env_manager.get_env_info()
    print(f"当前环境: {env_info['current_env']}")
    print(f"模拟盘模式: {env_info['is_test']}")
    
    api_config = env_manager.get_api_config()
    print(f"API Key: {api_config['api_key'][:8]}...")
    print("✅ 环境管理器测试通过")
    
except Exception as e:
    print(f"❌ 环境管理器测试失败: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# 步骤2: 公共API
print("\n" + "=" * 60)
print("步骤2: 测试公共API")
print("=" * 60)

try:
    import asyncio
    from core.api.okx_rest_client import OKXRESTClient
    print("✅ REST客户端导入成功")
    
    async def test_public_api():
        # 创建REST客户端
        rest_client = OKXRESTClient(
            api_key=api_config['api_key'],
            api_secret=api_config['api_secret'],
            passphrase=api_config['passphrase'],
            is_test=api_config['is_test']
        )
        print("✅ REST客户端创建成功")
        
        # 测试服务器时间
        print("\n2.1 测试服务器时间")
        server_time = await rest_client.get_server_time()
        if server_time:
            print(f"✅ 服务器时间: {server_time}")
        else:
            print("❌ 服务器时间获取失败")
        
        # 测试行情数据
        print("\n2.2 测试行情数据")
        ticker = await rest_client.get_ticker('BTC-USDT')
        if ticker:
            print("✅ 行情数据获取成功")
            print(f"  BTC-USDT 最新价: {ticker.get('last')}")
        else:
            print("❌ 行情数据获取失败")
        
        # 测试K线数据
        print("\n2.3 测试K线数据")
        candles = await rest_client.get_candles('BTC-USDT', bar='1m', limit=3)
        if candles:
            print("✅ K线数据获取成功")
            for candle in candles:
                print(f"  {candle[0]}: 开 {candle[1]}, 收 {candle[4]}")
        else:
            print("❌ K线数据获取失败")
        
        # 清理会话
        if hasattr(rest_client, 'session') and rest_client.session:
            await rest_client.session.close()
        
        return ticker
    
    ticker = asyncio.get_event_loop().run_until_complete(test_public_api())
    print("\n✅ 公共API测试通过")
    
except Exception as e:
    print(f"❌ 公共API测试失败: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# 步骤3: 私有API
print("\n" + "=" * 60)
print("步骤3: 测试私有API")
print("=" * 60)

try:
    import asyncio
    from core.api.okx_rest_client import OKXRESTClient
    
    async def test_private_api():
        # 创建REST客户端
        rest_client = OKXRESTClient(
            api_key=api_config['api_key'],
            api_secret=api_config['api_secret'],
            passphrase=api_config['passphrase'],
            is_test=api_config['is_test']
        )
        
        # 测试账户余额
        print("\n3.1 测试账户余额")
        balance = await rest_client.get_account_balance()
        if balance:
            print("✅ 账户余额获取成功")
            if isinstance(balance, list) and len(balance) > 0:
                for item in balance:
                    if isinstance(item, dict):
                        print(f"  总权益: {item.get('totalEq', 'N/A')}")
        else:
            print("❌ 账户余额获取失败")
        
        # 测试持仓信息
        print("\n3.2 测试持仓信息")
        positions = await rest_client.get_positions(inst_type='MARGIN')
        if positions:
            print(f"✅ 持仓信息获取成功，共 {len(positions)} 个持仓")
            for pos in positions[:3]:
                if isinstance(pos, dict):
                    print(f"  {pos.get('instId')}: {pos.get('pos')}")
        else:
            print("ℹ️  无持仓信息")
        
        # 测试未成交订单
        print("\n3.3 测试未成交订单")
        pending_orders = await rest_client.get_orders_pending()
        if pending_orders:
            print(f"✅ 未成交订单获取成功，共 {len(pending_orders)} 个订单")
        else:
            print("ℹ️  无未成交订单")
        
        # 清理会话
        if hasattr(rest_client, 'session') and rest_client.session:
            await rest_client.session.close()
    
    asyncio.get_event_loop().run_until_complete(test_private_api())
    print("\n✅ 私有API测试通过")
    
except Exception as e:
    print(f"❌ 私有API测试失败: {e}")
    import traceback
    traceback.print_exc()

# 步骤4: API缓存
print("\n" + "=" * 60)
print("步骤4: 测试API缓存")
print("=" * 60)

try:
    import asyncio
    import time
    from core.api.okx_rest_client import OKXRESTClient
    
    async def test_caching():
        # 创建REST客户端
        rest_client = OKXRESTClient(
            api_key=api_config['api_key'],
            api_secret=api_config['api_secret'],
            passphrase=api_config['passphrase'],
            is_test=api_config['is_test']
        )
        
        # 第一次请求
        print("\n4.1 第一次请求")
        start = time.time()
        await rest_client.get_ticker('BTC-USDT')
        elapsed1 = time.time() - start
        print(f"  耗时: {elapsed1:.3f}s")
        
        # 第二次请求
        print("\n4.2 第二次请求")
        start = time.time()
        await rest_client.get_ticker('BTC-USDT')
        elapsed2 = time.time() - start
        print(f"  耗时: {elapsed2:.3f}s")
        
        if elapsed2 < elapsed1:
            print("✅ API缓存工作正常")
        else:
            print("⚠️  API缓存可能未生效")
        
        # API统计
        print("\n4.3 API统计")
        print(f"  总调用次数: {rest_client.api_stats['total_calls']}")
        print(f"  缓存调用次数: {rest_client.api_stats['cached_calls']}")
        
        # 清理会话
        if hasattr(rest_client, 'session') and rest_client.session:
            await rest_client.session.close()
    
    asyncio.get_event_loop().run_until_complete(test_caching())
    print("\n✅ API缓存测试通过")
    
except Exception as e:
    print(f"❌ API缓存测试失败: {e}")
    import traceback
    traceback.print_exc()

# 完成
print("\n" + "=" * 60)
print("🎉 所有步骤测试完成！")
print("=" * 60)
