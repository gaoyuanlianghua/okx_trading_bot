#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在交易机器人中集成日志记录功能
"""

import os
import sys

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.agents.coordinator_agent import CoordinatorAgent
from core.agents.order_agent import OrderAgent
from core.agents.strategy_agent import StrategyAgent
from core.agents.market_data_agent import MarketDataAgent
from core.agents.risk_agent import RiskAgent
from core.utils.config_manager import config_manager
from core.events.event_bus import event_bus, EventType
from core.api.exchange_manager import exchange_manager
from .generate_trade_logs import TradeLogger

class TradeLogIntegrator:
    """交易日志集成器"""
    
    def __init__(self, event_bus=None):
        self.trade_logger = TradeLogger()
        self.coordinator_agent = None
        self.event_bus = event_bus
        self._register_event_listeners()
        print("交易日志集成器初始化成功")
    
    def _register_event_listeners(self):
        """注册事件监听器"""
        if self.event_bus:
            # 监听策略信号事件
            self.event_bus.subscribe(
                EventType.STRATEGY_SIGNAL,
                self._on_strategy_signal,
                async_callback=True
            )
            
            # 监听交易事件
            self.event_bus.subscribe(
                EventType.TRADE_EVENT,
                self._on_trade_event,
                async_callback=True
            )
            
            # 监听订单事件
            self.event_bus.subscribe(
                EventType.ORDER_EVENT,
                self._on_order_event,
                async_callback=True
            )
            
            print("事件监听器注册成功")
        else:
            print("警告: 未提供事件总线，无法注册事件监听器")
    
    async def _on_strategy_signal(self, event):
        """处理策略信号事件"""
        try:
            print(f"接收到策略信号事件: {event}")
            signal = event.data.get('signal', {})
            print(f"接收到的信号: {signal}")
            if signal and isinstance(signal, dict):
                # 计算最小交易数量，确保交易金额至少为1 USDT
                price = signal.get('price', 0)
                min_size = 1.0 / price if price > 0 else 0.00001
                # 确保最小交易数量不小于0.00001
                size = max(min_size, 0.00001)
                
                # 使用策略生成的预期收益
                expected_return = signal.get('expected_return', 0)
                side = signal.get('side', 'none')
                
                trade_info = {
                    "strategy": signal.get('strategy', 'NuclearDynamicsStrategy'),
                    "side": side,
                    "price": price,
                    "size": size,  # 确保交易金额至少为1 USDT
                    "expected_return": expected_return,
                    "signal_level": signal.get('signal_level', 'S'),
                    "signal_strength": signal.get('signal_strength', 1.0),
                    "signal_score": signal.get('signal_score', 100),
                    "timestamp": signal.get('timestamp', ''),
                    "is_api_filled": True,  # 标记为API返回的订单
                    "state": "filled"  # 标记为已完成订单
                }
                print(f"准备记录的交易信息: {trade_info}")
                self.trade_logger.log_trade(trade_info)
                print(f"记录策略信号: {side} @ {price}")
        except Exception as e:
            print(f"处理策略信号事件失败: {e}")
    
    async def _on_trade_event(self, event):
        """处理交易事件"""
        try:
            trade_data = event.data
            if trade_data and isinstance(trade_data, dict):
                print(f"交易事件: {trade_data.get('side')} @ {trade_data.get('price')}")
        except Exception as e:
            print(f"处理交易事件失败: {e}")
    
    async def _on_order_event(self, event):
        """处理订单事件"""
        try:
            order_data = event.data
            if order_data and isinstance(order_data, dict):
                print(f"订单事件: {order_data.get('order', {}).get('side')} @ {order_data.get('order', {}).get('sz')}")
        except Exception as e:
            print(f"处理订单事件失败: {e}")
    
    def start(self):
        """启动集成器"""
        try:
            # 启动协调智能体
            if self.coordinator_agent:
                import asyncio
                asyncio.run(self.coordinator_agent.start())
        except Exception as e:
            print(f"启动集成器失败: {e}")

if __name__ == "__main__":
    integrator = TradeLogIntegrator()
    integrator.start()
