#!/usr/bin/env python3
"""
测试核互反动力学策略
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from core.config.env_manager import env_manager
from core.api.okx_rest_client import OKXRESTClient
from strategies.nuclear_dynamics_strategy import NuclearDynamicsStrategy

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_nuclear_strategy():
    """测试核互反动力学策略"""
    logger.info("\n" + "=" * 60)
    logger.info("测试核互反动力学策略")
    logger.info("=" * 60)
    
    # 检查环境
    env_info = env_manager.get_env_info()
    logger.info(f"当前环境: {env_info['current_env']}")
    logger.info(f"模拟盘模式: {env_info['is_test']}")
    
    # 获取API配置
    api_config = env_manager.get_api_config()
    logger.info(f"API Key: {api_config['api_key'][:8]}...")
    
    # 创建REST客户端
    rest_client = OKXRESTClient(
        api_key=api_config['api_key'],
        api_secret=api_config['api_secret'],
        passphrase=api_config['passphrase'],
        is_test=api_config['is_test']
    )
    
    # 测试API连接
    logger.info("\n测试API连接...")
    server_time = await rest_client.get_server_time()
    if server_time:
        logger.info(f"✅ 服务器时间获取成功: {server_time}")
    else:
        logger.error("❌ API连接失败")
        return False
    
    # 测试行情数据
    ticker = await rest_client.get_ticker('BTC-USDT')
    if ticker:
        logger.info(f"✅ 行情数据获取成功")
        logger.info(f"  BTC-USDT 最新价: {ticker.get('last')} USDT")
    else:
        logger.error("❌ 行情数据获取失败")
        return False
    
    # 创建策略实例
    logger.info("\n初始化核互反动力学策略...")
    strategy_config = {
        'strategy': {
            'name': 'nuclear_dynamics_strategy',
            'symbol': 'BTC-USDT',
            'timeframe': '1m'
        }
    }
    
    try:
        strategy = NuclearDynamicsStrategy(
            api_client=rest_client,
            config=strategy_config
        )
        logger.info("✅ 策略初始化成功")
        
        # 启动策略
        strategy.start()
        logger.info("✅ 策略启动成功")
        
        # 测试策略执行
        logger.info("\n测试策略执行...")
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
            logger.info("✅ 策略执行成功")
            logger.info(f"策略信号: {signal}")
        else:
            logger.error("❌ 策略执行失败")
            return False
        
        # 停止策略
        strategy.stop()
        logger.info("✅ 策略停止成功")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 策略测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理REST客户端
        if hasattr(rest_client, 'session') and rest_client.session:
            await rest_client.session.close()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    success = loop.run_until_complete(test_nuclear_strategy())
    loop.close()
    
    if success:
        logger.info("\n🎉 核互反动力学策略测试通过！")
    else:
        logger.error("\n❌ 核互反动力学策略测试失败！")
