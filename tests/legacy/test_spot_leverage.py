#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# test_spot_leverage.py
# 测试现货杠杆交易功能

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

async def test_spot_leverage_trading():
    """测试现货杠杆交易功能"""
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
        
        # 1. 测试买入操作（现货杠杆）
        logger.info("测试买入操作...")
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
        
        # 2. 测试卖出操作（现货杠杆）
        logger.info("测试卖出操作...")
        # 计算卖出数量（约1 USDT的BTC）
        from core.api.okx_rest_client import OKXRESTClient
        rest_client = OKXRESTClient(
            api_key=api_config["api_key"],
            api_secret=api_config["api_secret"],
            passphrase=api_config["passphrase"],
            is_test=api_config.get("is_test", False)
        )
        
        # 添加错误处理，处理ticker为None的情况
        try:
            ticker = await rest_client.get_ticker("BTC-USDT")
            if ticker and isinstance(ticker, dict) and "data" in ticker and len(ticker["data"]) > 0:
                current_price = float(ticker["data"][0]["last"])
                sell_amount = 1.0 / current_price  # 1 USDT的BTC数量
                sell_amount = round(sell_amount, 5)  # 保留5位小数
                
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
            else:
                logger.error("获取ticker数据失败，跳过卖出操作")
                sell_result = {"success": False, "error": "获取ticker数据失败"}
        except Exception as e:
            logger.error(f"获取ticker数据或执行卖出操作时出错: {e}")
            sell_result = {"success": False, "error": f"获取ticker数据或执行卖出操作时出错: {e}"}
        
        # 3. 检查订单状态
        logger.info("检查订单状态...")
        if buy_result.get("order_id"):
            buy_order_id = buy_result["order_id"]
            # 订单智能体的get_order_info方法需要inst_id参数
            buy_order_status = await rest_client.get_order_info(buy_order_id, "BTC-USDT")
            logger.info(f"买入订单状态: {buy_order_status}")
        
        if sell_result.get("order_id"):
            sell_order_id = sell_result["order_id"]
            sell_order_status = await rest_client.get_order_info(sell_order_id, "BTC-USDT")
            logger.info(f"卖出订单状态: {sell_order_status}")
        
        # 停止订单智能体
        await order_agent.stop()
        
        logger.info("现货杠杆交易测试完成")
        
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_spot_leverage_trading())
    loop.close()
