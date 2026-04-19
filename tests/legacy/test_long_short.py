#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# test_long_short.py
# 测试现货杠杆交易的多空双开功能

import asyncio
import logging
from core.agents.order_agent import OrderAgent
from core.agents.base_agent import AgentConfig
from core.utils.config_manager import get_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_long_short_trading():
    """测试现货杠杆交易的多空双开功能"""
    try:
        # 加载配置
        api_config = get_config("api")
        
        # 初始化订单智能体配置
        order_agent_config = AgentConfig(name="OrderAgent")
        
        # 初始化订单智能体
        order_agent = OrderAgent(
            config=order_agent_config,
            exchange_name="okx",
            api_key=api_config["api_key"],
            api_secret=api_config["api_secret"],
            passphrase=api_config["passphrase"],
            is_test=api_config.get("is_test", False)
        )
        
        # 启动订单智能体
        await order_agent.start()
        
        # 1. 测试买入操作（做多）
        logger.info("测试买入操作（做多）...")
        buy_params = {
            "inst_id": "BTC-USDT",
            "side": "buy",
            "ord_type": "market",
            "sz": "1.0",  # 1 USDT
            "td_mode": "isolated",  # 逐仓模式
            "lever": "2"  # 2倍杠杆
        }
        buy_result = await order_agent.place_order(buy_params)
        logger.info(f"买入结果: {buy_result}")
        
        # 等待1秒
        await asyncio.sleep(1)
        
        # 2. 测试卖出操作（做空）
        logger.info("测试卖出操作（做空）...")
        # 使用固定的卖出数量，避免API调用失败
        sell_amount = 0.00001  # 最小交易单位
        
        sell_params = {
            "inst_id": "BTC-USDT",
            "side": "sell",
            "ord_type": "market",
            "sz": f"{sell_amount:.5f}",  # BTC数量
            "td_mode": "isolated",  # 逐仓模式
            "lever": "2"  # 2倍杠杆
        }
        sell_result = await order_agent.place_order(sell_params)
        logger.info(f"卖出结果: {sell_result}")
        
        # 3. 检查订单状态
        logger.info("检查订单状态...")
        if buy_result.get("order_id"):
            logger.info(f"买入订单ID: {buy_result['order_id']}")
        
        if sell_result.get("order_id"):
            logger.info(f"卖出订单ID: {sell_result['order_id']}")
        
        # 4. 检查账户余额
        logger.info("检查账户余额...")
        from core.api.okx_rest_client import OKXRESTClient
        rest_client = OKXRESTClient(
            api_key=api_config["api_key"],
            api_secret=api_config["api_secret"],
            passphrase=api_config["passphrase"],
            is_test=api_config.get("is_test", False)
        )
        
        try:
            balance = await rest_client.get_account_balance()
            if balance and isinstance(balance, dict):
                logger.info(f"账户余额信息: {balance}")
            else:
                logger.error("获取账户余额失败")
        except Exception as e:
            logger.error(f"获取账户余额时出错: {e}")
        
        # 停止订单智能体
        await order_agent.stop()
        
        logger.info("多空双开交易测试完成")
        
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_long_short_trading())
    loop.close()
