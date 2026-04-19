#!/usr/bin/env python3
"""
正式的策略启动脚本
使用策略运行器启动和管理交易策略
"""

import asyncio
import logging
import sys
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

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

# 策略映射
STRATEGIES = {
    'nuclear_dynamics': 'NuclearDynamicsStrategy',
    'dynamics': 'DynamicsStrategy',
    'ma_rsi': 'MARsiStrategy',
    'macd_bollinger': 'MacdBollingerStrategy',
    'arbitrage': 'ArbitrageStrategy',
    'cross_market_arbitrage': 'CrossMarketArbitrageStrategy',
    'machine_learning': 'MachineLearningStrategy',
    'combined': 'CombinedStrategy',
}

def get_strategy_class(strategy_name):
    """获取策略类"""
    module_map = {
        'nuclear_dynamics': 'strategies.nuclear_dynamics_strategy',
        'dynamics': 'strategies.dynamics_strategy',
        'ma_rsi': 'strategies.ma_rsi_strategy',
        'macd_bollinger': 'strategies.macd_bollinger_strategy',
        'arbitrage': 'strategies.arbitrage_strategy',
        'cross_market_arbitrage': 'strategies.cross_market_arbitrage_strategy',
        'machine_learning': 'strategies.machine_learning_strategy',
        'combined': 'strategies.combined_strategy',
    }
    
    if strategy_name not in module_map:
        raise ValueError(f"未知的策略: {strategy_name}")
    
    module_name = module_map[strategy_name]
    class_name = STRATEGIES[strategy_name]
    
    module = __import__(module_name, fromlist=[class_name])
    return getattr(module, class_name)

async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='启动交易策略')
    parser.add_argument(
        '--strategy',
        type=str,
        default='nuclear_dynamics',
        choices=list(STRATEGIES.keys()),
        help='要使用的策略名称'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='策略执行间隔（秒）'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='只执行一次策略'
    )
    parser.add_argument(
        '--symbol',
        type=str,
        default='BTC-USDT',
        help='交易对'
    )
    parser.add_argument(
        '--timeframe',
        type=str,
        default='1m',
        help='时间周期'
    )
    
    args = parser.parse_args()
    
    # 导入策略运行器
    from core.trading.strategy_runner import StrategyRunner
    
    # 获取策略类
    try:
        strategy_class = get_strategy_class(args.strategy)
    except Exception as e:
        logger.error(f"获取策略类失败: {e}")
        return
    
    # 创建策略配置
    strategy_config = {
        'strategy': {
            'name': args.strategy,
            'symbol': args.symbol,
            'timeframe': args.timeframe
        }
    }
    
    # 创建策略运行器
    runner = StrategyRunner()
    
    try:
        # 设置策略
        await runner.setup(strategy_class, strategy_config)
        
        if args.once:
            # 只执行一次
            logger.info(f"执行一次策略: {args.strategy}")
            signal = await runner.execute_once()
            
            if signal and signal.get('side') != 'neutral':
                logger.info(f"策略信号: {signal}")
            else:
                logger.info("无交易信号")
            
            # 停止策略
            await runner.stop()
        else:
            # 持续运行策略
            logger.info(f"持续运行策略: {args.strategy} (间隔: {args.interval}秒)")
            await runner.run_continuous(interval=args.interval)
            
    except Exception as e:
        logger.error(f"启动策略失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if runner.is_running:
            await runner.stop()


if __name__ == "__main__":
    # 运行主函数
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
        loop.close()
    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.error(f"程序异常: {e}")
        import traceback
        traceback.print_exc()
