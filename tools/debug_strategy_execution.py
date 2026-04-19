#!/usr/bin/env python3
"""
调试策略执行流程
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def debug_strategy():
    """调试策略执行"""
    print("\n" + "=" * 60)
    print("调试策略执行流程")
    print("=" * 60)
    
    # 1. 导入环境管理器
    print("\n1. 导入环境管理器...")
    try:
        from core.config.env_manager import env_manager
        env_info = env_manager.get_env_info()
        print(f"  当前环境: {env_info['current_env']}")
        api_config = env_manager.get_api_config()
        print(f"  API Key: {api_config['api_key'][:8]}...")
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 2. 导入和初始化策略
    print("\n2. 导入策略...")
    try:
        from strategies.nuclear_dynamics_strategy import NuclearDynamicsStrategy
        strategy = NuclearDynamicsStrategy()
        print(f"✅ 策略导入成功: {strategy.name}")
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 3. 创建模拟市场数据
    print("\n3. 创建模拟市场数据...")
    try:
        from core import OKXRESTClient
        
        rest_client = OKXRESTClient(
            api_key=api_config['api_key'],
            api_secret=api_config['api_secret'],
            passphrase=api_config['passphrase'],
            is_test=api_config['is_test']
        )
        
        print("✅ REST客户端初始化成功")
        
        # 获取BTC-USDT行情
        print("\n  获取BTC-USDT行情...")
        ticker = await rest_client.get_ticker("BTC-USDT")
        current_price = float(ticker.get("last", 0))
        print(f"  BTC-USDT 最新价: {current_price} USDT")
        
        # 获取ETH-USDT行情
        print("\n  获取ETH-USDT行情...")
        ticker_eth = await rest_client.get_ticker("ETH-USDT")
        current_price_eth = float(ticker_eth.get("last", 0))
        print(f"  ETH-USDT 最新价: {current_price_eth} USDT")
        
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 4. 测试BTC-USDT策略执行
    print("\n4. 测试BTC-USDT策略执行...")
    try:
        strategy_data = {
            "market_data": {
                "inst_id": "BTC-USDT",
                "price": current_price,
                "timestamp": ticker.get("ts", 0),
            },
            "order_data": {},
            "readonly": True
        }
        
        signal = strategy.execute(strategy_data)
        
        if signal:
            print(f"✅ 生成信号:")
            print(f"  方向: {signal.get('direction')}")
            print(f"  信号强度: {signal.get('confidence')}")
            print(f"  信号级别: {signal.get('signal_level')}")
            print(f"  信号得分: {signal.get('score')}")
            print(f"  价格: {signal.get('price')} USDT")
        else:
            print("⚠️  没有生成信号")
            
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 5. 测试ETH-USDT策略执行
    print("\n5. 测试ETH-USDT策略执行...")
    try:
        strategy_data = {
            "market_data": {
                "inst_id": "ETH-USDT",
                "price": current_price_eth,
                "timestamp": ticker_eth.get("ts", 0),
            },
            "order_data": {},
            "readonly": True
        }
        
        signal = strategy.execute(strategy_data)
        
        if signal:
            print(f"✅ 生成信号:")
            print(f"  方向: {signal.get('direction')}")
            print(f"  信号强度: {signal.get('confidence')}")
            print(f"  信号级别: {signal.get('signal_level')}")
            print(f"  信号得分: {signal.get('score')}")
            print(f"  价格: {signal.get('price')} USDT")
        else:
            print("⚠️  没有生成信号")
            
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 清理
    await rest_client.close()
    
    print("\n" + "=" * 60)
    print("✅ 策略执行调试完成！")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        success = loop.run_until_complete(debug_strategy())
        loop.close()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
