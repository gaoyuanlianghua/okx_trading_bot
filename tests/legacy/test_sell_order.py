#!/usr/bin/env python3
"""
测试卖出订单功能
"""

import asyncio
import logging
from core.agents.order_agent_adapter import OrderAgentAdapter as OrderAgent
from core.api.okx_rest_client import OKXRESTClient
import os

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_sell_order():
    """测试卖出订单"""
    logger.info("开始测试卖出订单...")
    
    # 创建OKX REST客户端
    rest_client = OKXRESTClient(
        api_key=os.getenv('OKX_API_KEY'),
        api_secret=os.getenv('OKX_API_SECRET'),
        passphrase=os.getenv('OKX_PASSPHRASE')
    )
    
    # 创建订单智能体
    order_agent = OrderAgent(rest_client=rest_client)
    
    # 初始化订单智能体
    await order_agent._initialize()
    
    # 同步账户和订单状态
    sync_result = await order_agent.sync_account_and_orders()
    logger.info(f"同步结果: {sync_result}")
    
    # 构建卖出订单参数
    order_params = {
        "inst_id": "BTC-USDT",
        "side": "sell",
        "ord_type": "market",
        "sz": "0.00001",  # 卖出0.00001 BTC
        "td_mode": "cash",
        "expected_return": 0.01,  # 1% 预期收益
        "price": 73000  # 当前BTC价格
    }
    
    # 执行卖出操作
    logger.info("执行卖出操作...")
    result = await order_agent.sell(order_params)
    logger.info(f"卖出操作结果: {result}")
    
    # 清理
    await order_agent._cleanup()
    
    return result

if __name__ == "__main__":
    # 加载环境变量
    if not os.getenv('OKX_API_KEY'):
        os.environ['OKX_API_KEY'] = 'your_api_key'
        os.environ['OKX_API_SECRET'] = 'your_api_secret'
        os.environ['OKX_PASSPHRASE'] = 'your_passphrase'
    
    # 运行测试
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(test_sell_order())
    logger.info(f"测试完成，结果: {result}")
