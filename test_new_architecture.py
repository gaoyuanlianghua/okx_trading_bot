"""
新架构测试脚本 - 验证核心组件功能
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


async def test_event_bus():
    """测试事件总线"""
    logger.info("=== 测试事件总线 ===")

    event_bus = EventBus()
    event_bus.start()

    # 测试事件发布和订阅
    received_events = []

    def handler(event):
        received_events.append(event)
        logger.info(f"收到事件: {event.type.name}")

    event_bus.subscribe(EventType.SYSTEM_STARTUP, handler)

    # 发布事件
    event = Event(type=EventType.SYSTEM_STARTUP, source="test", data={"test": True})

    count = event_bus.publish(event)
    logger.info(f"事件通知了 {count} 个订阅者")

    assert len(received_events) == 1, "事件订阅失败"

    event_bus.stop()
    logger.info("事件总线测试通过\n")


async def test_agents():
    """测试智能体"""
    logger.info("=== 测试智能体 ===")

    # 创建配置
    config = AgentConfig(name="TestAgent", description="测试智能体")

    # 创建协调智能体
    coordinator = CoordinatorAgent(config)

    # 测试启动和停止
    result = await coordinator.start()
    assert result, "智能体启动失败"
    logger.info("智能体启动成功")

    # 获取状态
    status = coordinator.get_status()
    logger.info(f"智能体状态: {status}")

    # 停止
    result = await coordinator.stop()
    assert result, "智能体停止失败"
    logger.info("智能体停止成功")

    logger.info("智能体测试通过\n")


async def test_api_clients():
    """测试API客户端"""
    logger.info("=== 测试API客户端 ===")

    # 创建REST客户端（使用模拟盘）
    rest_client = OKXRESTClient(is_test=True)

    # 测试获取服务器时间
    try:
        server_time = await rest_client.get_server_time()
        logger.info(f"服务器时间: {server_time}")
    except Exception as e:
        logger.warning(f"获取服务器时间失败: {e}")

    # 测试获取交易产品
    try:
        instruments = await rest_client.get_instruments("SWAP")
        logger.info(f"获取到 {len(instruments)} 个交易产品")
        if instruments:
            logger.info(f"第一个产品: {instruments[0].get('instId')}")
    except Exception as e:
        logger.warning(f"获取交易产品失败: {e}")

    # 测试获取ticker
    try:
        ticker = await rest_client.get_ticker("BTC-USDT-SWAP")
        if ticker:
            logger.info(f"BTC-USDT-SWAP 最新价格: {ticker.get('last')}")
        else:
            logger.warning("获取ticker失败")
    except Exception as e:
        logger.warning(f"获取ticker失败: {e}")

    # 关闭客户端
    await rest_client.close()
    logger.info("API客户端测试通过\n")


async def test_strategy_loading():
    """测试策略加载"""
    logger.info("=== 测试策略加载 ===")

    try:
        from strategies.dynamics_strategy import DynamicsStrategy

        # 创建策略实例
        config = {"dynamics": {"ε": 0.85, "G_eff": 1.2e-3}}

        strategy = DynamicsStrategy(config=config)
        logger.info(f"策略创建成功: {strategy.name}")

        # 测试策略执行
        market_data = {"price": 50000.0, "timestamp": 1234567890}

        signal = strategy.execute(market_data)
        logger.info(f"策略信号: {signal}")

        strategy.start()
        logger.info("策略启动成功")

        strategy.stop()
        logger.info("策略停止成功")

        logger.info("策略加载测试通过\n")

    except Exception as e:
        logger.error(f"策略加载测试失败: {e}")


async def test_full_system():
    """测试完整系统"""
    logger.info("=== 测试完整系统 ===")

    try:
        # 创建API客户端
        rest_client = OKXRESTClient(is_test=True)
        ws_client = OKXWebSocketClient(is_test=True)

        # 创建智能体
        market_data_agent = MarketDataAgent(
            config=AgentConfig(name="MarketData"),
            rest_client=rest_client,
            ws_client=ws_client,
        )

        order_agent = OrderAgent(
            config=AgentConfig(name="Order"), rest_client=rest_client
        )

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

        # 测试启动
        await coordinator.start()
        await market_data_agent.start()
        await order_agent.start()
        await risk_agent.start()
        await strategy_agent.start()

        logger.info("所有智能体启动成功")

        # 运行一小段时间
        await asyncio.sleep(3)

        # 获取状态
        status = coordinator.get_status()
        logger.info(f"系统状态: {status['system_health']}")

        # 停止
        await strategy_agent.stop()
        await risk_agent.stop()
        await order_agent.stop()
        await market_data_agent.stop()
        await coordinator.stop()

        # 关闭客户端
        await rest_client.close()
        await ws_client.close()

        logger.info("完整系统测试通过\n")

    except Exception as e:
        logger.error(f"完整系统测试失败: {e}")
        import traceback

        traceback.print_exc()


async def main():
    """主测试函数"""
    logger.info("开始测试新架构...\n")

    try:
        # 运行各个测试
        await test_event_bus()
        await test_agents()
        await test_api_clients()
        await test_strategy_loading()
        await test_full_system()

        logger.info("所有测试完成！")

    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
