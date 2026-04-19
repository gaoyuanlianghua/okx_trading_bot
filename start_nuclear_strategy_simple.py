#!/usr/bin/env python3
"""
启动核互反动力学策略（简化版）
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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def main():
    """主函数"""
    logger.info("\n" + "=" * 60)
    logger.info("启动核互反动力学策略")
    logger.info("=" * 60)
    
    # 检查环境
    env_info = env_manager.get_env_info()
    if not env_info['is_test']:
        logger.warning("⚠️  注意：当前不是模拟盘环境，将使用实盘交易！")
    else:
        logger.info("✅ 正在使用模拟盘环境")
    
    # 获取API配置
    api_config = env_manager.get_api_config()
    logger.info(f"API Key: {api_config['api_key'][:8]}...")
    logger.info(f"模拟盘模式: {api_config['is_test']}")
    
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
        return
    
    # 测试行情数据
    ticker = await rest_client.get_ticker('BTC-USDT')
    if ticker:
        logger.info(f"✅ 行情数据获取成功")
        logger.info(f"  BTC-USDT 最新价: {ticker.get('last')} USDT")
    else:
        logger.error("❌ 行情数据获取失败")
        return
    
    # 创建策略实例
    logger.info("\n初始化核互反动力学策略...")
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
    logger.info("✅ 策略初始化成功")
    
    # 启动策略
    strategy.start()
    logger.info("✅ 策略启动成功")
    
    # 运行策略
    logger.info("\n" + "=" * 60)
    logger.info("开始运行核互反动力学策略")
    logger.info("=" * 60)
    
    try:
        # 执行一次策略
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
        
        logger.info("执行策略...")
        signal = strategy.execute(strategy_data)
        
        if signal and signal.get('side') != 'neutral':
            logger.info(f"\n策略信号: {signal}")
            logger.info(f"📊 信号强度: {signal.get('signal_strength'):.2f}")
            logger.info(f"📈 信号级别: {signal.get('signal_level')}")
            logger.info(f"🎯 信号得分: {signal.get('signal_score')}")
            logger.info(f"💡 方向: {signal.get('side')}")
            logger.info(f"💰 价格: {signal.get('price')}")
        else:
            logger.info("策略信号: 中性 (无交易)")
        
        logger.info("\n🎉 核互反动力学策略运行成功！")
        
    except Exception as e:
        logger.error(f"运行策略时出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 停止策略
        strategy.stop()
        # 清理REST客户端
        if hasattr(rest_client, 'session') and rest_client.session:
            await rest_client.session.close()
        logger.info("策略已停止")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
