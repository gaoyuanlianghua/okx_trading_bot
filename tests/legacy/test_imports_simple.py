#!/usr/bin/env python3
"""
简单测试脚本，逐步测试导入过程
"""

print("开始测试导入...")

# 测试1: 基础导入
print("\n1. 测试基础导入")
try:
    import sys
    import asyncio
    import logging
    print("✅ 基础导入成功")
except Exception as e:
    print(f"❌ 基础导入失败: {e}")
    exit(1)

# 测试2: 环境管理器
print("\n2. 测试环境管理器")
try:
    from core.config.env_manager import env_manager
    print("✅ 环境管理器导入成功")
    env_info = env_manager.get_env_info()
    print(f"  当前环境: {env_info['current_env']}")
    print(f"  模拟盘模式: {env_info['is_test']}")
except Exception as e:
    print(f"❌ 环境管理器导入失败: {e}")
    import traceback
    traceback.print_exc()

# 测试3: REST客户端
print("\n3. 测试REST客户端")
try:
    from core.api.okx_rest_client import OKXRESTClient
    print("✅ REST客户端导入成功")
    # 测试初始化
    api_config = env_manager.get_api_config()
    rest_client = OKXRESTClient(
        api_key=api_config['api_key'],
        api_secret=api_config['api_secret'],
        passphrase=api_config['passphrase'],
        is_test=api_config['is_test']
    )
    print("✅ REST客户端初始化成功")
except Exception as e:
    print(f"❌ REST客户端导入失败: {e}")
    import traceback
    traceback.print_exc()

# 测试4: 核互反动力学策略
print("\n4. 测试核互反动力学策略")
try:
    from strategies.nuclear_dynamics_strategy import NuclearDynamicsStrategy
    print("✅ 核互反动力学策略导入成功")
    # 测试初始化
    strategy_config = {
        'strategy': {
            'name': 'nuclear_dynamics_strategy',
            'symbol': 'BTC-USDT',
            'timeframe': '1m'
        }
    }
    strategy = NuclearDynamicsStrategy(
        api_client=None,
        config=strategy_config
    )
    print("✅ 核互反动力学策略初始化成功")
except Exception as e:
    print(f"❌ 核互反动力学策略导入失败: {e}")
    import traceback
    traceback.print_exc()

print("\n测试完成！")
