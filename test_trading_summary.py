"""
交易摘要测试脚本 - 验证交易记录和收益跟踪功能
"""

import asyncio
import logging
import sys
import os

# 设置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 导入核心组件
from core import (
    EventBus,
    Event,
    EventType,
    AgentConfig,
    MarketDataAgent,
    OrderAgent,
    RiskAgent,
    StrategyAgent,
    CoordinatorAgent,
    OKXRESTClient,
    OKXWebSocketClient,
)


async def test_trading_summary():
    """测试交易摘要功能"""
    logger.info("=== 测试交易摘要功能 ===")

    # 创建API客户端
    rest_client = OKXRESTClient(is_test=True)
    ws_client = OKXWebSocketClient(is_test=True)

    # 创建智能体
    market_data_agent = MarketDataAgent(
        config=AgentConfig(name="MarketData"),
        rest_client=rest_client,
        ws_client=ws_client,
    )

    order_agent = OrderAgent(config=AgentConfig(name="Order"), rest_client=rest_client)

    risk_agent = RiskAgent(config=AgentConfig(name="Risk"), rest_client=rest_client)

    strategy_agent = StrategyAgent(
        config=AgentConfig(name="Strategy"),
        market_data_agent=market_data_agent,
        order_agent=order_agent,
    )

    coordinator = CoordinatorAgent(AgentConfig(name="Coordinator"))

    # 注册智能体
    coordinator.register_agent(market_data_agent)
    coordinator.register_agent(order_agent)
    coordinator.register_agent(risk_agent)
    coordinator.register_agent(strategy_agent)

    logger.info(f"注册了 {len(coordinator._agents)} 个智能体")

    # 启动智能体
    await coordinator.start()
    await market_data_agent.start()
    await order_agent.start()
    await risk_agent.start()
    await strategy_agent.start()

    logger.info("所有智能体启动成功")

    # 模拟交易记录
    logger.info("=== 模拟交易记录 ===")

    # 模拟订单填充事件
    mock_order = {
        "ordId": "test_order_001",
        "instId": "BTC-USDT-SWAP",
        "side": "buy",
        "ordType": "limit",
        "avgPx": "50000.0",
        "sz": "0.01",
        "accFillSz": "0.01",
        "fee": "0.1",
        "state": "filled",
        "cTime": "1774764217554910",
        "fillTime": "1774764217554910",
    }

    # 发布订单填充事件
    event = Event(
        type=EventType.ORDER_FILLED, source="test", data={"order": mock_order}
    )

    # 触发事件
    await coordinator.event_bus.publish_async(event)
    await asyncio.sleep(1)

    # 测试交易摘要
    logger.info("=== 测试交易摘要 ===")
    summary = coordinator.get_trading_summary()

    logger.info(f"交易摘要: {summary}")
    logger.info(f"总交易次数: {summary.get('total_trades')}")
    logger.info(f"总收益: {summary.get('total_pnl')}")
    logger.info(f"总费用: {summary.get('total_fees')}")
    logger.info(f"账户信息: {summary.get('account_info')}")
    logger.info(f"资产分布: {summary.get('asset_distribution')}")

    # 测试订单智能体的交易历史
    trade_history = order_agent.get_trade_history()
    logger.info(f"交易历史: {trade_history}")

    # 测试风险管理智能体的账户信息
    account_info = risk_agent.get_account_info()
    logger.info(f"账户信息: {account_info}")

    asset_distribution = risk_agent.get_asset_distribution()
    logger.info(f"资产分布: {asset_distribution}")

    # 停止智能体
    await strategy_agent.stop()
    await risk_agent.stop()
    await order_agent.stop()
    await market_data_agent.stop()
    await coordinator.stop()

    # 关闭客户端
    await rest_client.close()
    await ws_client.close()

    logger.info("测试完成")


async def main():
    """主测试函数"""
    try:
        await test_trading_summary()
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
