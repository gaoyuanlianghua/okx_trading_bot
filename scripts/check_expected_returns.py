#!/usr/bin/env python3
"""
查看最近订单的预期收益情况
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

async def check_expected_returns():
    """检查最近订单的预期收益"""
    rest_client = None
    try:
        # 加载配置
        logger.info("正在加载配置...")
        config_manager = ConfigManager()
        
        # 获取API配置
        api_key = config_manager.get("api.api_key")
        api_secret = config_manager.get("api.api_secret")
        passphrase = config_manager.get("api.passphrase")
        is_test = config_manager.get("api.is_test", True)
        
        logger.info(f"API配置加载完成: is_test={is_test}")
        
        # 创建REST客户端
        logger.info("正在创建REST客户端...")
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
        
        logger.info("REST客户端创建成功")
        
        # 获取最近订单
        logger.info("=" * 60)
        logger.info("查询最近订单的预期收益情况")
        logger.info("=" * 60)
        
        # 获取账户余额
        try:
            logger.info("正在获取账户余额...")
            balance = await rest_client.get_account_balance()
            if balance:
                logger.info(f"\n账户余额:")
                if isinstance(balance, list):
                    for item in balance:
                        if isinstance(item, dict):
                            logger.info(f"  {item.get('ccy', 'N/A')}: {item.get('availBal', '0')} (可用)")
                        else:
                            logger.info(f"  {item}")
                elif isinstance(balance, dict):
                    for key, value in balance.items():
                        logger.info(f"  {key}: {value}")
                else:
                    logger.info(f"  {balance}")
            else:
                logger.info("\n暂无账户余额信息")
        except Exception as e:
            logger.error(f"获取账户余额失败: {e}")
        
        # 获取最近订单
        try:
            logger.info("正在获取最近订单...")
            orders = await rest_client.get_order_history(inst_type="SPOT", inst_id="BTC-USDT", limit=10)
            if orders:
                logger.info(f"\n最近订单 ({len(orders)}个):")
                logger.info("-" * 60)
                for i, order in enumerate(orders, 1):
                    if isinstance(order, dict):
                        order_id = order.get('ordId', 'N/A')
                        side = order.get('side', 'N/A')
                        price = order.get('avgPx', order.get('px', '0'))
                        size = order.get('sz', '0')
                        state = order.get('state', 'N/A')
                        fee = order.get('fee', '0')
                        
                        # 计算预期收益率（简化计算）
                        if price and float(price) > 0:
                            # 假设目标收益率为0.5%
                            target_return = 0.005
                            # 简化的预期收益计算
                            expected_return = target_return
                            
                            logger.info(f"\n订单 {i}:")
                            logger.info(f"  订单ID: {order_id}")
                            logger.info(f"  方向: {side}")
                            logger.info(f"  价格: {price}")
                            logger.info(f"  数量: {size}")
                            logger.info(f"  状态: {state}")
                            logger.info(f"  手续费: {fee}")
                            logger.info(f"  预期收益率: {expected_return * 100:.2f}%")
                        else:
                            logger.info(f"\n订单 {i}:")
                            logger.info(f"  订单ID: {order_id}")
                            logger.info(f"  方向: {side}")
                            logger.info(f"  价格: {price}")
                            logger.info(f"  数量: {size}")
                            logger.info(f"  状态: {state}")
                            logger.info(f"  手续费: {fee}")
                            logger.info(f"  预期收益率: 无法计算")
                    else:
                        logger.info(f"\n订单 {i}: {order}")
            else:
                logger.info("\n暂无订单记录")
        except Exception as e:
            logger.error(f"获取订单历史失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # 获取未成交订单
        try:
            logger.info("正在获取未成交订单...")
            pending_orders = await rest_client.get_pending_orders(inst_id="BTC-USDT")
            if pending_orders:
                logger.info(f"\n未成交订单 ({len(pending_orders)}个):")
                logger.info("-" * 60)
                for i, order in enumerate(pending_orders, 1):
                    if isinstance(order, dict):
                        order_id = order.get('ordId', 'N/A')
                        side = order.get('side', 'N/A')
                        price = order.get('px', '0')
                        size = order.get('sz', '0')
                        
                        logger.info(f"\n未成交订单 {i}:")
                        logger.info(f"  订单ID: {order_id}")
                        logger.info(f"  方向: {side}")
                        logger.info(f"  价格: {price}")
                        logger.info(f"  数量: {size}")
                    else:
                        logger.info(f"\n未成交订单 {i}: {order}")
            else:
                logger.info("\n暂无未成交订单")
        except Exception as e:
            logger.error(f"获取未成交订单失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        logger.info("\n" + "=" * 60)
        logger.info("查询完成")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"查询订单预期收益失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # 关闭客户端连接
        if rest_client and hasattr(rest_client, 'close'):
            await rest_client.close()

if __name__ == "__main__":
    # Python 3.6兼容性处理
    try:
        asyncio.run(check_expected_returns())
    except AttributeError:
        # Python 3.6使用旧的事件循环API
        loop = asyncio.get_event_loop()
        loop.run_until_complete(check_expected_returns())
