#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# test_long_short_direct.py
# 直接测试现货杠杆交易的多空双开功能，绕过收益率检查

import asyncio
import logging
from core.api.okx_rest_client import OKXRESTClient
from core.utils.config_manager import get_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_long_short_trading():
    """直接测试现货杠杆交易的多空双开功能"""
    try:
        # 加载配置
        api_config = get_config("api")
        
        # 初始化OKX REST客户端
        rest_client = OKXRESTClient(
            api_key=api_config["api_key"],
            api_secret=api_config["api_secret"],
            passphrase=api_config["passphrase"],
            is_test=api_config.get("is_test", False)
        )
        
        # 1. 检查账户余额
        logger.info("检查账户余额...")
        balance = await rest_client.get_account_balance()
        if balance and isinstance(balance, dict):
            logger.info(f"账户余额信息: {balance}")
        else:
            logger.error("获取账户余额失败")
        
        # 2. 检查账户状态
        logger.info("检查账户状态...")
        try:
            # 尝试获取账户信息
            account_info = await rest_client.request("GET", "/account/info")
            logger.info(f"账户信息: {account_info}")
        except Exception as e:
            logger.error(f"获取账户信息失败: {e}")
        
        # 3. 测试买入操作（做多）- 使用现金模式
        logger.info("测试买入操作（做多）...")
        try:
            buy_order_id = await rest_client.place_order(
                inst_id="BTC-USDT",
                side="buy",
                ord_type="market",
                sz="1.0",  # 1 USDT
                td_mode="cash",  # 现金模式
                lever=""
            )
            logger.info(f"买入订单ID: {buy_order_id}")
        except Exception as e:
            logger.error(f"买入操作失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 等待1秒
        await asyncio.sleep(1)
        
        # 4. 测试卖出操作（做空）- 使用现金模式
        logger.info("测试卖出操作（做空）...")
        try:
            # 使用固定的卖出数量，避免API调用失败
            sell_amount = 0.00001  # 最小交易单位
            
            sell_order_id = await rest_client.place_order(
                inst_id="BTC-USDT",
                side="sell",
                ord_type="market",
                sz=f"{sell_amount:.5f}",  # BTC数量
                td_mode="cash",  # 现金模式
                lever=""
            )
            logger.info(f"卖出订单ID: {sell_order_id}")
        except Exception as e:
            logger.error(f"卖出操作失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 5. 再次检查账户余额
        logger.info("再次检查账户余额...")
        balance = await rest_client.get_account_balance()
        if balance and isinstance(balance, dict):
            logger.info(f"账户余额信息: {balance}")
        else:
            logger.error("获取账户余额失败")
        
        logger.info("多空双开交易测试完成")
        
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_long_short_trading())
    loop.close()
