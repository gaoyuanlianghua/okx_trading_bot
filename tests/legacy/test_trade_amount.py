#!/usr/bin/env python3
"""
测试交易金额控制功能

该脚本用于验证系统是否正确处理交易金额配置，包括固定交易金额和基于可用余额的比例。
"""

import asyncio
import logging
import sys
from decimal import Decimal

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 导入核心组件
from core.config.env_manager import env_manager
from core.agents.coordinator_agent import CoordinatorAgent
from core.agents.base_agent import AgentConfig
from core.events.event_bus import event_bus
from core import Event, EventType

async def test_trade_amount_control():
    """测试交易金额控制功能"""
    logger.info("开始测试交易金额控制功能")
    
    # 初始化环境管理器
    env_info = env_manager.get_env_info()
    logger.info(f"当前环境: {env_info['current_env']}")
    logger.info(f"模拟盘模式: {env_info['is_test']}")
    
    # 获取交易配置
    trading_config = env_manager.get_trading_config()
    fixed_trade_amount = trading_config.get('fixed_trade_amount', 10)
    trade_amount_percentage = trading_config.get('trade_amount_percentage', 0.1)
    min_order_amount = trading_config.get('min_order_amount', 1)
    max_trade_amount = trading_config.get('max_position_size', 1000)
    
    logger.info(f"固定交易金额: {fixed_trade_amount} USDT")
    logger.info(f"交易金额占可用余额的比例: {trade_amount_percentage * 100:.1f}%")
    logger.info(f"最小订单金额: {min_order_amount} USDT")
    logger.info(f"最大交易金额: {max_trade_amount} USDT")
    
    # 模拟策略信号
    test_signals = [
        {
            "strategy": "NuclearDynamicsStrategy",
            "side": "buy",
            "signal_level": "S",
            "signal_strength": 1.0,
            "signal_score": 100,
            "price": 73837.4,
            "timestamp": "2026-04-15T23:57:46.029620",
            "expected_return": 0.02,
            "inst_id": "BTC-USDT"
        },
        {
            "strategy": "NuclearDynamicsStrategy",
            "side": "sell",
            "signal_level": "S",
            "signal_strength": 1.0,
            "signal_score": 100,
            "price": 73837.4,
            "timestamp": "2026-04-15T23:57:46.029620",
            "expected_return": 0.02,
            "inst_id": "BTC-USDT"
        },
        {
            "strategy": "NuclearDynamicsStrategy",
            "side": "buy",
            "signal_level": "S",
            "signal_strength": 1.0,
            "signal_score": 100,
            "price": 3691.87,
            "timestamp": "2026-04-15T23:57:46.029620",
            "expected_return": 0.02,
            "inst_id": "ETH-USDT"
        }
    ]
    
    # 创建协调智能体
    coordinator_config = AgentConfig(
        name="Coordinator", description="系统协调智能体"
    )
    coordinator = CoordinatorAgent(coordinator_config)
    
    # 启动协调智能体
    await coordinator.start()
    
    # 发送测试信号
    for i, signal in enumerate(test_signals):
        logger.info(f"发送测试信号 {i+1}: {signal['side']} {signal['inst_id']} @ {signal['price']}")
        event = Event(
            type=EventType.STRATEGY_SIGNAL,
            source="test_script",
            data={"signal": signal}
        )
        await event_bus.publish_async(event)
        await asyncio.sleep(2)  # 等待信号处理
    
    # 停止协调智能体
    await coordinator.stop()
    
    logger.info("交易金额控制功能测试完成")

if __name__ == "__main__":
    # 运行测试
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_trade_amount_control())
    loop.close()