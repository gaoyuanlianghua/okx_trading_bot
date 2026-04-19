#!/usr/bin/env python3
"""
调试策略激活流程
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

# 配置日志为DEBUG级别
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def debug_strategy_activation():
    """调试策略激活流程"""
    print("\n" + "=" * 60)
    print("调试策略激活流程")
    print("=" * 60)
    
    # 1. 导入必要的模块
    print("\n1. 导入必要的模块...")
    try:
        from core.config.env_manager import env_manager
        from core import (
            EventBus,
            AgentConfig,
            StrategyAgent,
            MarketDataAgent,
            OrderAgent,
            OKXRESTClient
        )
        print("✅ 模块导入成功")
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 2. 获取环境配置
    print("\n2. 获取环境配置...")
    try:
        env_info = env_manager.get_env_info()
        print(f"  当前环境: {env_info['current_env']}")
        
        api_config = env_manager.get_api_config()
        print(f"  API Key: {api_config['api_key'][:8]}...")
    except Exception as e:
        print(f"❌ 环境配置获取失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 3. 创建事件总线
    print("\n3. 创建事件总线...")
    try:
        event_bus = EventBus()
        print("✅ 事件总线创建成功")
    except Exception as e:
        print(f"❌ 事件总线创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 4. 创建REST客户端
    print("\n4. 创建REST客户端...")
    try:
        rest_client = OKXRESTClient(
            api_key=api_config['api_key'],
            api_secret=api_config['api_secret'],
            passphrase=api_config['passphrase'],
            is_test=api_config['is_test']
        )
        print("✅ REST客户端创建成功")
    except Exception as e:
        print(f"❌ REST客户端创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 5. 创建智能体
    print("\n5. 创建智能体...")
    try:
        # 市场数据智能体
        market_config = AgentConfig(name="MarketData", description="市场数据智能体")
        market_data_agent = MarketDataAgent(
            config=market_config,
            rest_client=rest_client
        )
        print("✅ 市场数据智能体创建成功")
        
        # 订单智能体
        order_config = AgentConfig(name="Order", description="订单智能体")
        order_agent = OrderAgent(
            config=order_config,
            exchange_name="okx",
            api_key=api_config['api_key'],
            api_secret=api_config['api_secret'],
            passphrase=api_config['passphrase'],
            is_test=api_config['is_test']
        )
        print("✅ 订单智能体创建成功")
        
        # 策略智能体
        strategy_config = AgentConfig(name="Strategy", description="策略执行智能体")
        strategy_agent = StrategyAgent(
            config=strategy_config,
            market_data_agent=market_data_agent,
            order_agent=order_agent,
            rest_client=rest_client
        )
        print("✅ 策略智能体创建成功")
    except Exception as e:
        print(f"❌ 智能体创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 6. 启动智能体
    print("\n6. 启动智能体...")
    try:
        await market_data_agent.start()
        print("✅ 市场数据智能体启动成功")
        
        # 订阅交易对
        print("  订阅交易对...")
        for inst_id in ['BTC-USDT', 'ETH-USDT']:
            await market_data_agent.subscribe_instrument(inst_id)
        print("  ✅ 交易对订阅完成")
        
        # 查看订阅的交易对
        print(f"  订阅的交易对: {market_data_agent._subscribed_inst_ids}")
        
        # 手动更新REST数据
        print("  更新REST数据...")
        await market_data_agent._update_rest_data()
        print("  ✅ REST数据更新完成")
        
        # 查看缓存状态
        print(f"  Ticker缓存: {list(market_data_agent._ticker_cache.keys())}")
        print(f"  Orderbook缓存: {list(market_data_agent._orderbook_cache.keys())}")
        
        # 测试获取市场数据
        print("  测试获取市场数据...")
        for inst_id in ['BTC-USDT', 'ETH-USDT']:
            ticker = market_data_agent.get_ticker(inst_id)
            print(f"    {inst_id} ticker: {ticker}")
        
        await strategy_agent.start()
        print("✅ 策略智能体启动成功")
    except Exception as e:
        print(f"❌ 智能体启动失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 7. 查看加载的策略
    print("\n7. 查看加载的策略...")
    try:
        print(f"  加载的策略: {list(strategy_agent._strategies.keys())}")
        print(f"  激活的策略: {strategy_agent.get_active_strategies()}")
    except Exception as e:
        print(f"❌ 查看策略失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 8. 激活策略
    print("\n8. 激活NuclearDynamicsStrategy...")
    try:
        result = await strategy_agent.activate_strategy("NuclearDynamicsStrategy")
        print(f"  激活结果: {result}")
        print(f"  激活后的策略: {strategy_agent.get_active_strategies()}")
    except Exception as e:
        print(f"❌ 策略激活失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 9. 等待几秒钟让策略执行
    print("\n9. 等待5秒让策略执行...")
    try:
        await asyncio.sleep(5)
        print("✅ 等待完成")
    except Exception as e:
        print(f"❌ 等待失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 10. 查看信号统计
    print("\n10. 查看信号统计...")
    try:
        signal_stats = strategy_agent.get_signal_stats()
        print(f"  信号统计: {signal_stats}")
        
        recent_signals = strategy_agent.get_signals(limit=10)
        print(f"  最近信号: {recent_signals}")
    except Exception as e:
        print(f"❌ 查看信号统计失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 11. 停止智能体
    print("\n11. 停止智能体...")
    try:
        await strategy_agent.stop()
        print("✅ 智能体停止成功")
    except Exception as e:
        print(f"❌ 智能体停止失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("✅ 策略激活调试完成！")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        success = loop.run_until_complete(debug_strategy_activation())
        loop.close()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"调试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
