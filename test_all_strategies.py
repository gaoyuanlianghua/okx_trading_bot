#!/usr/bin/env python3
"""
OKX交易机器人策略API连接测试
测试所有策略的API连接是否正常
"""

import asyncio
import time
import logging
import yaml
import os
import importlib.util

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def load_config():
    """加载配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


async def test_strategy_api(strategy_name, strategy_file):
    """测试单个策略的API连接"""
    logger.info(f"\n测试策略: {strategy_name}")
    
    try:
        # 加载配置
        config = await load_config()
        api_config = config.get('api', {})
        
        # 导入OKX REST客户端
        from core.api.okx_rest_client import OKXRESTClient
        
        # 初始化REST客户端
        client = OKXRESTClient(
            api_key=api_config.get('api_key', ''),
            api_secret=api_config.get('api_secret', ''),
            passphrase=api_config.get('passphrase', ''),
            is_test=api_config.get('is_test', True),
            timeout=api_config.get('timeout', 30)
        )
        
        try:
            # 测试API连接
            logger.info(f"  测试API连接...")
            start_time = time.time()
            server_time = await client.get_server_time()
            end_time = time.time()
            
            if server_time:
                logger.info(f"  ✓ API连接成功")
                logger.info(f"  响应时间: {((end_time - start_time) * 1000):.2f}ms")
            else:
                logger.error(f"  ✗ API连接失败")
                return False
            
            # 测试获取行情数据
            logger.info(f"  测试获取行情数据...")
            start_time = time.time()
            ticker = await client.get_ticker("BTC-USDT")
            end_time = time.time()
            
            if ticker:
                logger.info(f"  ✓ 行情数据获取成功")
                logger.info(f"  响应时间: {((end_time - start_time) * 1000):.2f}ms")
                logger.info(f"  最新价格: {ticker.get('last')}")
            else:
                logger.error(f"  ✗ 行情数据获取失败")
                return False
            
            # 测试获取账户余额（如果API密钥配置正确）
            logger.info(f"  测试获取账户余额...")
            start_time = time.time()
            balance = await client.get_account_balance()
            end_time = time.time()
            
            if balance:
                logger.info(f"  ✓ 账户余额获取成功")
                logger.info(f"  响应时间: {((end_time - start_time) * 1000):.2f}ms")
            else:
                logger.warning(f"  ⚠ 账户余额获取失败（可能是权限问题）")
            
            # 尝试加载策略模块，测试模块是否可导入
            logger.info(f"  测试策略模块加载...")
            import sys
            sys.path.insert(0, '.')
            
            # 尝试直接导入
            module_name = f"strategies.{strategy_file[:-3]}"
            strategy_module = __import__(module_name, fromlist=[strategy_name])
            logger.info(f"  ✓ 策略模块加载成功")
            
            return True
            
        finally:
            # 关闭客户端
            await client.close()
            
    except Exception as e:
        logger.error(f"  ✗ 策略测试失败: {e}")
        return False


async def main():
    """主测试函数"""
    logger.info("=" * 60)
    logger.info("OKX交易机器人策略API连接测试")
    logger.info("=" * 60)
    
    # 策略列表
    strategies = [
        ("ArbitrageStrategy", "arbitrage_strategy.py"),
        ("CombinedStrategy", "combined_strategy.py"),
        ("CrossMarketArbitrageStrategy", "cross_market_arbitrage_strategy.py"),
        ("DynamicsStrategy", "dynamics_strategy.py"),
        ("MACD_Bollinger_Strategy", "macd_bollinger_strategy.py"),
        ("MachineLearningStrategy", "machine_learning_strategy.py"),
        ("MA_RSI_Strategy", "ma_rsi_strategy.py"),
        ("NuclearDynamicsStrategy", "nuclear_dynamics_strategy.py"),
        ("PassivbotIntegrator", "passivbot_integrator.py")
    ]
    
    # 测试结果
    results = {}
    
    # 测试每个策略
    for strategy_name, strategy_file in strategies:
        success = await test_strategy_api(strategy_name, strategy_file)
        results[strategy_name] = success
    
    # 输出测试结果
    logger.info("\n" + "=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)
    
    success_count = 0
    total_count = len(results)
    
    for strategy_name, success in results.items():
        status = "✓ 成功" if success else "✗ 失败"
        logger.info(f"{strategy_name}: {status}")
        if success:
            success_count += 1
    
    logger.info("\n测试统计:")
    logger.info(f"总策略数: {total_count}")
    logger.info(f"成功数: {success_count}")
    logger.info(f"失败数: {total_count - success_count}")
    logger.info(f"成功率: {((success_count / total_count) * 100):.2f}%")
    
    logger.info("\n" + "=" * 60)
    logger.info("策略API连接测试完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
