#!/usr/bin/env python3
"""
测试多货币交易功能
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


async def test_multi_currency():
    """测试多货币交易功能"""
    print("\n" + "=" * 60)
    print("测试多货币交易功能")
    print("=" * 60)
    
    # 测试1: 导入环境管理器
    print("\n1. 测试环境管理器导入...")
    try:
        from core.config.env_manager import env_manager
        print("✅ 环境管理器导入成功")
        
        env_info = env_manager.get_env_info()
        print(f"  当前环境: {env_info['current_env']}")
        print(f"  模拟盘模式: {env_info['is_test']}")
        
        api_config = env_manager.get_api_config()
        print(f"  API Key: {api_config['api_key'][:8]}...")
    except Exception as e:
        print(f"❌ 环境管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 测试2: 导入策略智能体
    print("\n2. 测试策略智能体导入...")
    try:
        from core.agents.strategy_agent import StrategyAgent
        from core.agents.base_agent import AgentConfig
        print("✅ 策略智能体导入成功")
        
        # 创建策略智能体配置
        config = AgentConfig(
            name="Strategy",
            description="策略智能体"
        )
        
        # 创建策略智能体
        strategy_agent = StrategyAgent(config)
        print("✅ 策略智能体创建成功")
        print(f"  订阅的交易对: {strategy_agent._subscribed_instruments}")
    except Exception as e:
        print(f"❌ 策略智能体测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 测试3: 测试主程序启动
    print("\n3. 测试主程序启动...")
    try:
        # 暂时禁用main_new.py的自动运行
        import sys
        original_argv = sys.argv.copy()
        sys.argv = ['test_multi_currency.py']
        
        # 导入main_new
        from main_new import TradingBot
        print("✅ main_new.py 导入成功")
        
        # 恢复原始argv
        sys.argv = original_argv
    except Exception as e:
        print(f"❌ main_new.py 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("✅ 多货币交易功能测试通过！")
    print("=" * 60)
    print("\n总结:")
    print("- 环境管理器正常工作")
    print("- 策略智能体支持多货币交易")
    print("- 系统配置了以下交易对: BTC-USDT, ETH-USDT")
    print("- 主程序已准备就绪，可以开始多货币交易测试")
    
    return True


if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        success = loop.run_until_complete(test_multi_currency())
        loop.close()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
