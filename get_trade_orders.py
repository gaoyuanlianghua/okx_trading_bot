#!/usr/bin/env python3
"""
获取OKX交易订单信息

此脚本从OKX API获取交易订单信息，并显示详细的订单数据
"""

import asyncio
import logging
from core.utils.logger import logger_config, get_logger
from core import OKXRESTClient
from core.utils.config_manager import get_config
import os

# 配置日志
logger_config.configure(level=logging.INFO, structured=False)
logger = get_logger(__name__)

async def get_trade_orders():
    """
    获取交易订单信息
    """
    try:
        # 从配置获取API密钥
        api_key = get_config("api.api_key", os.getenv("OKX_API_KEY", ""))
        api_secret = get_config("api.api_secret", os.getenv("OKX_API_SECRET", ""))
        passphrase = get_config("api.passphrase", os.getenv("OKX_PASSPHRASE", ""))
        is_test = get_config("api.is_test", True)
        
        # 创建REST客户端
        rest_client = OKXRESTClient(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            is_test=is_test,
        )
        
        logger.info("开始获取交易订单信息...")
        
        # 获取最近的交易订单
        # 现货交易订单
        logger.info("\n📊 现货交易订单:")
        spot_orders = await rest_client.get_order_history(
            inst_type="SPOT",
            inst_id="BTC-USDT",
            limit=10  # 最近10个订单
        )
        
        if spot_orders:
            logger.info(f"获取到 {len(spot_orders)} 个现货订单")
            for order in spot_orders:
                logger.info(f"  订单ID: {order.get('ordId')}")
                logger.info(f"  方向: {'买入' if order.get('side') == 'buy' else '卖出'}")
                logger.info(f"  价格: {order.get('avgPx')} USDT")
                logger.info(f"  数量: {order.get('accFillSz')} BTC")
                logger.info(f"  状态: {order.get('state')}")
                logger.info(f"  时间: {order.get('cTime')}")
                logger.info(f"  手续费: {order.get('fee')} {order.get('feeCcy')}")
                logger.info("  " + "-" * 50)
        else:
            logger.info("  暂无现货交易订单")
        
        # 杠杆交易订单
        logger.info("\n📊 杠杆交易订单:")
        margin_orders = await rest_client.get_order_history(
            inst_type="MARGIN",
            inst_id="BTC-USDT",
            limit=20  # 最近20个订单
        )
        
        if margin_orders:
            logger.info(f"获取到 {len(margin_orders)} 个杠杆订单")
            for order in margin_orders:
                logger.info(f"  订单ID: {order.get('ordId')}")
                logger.info(f"  方向: {'买入' if order.get('side') == 'buy' else '卖出'}")
                logger.info(f"  价格: {order.get('avgPx')} USDT")
                logger.info(f"  数量: {order.get('accFillSz')} BTC")
                logger.info(f"  状态: {order.get('state')}")
                logger.info(f"  杠杆: {order.get('lever')}x")
                logger.info(f"  时间: {order.get('cTime')}")
                logger.info(f"  手续费: {order.get('fee')} {order.get('feeCcy')}")
                logger.info(f"  盈亏: {order.get('pnl')} USDT")
                logger.info("  " + "-" * 50)
        else:
            logger.info("  暂无杠杆交易订单")
        
        # 获取未成交订单
        logger.info("\n📊 未成交订单:")
        open_orders = await rest_client.get_pending_orders(
            inst_id="BTC-USDT",
            inst_type="MARGIN"
        )
        
        if open_orders:
            logger.info(f"获取到 {len(open_orders)} 个未成交订单")
            for order in open_orders:
                logger.info(f"  订单ID: {order.get('ordId')}")
                logger.info(f"  方向: {'买入' if order.get('side') == 'buy' else '卖出'}")
                logger.info(f"  价格: {order.get('px')} USDT")
                logger.info(f"  数量: {order.get('sz')} BTC")
                logger.info(f"  状态: {order.get('state')}")
                logger.info(f"  时间: {order.get('cTime')}")
                logger.info("  " + "-" * 50)
        else:
            logger.info("  暂无未成交订单")
        
        # 关闭客户端
        await rest_client.close()
        
        logger.info("\n✅ 交易订单信息获取完成")
        
    except Exception as e:
        logger.error(f"❌ 获取交易订单信息失败: {e}")
        import traceback
        logger.error(f"详细错误信息:\n{traceback.format_exc()}")

if __name__ == "__main__":
    # 使用传统的事件循环方式运行异步任务
    loop = asyncio.get_event_loop()
    loop.run_until_complete(get_trade_orders())
    loop.close()
