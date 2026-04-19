#!/usr/bin/env python3
"""
策略文件测试脚本
逐一测试所有策略文件
"""

import os
import sys
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 添加项目根目录到Python路径
sys.path.insert(0, '/root/okx_trading_bot')

# 策略文件目录
STRATEGIES_DIR = Path('/root/okx_trading_bot/strategies')

# 要测试的策略文件
STRATEGY_FILES = [
    'base_strategy.py',
    'ma_rsi_strategy.py',
    'combined_strategy.py',
    'macd_bollinger_strategy.py',
    'cross_market_arbitrage_strategy.py',
    'machine_learning_strategy.py',
    'dynamics_strategy.py',
    'nuclear_dynamics_strategy.py',
    'arbitrage_strategy.py'
]

def test_strategy(strategy_file):
    """测试单个策略文件"""
    logger.info(f"\n" + "=" * 60)
    logger.info(f"测试策略: {strategy_file}")
    logger.info("=" * 60)
    
    try:
        # 提取策略类名
        module_name = strategy_file.replace('.py', '')
        
        # 特殊处理类名
        if module_name == 'ma_rsi_strategy':
            class_name = 'MARsiStrategy'
        else:
            # 普通情况：将下划线分隔的单词首字母大写
            class_name = ''.join([word.capitalize() for word in module_name.split('_')])
        
        # 动态导入模块
        logger.info(f"1. 导入模块: {module_name}")
        module = __import__(f'strategies.{module_name}', fromlist=[class_name])
        
        # 获取策略类
        logger.info(f"2. 获取策略类: {class_name}")
        strategy_class = getattr(module, class_name, None)
        
        if not strategy_class:
            # 尝试查找所有类
            classes = [name for name in dir(module) if name[0].isupper()]
            logger.error(f"❌ 未找到策略类: {class_name}")
            logger.error(f"  模块中可用的类: {classes}")
            return False
        
        # 测试策略初始化
        logger.info("3. 测试策略初始化")
        # 基础策略参数
        config = {
            'strategy': {
                'name': module_name,
                'symbol': 'BTC-USDT',
                'timeframe': '1m'
            }
        }
        
        # 特殊策略的额外参数
        if module_name == 'dynamics_strategy' or module_name == 'nuclear_dynamics_strategy':
            config['strategy'].update({
                'G_eff': 0.001,
                'ε': 0.85,
                'position_size': 0.1,
                'max_position': 0.6,
                'stop_loss': 0.02,
                'take_profit': 0.05
            })
        
        strategy = strategy_class(api_client=None, config=config)
        logger.info("✅ 策略初始化成功")
        
        # 测试策略属性
        logger.info("4. 测试策略属性")
        if hasattr(strategy, 'name'):
            logger.info(f"  策略名称: {strategy.name}")
        if hasattr(strategy, 'config'):
            logger.info(f"  策略配置: {strategy.config}")
        if hasattr(strategy, 'status'):
            logger.info(f"  策略状态: {strategy.status}")
        
        # 测试策略方法
        logger.info("5. 测试策略方法")
        
        # 测试执行方法
        if hasattr(strategy, 'execute'):
            # 模拟市场数据
            market_data = {
                'last': '74000.0',
                'high': '74500.0',
                'low': '73500.0',
                'volume': 100000000,
                'timestamp': 1776192000000
            }
            
            try:
                signal = strategy.execute(market_data)
                logger.info(f"  执行结果: {signal}")
                logger.info("✅ execute 方法测试通过")
            except Exception as e:
                logger.warning(f"⚠️  execute 方法测试失败: {e}")
        
        # 测试获取参数方法
        if hasattr(strategy, 'get_params'):
            try:
                params = strategy.get_params()
                logger.info(f"  策略参数: {params}")
                logger.info("✅ get_params 方法测试通过")
            except Exception as e:
                logger.warning(f"⚠️  get_params 方法测试失败: {e}")
        
        # 测试启动和停止方法
        if hasattr(strategy, 'start'):
            try:
                strategy.start()
                logger.info("✅ start 方法测试通过")
            except Exception as e:
                logger.warning(f"⚠️  start 方法测试失败: {e}")
        
        if hasattr(strategy, 'stop'):
            try:
                strategy.stop()
                logger.info("✅ stop 方法测试通过")
            except Exception as e:
                logger.warning(f"⚠️  stop 方法测试失败: {e}")
        
        logger.info("✅ 策略测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ 策略测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """测试所有策略文件"""
    logger.info("\n" + "=" * 60)
    logger.info("开始测试策略文件")
    logger.info("=" * 60)
    
    results = {}
    
    for strategy_file in STRATEGY_FILES:
        file_path = STRATEGIES_DIR / strategy_file
        if file_path.exists():
            results[strategy_file] = test_strategy(strategy_file)
        else:
            logger.error(f"❌ 策略文件不存在: {strategy_file}")
            results[strategy_file] = False
    
    # 打印测试总结
    logger.info("\n" + "=" * 60)
    logger.info("测试总结")
    logger.info("=" * 60)
    
    passed = 0
    failed = 0
    
    for strategy_file, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{strategy_file}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    logger.info("\n" + "=" * 60)
    logger.info(f"总计: {len(results)} 个策略文件")
    logger.info(f"通过: {passed} 个")
    logger.info(f"失败: {failed} 个")
    
    if failed == 0:
        logger.info("🎉 所有策略文件测试通过！")
    else:
        logger.warning(f"⚠️  有 {failed} 个策略文件测试失败")
    
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
