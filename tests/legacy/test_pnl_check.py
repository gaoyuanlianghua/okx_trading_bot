#!/usr/bin/env python3
"""
测试订单智能体的未实现盈亏率检查功能
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 设置日志级别
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from core.api.exchange_manager import exchange_manager
from core.utils.config_manager import ConfigManager
from core.utils.logger import get_logger

logger = get_logger(__name__)

async def test_pnl_check():
    """测试未实现盈亏率检查"""
    rest_client = None
    try:
        # 加载配置
        config_manager = ConfigManager()
        
        # 获取API配置
        api_key = config_manager.get("api.api_key")
        api_secret = config_manager.get("api.api_secret")
        passphrase = config_manager.get("api.passphrase")
        is_test = config_manager.get("api.is_test", True)
        
        # 创建REST客户端
        rest_client = exchange_manager.get_exchange(
            "okx",
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            is_test=is_test
        )
        
        if not rest_client:
            logger.error("无法创建REST客户端")
            return
        
        logger.info("=" * 60)
        logger.info("测试未实现盈亏率检查功能")
        logger.info("=" * 60)
        
        # 获取账户余额信息
        balance = await rest_client.get_account_balance()
        if balance and isinstance(balance, dict):
            details = balance.get('details', [])
            
            # 查找BTC持仓信息
            btc_info = None
            for item in details:
                if isinstance(item, dict) and item.get('ccy') == 'BTC':
                    btc_info = item
                    break
            
            if btc_info:
                logger.info("\n📊 BTC持仓详情:")
                logger.info("-" * 60)
                
                avail_bal = float(btc_info.get('availBal', 0))
                eq = float(btc_info.get('eq', 0))
                eq_usd = float(btc_info.get('eqUsd', 0))
                spot_upl = float(btc_info.get('spotUpl', 0))
                spot_upl_ratio = float(btc_info.get('spotUplRatio', 0))
                
                logger.info(f"  可用余额: {avail_bal} BTC")
                logger.info(f"  总权益: {eq} BTC")
                logger.info(f"  权益价值: {eq_usd} USDT")
                logger.info(f"  未实现盈亏: {spot_upl} BTC")
                logger.info(f"  未实现盈亏率: {spot_upl_ratio * 100:.4f}%")
                
                # 检查盈亏率是否达到1.0%
                if spot_upl_ratio >= 0.01:
                    logger.info("  ✅ 未实现盈亏率达到1.0%，可以平仓")
                else:
                    logger.info("  ❌ 未实现盈亏率未达到1.0%，不能平仓")
            else:
                logger.info("\n未找到BTC持仓信息")
        else:
            logger.info("\n无法获取账户余额信息")
        
        # 测试订单智能体的平仓检查
        logger.info("\n" + "-" * 60)
        logger.info("测试订单智能体平仓检查")
        logger.info("-" * 60)
        
        # 模拟平仓操作
        test_order = {
            "inst_id": "BTC-USDT",
            "side": "sell",
            "ord_type": "limit",
            "sz": "0.00001",
            "px": "66700",
            "td_mode": "cross"
        }
        
        logger.info(f"模拟平仓订单: {test_order}")
        
        # 计算预期盈亏率
        if rest_client:
            # 获取当前价格
            ticker = await rest_client.get_ticker("BTC-USDT")
            if ticker and isinstance(ticker, list) and len(ticker) > 0:
                current_price = float(ticker[0].get('last', 0))
                order_price = float(test_order['px'])
                
                # 计算预期盈亏率
                expected_pnl_ratio = (order_price - current_price) / current_price
                logger.info(f"当前价格: {current_price} USDT")
                logger.info(f"订单价格: {order_price} USDT")
                logger.info(f"预期盈亏率: {expected_pnl_ratio * 100:.4f}%")
        
        logger.info("\n" + "=" * 60)
        logger.info("测试完成")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        if rest_client and hasattr(rest_client, 'close'):
            await rest_client.close()

if __name__ == "__main__":
    try:
        asyncio.run(test_pnl_check())
    except AttributeError:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(test_pnl_check())
