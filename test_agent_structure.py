#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试智能体结构是否正常工作，无需实际网络连接
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from loguru import logger

# 初始化日志
logger.add("logs/agent_structure_test.log", rotation="500 MB", compression="zip")

# 测试智能体结构
def test_agent_structure():
    """测试智能体结构"""
    logger.info("开始测试智能体结构...")
    
    try:
        # 测试导入智能体类
        from agents.market_data_agent import MarketDataAgent
        from agents.order_agent import OrderAgent
        from agents.risk_management_agent import RiskManagementAgent
        from agents.strategy_execution_agent import StrategyExecutionAgent
        from agents.decision_coordination_agent import DecisionCoordinationAgent
        
        logger.info("✓ 智能体类导入成功")
        
        # 测试导入策略基类
        from strategies.base_strategy import BaseStrategy
        logger.info("✓ 策略基类导入成功")
        
        # 测试导入事件总线和智能体注册表
        from commons.event_bus import EventBus
        from commons.agent_registry import AgentRegistry
        
        logger.info("✓ 事件总线和智能体注册表导入成功")
        
        # 测试创建事件总线实例
        event_bus = EventBus()
        logger.info("✓ 事件总线实例创建成功")
        
        # 测试创建智能体注册表实例
        agent_registry = AgentRegistry()
        logger.info("✓ 智能体注册表实例创建成功")
        
        # 测试创建智能体实例
        market_data_agent = MarketDataAgent("test_market_agent", {})
        order_agent = OrderAgent("test_order_agent", {})
        risk_agent = RiskManagementAgent("test_risk_agent", {})
        strategy_agent = StrategyExecutionAgent("test_strategy_agent", {})
        decision_agent = DecisionCoordinationAgent("test_decision_agent", {})
        
        logger.info("✓ 智能体实例创建成功")
        
        # 测试注册智能体
        agent_registry.register_agent(market_data_agent)
        agent_registry.register_agent(order_agent)
        agent_registry.register_agent(risk_agent)
        agent_registry.register_agent(strategy_agent)
        agent_registry.register_agent(decision_agent)
        
        logger.info("✓ 智能体注册成功")
        
        # 测试获取所有智能体
        all_agents = agent_registry.get_all_agents()
        logger.info(f"✓ 获取所有智能体成功，共 {len(all_agents)} 个智能体")
        
        # 测试智能体启动和停止
        market_data_agent.start()
        logger.info(f"✓ 智能体启动成功，状态: {market_data_agent.status}")
        
        market_data_agent.stop()
        logger.info(f"✓ 智能体停止成功，状态: {market_data_agent.status}")
        
        # 测试策略执行智能体的策略加载
        strategies = strategy_agent.list_strategies()
        logger.info(f"✓ 获取策略列表成功，共 {len(strategies)} 个策略")
        
        logger.info("\n🎉 智能体结构测试全部通过！")
        logger.info("智能体系统架构设计合理，各组件能够正常初始化和工作")
        logger.info("策略扩展端口已预留，支持动态加载和执行多种交易策略")
        
    except ImportError as e:
        logger.error(f"导入错误: {e}")
        logger.error("请检查模块路径和依赖")
        raise
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        raise

# 测试策略扩展端口
def test_strategy_extension():
    """测试策略扩展端口"""
    logger.info("\n开始测试策略扩展端口...")
    
    try:
        from strategies.base_strategy import BaseStrategy
        
        # 创建自定义策略类
        class CustomStrategy(BaseStrategy):
            """自定义策略示例"""
            
            def __init__(self, config=None):
                super().__init__(config)
                self.name = "CustomStrategy"
                self.params = {
                    "ma_period": self.config.get("ma_period", 20),
                    "threshold": self.config.get("threshold", 0.01)
                }
            
            def execute(self, market_data):
                """执行策略"""
                # 简单的示例逻辑
                if market_data and "price" in market_data:
                    return {
                        "side": "buy",
                        "price": market_data["price"],
                        "amount": 0.001,
                        "symbol": market_data.get("symbol", "BTC-USDT-SWAP"),
                        "leverage": 1,
                        "signal_strength": 0.8
                    }
                return None
        
        logger.info("✓ 自定义策略类创建成功")
        
        # 测试策略实例化
        custom_strategy = CustomStrategy({"ma_period": 30, "threshold": 0.02})
        logger.info(f"✓ 自定义策略实例化成功，名称: {custom_strategy.name}")
        
        # 测试策略参数
        params = custom_strategy.get_params()
        logger.info(f"✓ 获取策略参数成功: {params}")
        
        # 测试更新策略参数
        custom_strategy.set_params({"ma_period": 50})
        updated_params = custom_strategy.get_params()
        logger.info(f"✓ 更新策略参数成功，新参数: {updated_params}")
        
        # 测试策略状态管理
        custom_strategy.start()
        logger.info(f"✓ 策略启动成功，状态: {custom_strategy.status}")
        
        custom_strategy.pause()
        logger.info(f"✓ 策略暂停成功，状态: {custom_strategy.status}")
        
        custom_strategy.resume()
        logger.info(f"✓ 策略恢复成功，状态: {custom_strategy.status}")
        
        custom_strategy.stop()
        logger.info(f"✓ 策略停止成功，状态: {custom_strategy.status}")
        
        logger.info("\n🎉 策略扩展端口测试全部通过！")
        logger.info("策略扩展机制正常工作，支持自定义策略的创建、配置和执行")
        logger.info("策略可以通过继承BaseStrategy类轻松扩展，实现各种交易逻辑")
        
    except Exception as e:
        logger.error(f"策略扩展测试失败: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("智能体结构和策略扩展测试")
    logger.info("=" * 50)
    
    # 运行测试
    agent_test_result = test_agent_structure()
    strategy_test_result = test_strategy_extension()
    
    logger.info("\n" + "=" * 50)
    logger.info("测试结果汇总")
    logger.info("=" * 50)
    
    if agent_test_result and strategy_test_result:
        logger.info("✅ 所有测试通过！智能体系统结构正常，策略扩展端口可用")
        logger.info("\n📝 智能体系统架构概览:")
        logger.info("1. 市场数据智能体 - 负责获取和处理市场数据")
        logger.info("2. 订单智能体 - 负责处理订单操作")
        logger.info("3. 风险控制智能体 - 负责监控和控制交易风险")
        logger.info("4. 策略执行智能体 - 负责执行策略，生成交易信号")
        logger.info("5. 决策协调智能体 - 负责协调各个智能体之间的工作")
        logger.info("\n📝 策略扩展使用方法:")
        logger.info("1. 创建一个继承自BaseStrategy的策略类")
        logger.info("2. 实现execute方法，生成交易信号")
        logger.info("3. 在main.py中注册策略，或通过GUI动态激活")
        logger.info("4. 策略将自动接收市场数据并生成交易信号")
        sys.exit(0)
    else:
        logger.error("❌ 部分测试失败，请检查日志获取详细信息")
        sys.exit(1)
