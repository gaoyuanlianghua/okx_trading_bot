#!/usr/bin/env python3
"""
验证各种交易类型的脚本
"""

import asyncio
import sys
import logging
from core.api.exchange_manager import exchange_manager
from core.traders.trader_manager import TraderManager
import aiohttp

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """主函数"""
    try:
        logger.info("开始验证各种交易类型...")
        
        # 从配置文件获取API参数
        import yaml
        import json
        
        # 读取当前环境配置
        with open('config/current_env.json', 'r') as f:
            current_env = json.load(f)
        env = current_env.get('env', 'test')
        
        # 读取对应环境的配置文件
        config_file = f'config/config_{env}.yaml' if env != 'live' else 'config/config_live.yaml'
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        api_config = config.get('api', {})
        api_key = api_config.get('api_key')
        api_secret = api_config.get('api_secret')
        passphrase = api_config.get('passphrase')
        is_test = api_config.get('is_test', env == 'test')
        
        if not api_key or not api_secret or not passphrase:
            logger.error(f"请在{config_file}中配置API参数")
            return
        
        # 初始化交易所
        logger.info(f"初始化交易所: okx, 模拟盘: {is_test}")
        exchange = exchange_manager.get_exchange(
            'okx',
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            is_test=is_test
        )
        
        if not exchange:
            logger.error("初始化交易所失败")
            return
        
        logger.info("交易所初始化成功")
        
        # 创建交易器管理器
        logger.info("创建交易器管理器")
        trader_manager = TraderManager(exchange)
        
        # 创建现货交易器
        logger.info("创建现货交易器")
        spot_trader = trader_manager.create_trader('spot', 'default_spot')
        
        # 验证各种交易类型
        logger.info("开始验证各种交易类型")
        results = await spot_trader.validate_trade_types()
        
        # 打印验证结果
        logger.info("\n验证结果:")
        for trade_type, result in results.items():
            logger.info(f"{trade_type}:")
            if 'success' in result:
                logger.info(f"  成功: {result['success']}")
                if result['success']:
                    logger.info(f"  订单ID: {result.get('order_id')}")
                else:
                    logger.info(f"  错误信息: {result.get('error_message')}")
            else:
                logger.info(f"  错误: {result.get('error')}")
        
    except Exception as e:
        logger.error(f"验证交易类型失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
