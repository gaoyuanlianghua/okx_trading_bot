#!/usr/bin/env python3
"""
启动核互反动力学策略进行交易
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

print("\n" + "=" * 60)
print("启动核互反动力学策略")
print("=" * 60)

# 测试1: 导入环境管理器
print("\n1. 导入环境管理器...")
try:
    from core.config.env_manager import env_manager
    print("✅ 环境管理器导入成功")
    
    # 检查环境
    env_info = env_manager.get_env_info()
    print(f"当前环境: {env_info['current_env']}")
    print(f"模拟盘模式: {env_info['is_test']}")
    
    # 获取API配置
    api_config = env_manager.get_api_config()
    print(f"API Key: {api_config['api_key'][:8]}...")
    
    # 测试2: 导入REST客户端
    print("\n2. 导入REST客户端...")
    from core.api.okx_rest_client import OKXRESTClient
    print("✅ REST客户端导入成功")
    
    # 创建REST客户端
    rest_client = OKXRESTClient(
        api_key=api_config['api_key'],
        api_secret=api_config['api_secret'],
        passphrase=api_config['passphrase'],
        is_test=api_config['is_test']
    )
    print("✅ REST客户端初始化成功")
    
    # 测试3: 测试API连接
    print("\n3. 测试API连接...")
    loop = asyncio.get_event_loop()
    server_time = loop.run_until_complete(rest_client.get_server_time())
    if server_time:
        print(f"✅ 服务器时间获取成功: {server_time}")
    else:
        print("❌ API连接失败")
        sys.exit(1)
    
    # 测试4: 测试行情数据
    print("\n4. 测试行情数据...")
    ticker = loop.run_until_complete(rest_client.get_ticker('BTC-USDT'))
    if ticker:
        print(f"✅ 行情数据获取成功")
        print(f"  BTC-USDT 最新价: {ticker.get('last')} USDT")
    else:
        print("❌ 行情数据获取失败")
        sys.exit(1)
    
    # 测试5: 导入核互反动力学策略
    print("\n5. 导入核互反动力学策略...")
    from strategies.nuclear_dynamics_strategy import NuclearDynamicsStrategy
    print("✅ 核互反动力学策略导入成功")
    
    # 创建策略实例
    strategy_config = {
        'strategy': {
            'name': 'nuclear_dynamics_strategy',
            'symbol': 'BTC-USDT',
            'timeframe': '1m'
        }
    }
    
    strategy = NuclearDynamicsStrategy(
        api_client=rest_client,
        config=strategy_config
    )
    print("✅ 核互反动力学策略初始化成功")
    
    # 启动策略
    strategy.start()
    print("✅ 策略启动成功")
    
    # 测试6: 执行策略
    print("\n6. 执行策略...")
    strategy_data = {
        "market_data": {
            "last": ticker.get('last'),
            "high": ticker.get('high24h'),
            "low": ticker.get('low24h'),
            "volume": ticker.get('vol24h'),
            "timestamp": ticker.get('ts'),
            "inst_id": 'BTC-USDT'
        },
        "order_data": {
            "trade_history": [],
            "pending_orders": []
        }
    }
    
    signal = strategy.execute(strategy_data)
    if signal:
        print("✅ 策略执行成功")
        print(f"策略信号: {signal}")
        if signal.get('side') != 'neutral':
            print(f"📊 信号强度: {signal.get('signal_strength'):.2f}")
            print(f"📈 信号级别: {signal.get('signal_level')}")
            print(f"🎯 信号得分: {signal.get('signal_score')}")
            print(f"💡 方向: {signal.get('side')}")
            print(f"💰 价格: {signal.get('price')}")
        else:
            print("策略信号: 中性 (无交易)")
    else:
        print("❌ 策略执行失败")
        sys.exit(1)
    
    # 停止策略
    strategy.stop()
    print("✅ 策略停止成功")
    
    # 清理REST客户端
    if hasattr(rest_client, 'session') and rest_client.session:
        loop.run_until_complete(rest_client.session.close())
    
    print("\n" + "=" * 60)
    print("🎉 核互反动力学策略交易启动成功！")
    print("=" * 60)
    print("策略已成功启动并执行了一次交易信号分析")
    print("如果需要持续运行策略，请使用 start_nuclear_strategy.py 脚本")
    
    loop.close()
    
except Exception as e:
    print(f"❌ 启动失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
