#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略执行链路诊断脚本

用于诊断策略信号是否正确生成和传递
"""

import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("Diagnosis")


async def diagnose():
    """诊断策略执行链路"""
    logger.info("=" * 60)
    logger.info("开始诊断策略执行链路")
    logger.info("=" * 60)

    # 1. 检查策略智能体
    logger.info("\n1. 检查StrategyAgent...")
    from core.agents.strategy_agent import StrategyAgent
    from core.agents.base_agent import AgentConfig

    strategy_config = AgentConfig(name="Strategy", description="策略执行智能体")
    strategy_agent = StrategyAgent(config=strategy_config)

    # 2. 初始化策略智能体
    logger.info("\n2. 初始化StrategyAgent...")
    await strategy_agent._initialize()

    # 3. 检查策略是否加载
    logger.info("\n3. 检查策略加载状态...")
    logger.info(f"已加载策略: {list(strategy_agent._strategies.keys())}")
    logger.info(f"活跃策略: {strategy_agent._active_strategies}")

    # 4. 检查订阅的交易对
    logger.info(f"\n4. 订阅的交易对: {strategy_agent._subscribed_instruments}")

    # 5. 获取市场数据
    logger.info("\n5. 获取市场数据...")
    market_data = {
        "inst_id": "BTC-USDT",
        "price": 74000.0,
        "timestamp": 1776245984.112,
    }
    logger.info(f"模拟市场数据: {market_data}")

    # 6. 直接调用策略execute方法
    logger.info("\n6. 直接调用策略execute方法...")
    if "NuclearDynamicsStrategy" in strategy_agent._strategies:
        strategy = strategy_agent._strategies["NuclearDynamicsStrategy"]
        logger.info(f"策略实例: {strategy}")
        logger.info(f"策略类: {strategy.__class__.__name__}")

        # 调用execute
        signal = strategy.execute(market_data)
        logger.info(f"策略返回的信号: {signal}")

        if signal:
            logger.info("✅ 策略成功生成信号!")
        else:
            logger.error("❌ 策略返回None，没有生成信号!")
    else:
        logger.error("❌ NuclearDynamicsStrategy未加载!")

    # 7. 通过StrategyAgent执行策略
    logger.info("\n7. 通过StrategyAgent执行策略...")
    if "NuclearDynamicsStrategy" in strategy_agent._strategies:
        strategy = strategy_agent._strategies["NuclearDynamicsStrategy"]
        signal = strategy.execute(market_data)
        logger.info(f"通过StrategyAgent执行的信号: {signal}")

        # 处理信号
        if signal:
            logger.info("处理信号...")
            await strategy_agent._process_signal(signal)
            logger.info("✅ 信号处理完成!")

    # 8. 检查事件总线订阅
    logger.info("\n8. 检查事件总线订阅...")
    from core.events.event_bus import event_bus
    from core.events.event_types import EventType

    async_subscribers = event_bus._async_subscribers.get(EventType.STRATEGY_SIGNAL, [])
    logger.info(f"STRATEGY_SIGNAL事件的异步订阅者数量: {len(async_subscribers)}")
    for i, callback in enumerate(async_subscribers):
        logger.info(f"  订阅者 {i}: {callback.__name__ if hasattr(callback, '__name__') else callback}")

    logger.info("\n" + "=" * 60)
    logger.info("诊断完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(diagnose())