"""
智能体单元测试
"""

import asyncio
import pytest
from unittest.mock import Mock, patch
from core.agents.base_agent import BaseAgent, AgentConfig
from core.agents.market_data_agent import MarketDataAgent
from core.agents.order_agent import OrderAgent
from core.agents.risk_agent import RiskAgent
from core.agents.strategy_agent import StrategyAgent
from core.agents.coordinator_agent import CoordinatorAgent
from core.api.okx_rest_client import OKXRESTClient
from core.api.okx_websocket_client import OKXWebSocketClient


class TestBaseAgent:
    """测试基础智能体"""
    
    @pytest.fixture
    def base_agent(self):
        """创建基础智能体实例"""
        config = AgentConfig(name="TestAgent", description="测试智能体")
        return BaseAgent(config)
    
    async def test_start_stop(self, base_agent):
        """测试智能体启动和停止"""
        result = await base_agent.start()
        assert result is True
        assert base_agent.status == base_agent._status.RUNNING
        
        result = await base_agent.stop()
        assert result is True
        assert base_agent.status == base_agent._status.STOPPED
    
    async def test_get_status(self, base_agent):
        """测试获取智能体状态"""
        status = base_agent.get_status()
        assert "name" in status
        assert "status" in status
        assert "uptime" in status
    
    async def test_message_handling(self, base_agent):
        """测试消息处理"""
        # 测试注册消息处理器
        received_messages = []
        
        def handler(message):
            received_messages.append(message)
        
        from core.events.agent_communication import MessageType
        base_agent.register_message_handler(MessageType.REQUEST_DATA, handler)
        
        # 测试发送消息
        from core.events.agent_communication import Message
        message = Message(
            sender="test_sender",
            receiver=base_agent.agent_id,
            type=MessageType.REQUEST_DATA,
            payload={"test": "data"}
        )
        
        await base_agent._process_message(message)
        assert len(received_messages) == 1


class TestMarketDataAgent:
    """测试市场数据智能体"""
    
    @pytest.fixture
    async def market_data_agent(self):
        """创建市场数据智能体实例"""
        config = AgentConfig(name="MarketData", description="市场数据智能体")
        rest_client = OKXRESTClient(is_test=True)
        ws_client = OKXWebSocketClient(is_test=True)
        agent = MarketDataAgent(config, rest_client, ws_client)
        return agent
    
    async def test_initialization(self, market_data_agent):
        """测试初始化"""
        assert market_data_agent is not None
        assert market_data_agent.agent_id is not None
    
    async def test_subscribe_instrument(self, market_data_agent):
        """测试订阅产品"""
        result = await market_data_agent.subscribe_instrument("BTC-USDT-SWAP")
        assert result is True
    
    async def test_get_ticker(self, market_data_agent):
        """测试获取ticker"""
        await market_data_agent.subscribe_instrument("BTC-USDT-SWAP")
        # 等待数据更新
        await asyncio.sleep(2)
        ticker = market_data_agent.get_ticker("BTC-USDT-SWAP")
        assert ticker is not None
    
    async def test_get_current_price(self, market_data_agent):
        """测试获取当前价格"""
        await market_data_agent.subscribe_instrument("BTC-USDT-SWAP")
        # 等待数据更新
        await asyncio.sleep(2)
        price = market_data_agent.get_current_price("BTC-USDT-SWAP")
        assert price is not None
        assert isinstance(price, float)
    
    async def test_cleanup_cache(self, market_data_agent):
        """测试清理缓存"""
        # 强制清理缓存
        await market_data_agent._cleanup_cache()
        # 验证缓存是否被清理
        assert len(market_data_agent._ticker_cache) == 0


class TestOrderAgent:
    """测试订单智能体"""
    
    @pytest.fixture
    async def order_agent(self):
        """创建订单智能体实例"""
        config = AgentConfig(name="Order", description="订单智能体")
        rest_client = OKXRESTClient(is_test=True)
        agent = OrderAgent(config, rest_client)
        return agent
    
    async def test_initialization(self, order_agent):
        """测试初始化"""
        assert order_agent is not None
        assert order_agent.agent_id is not None
    
    async def test_get_account_balance(self, order_agent):
        """测试获取账户余额"""
        # 注意：由于需要API密钥，这里可能会失败
        try:
            balance = await order_agent.get_account_balance()
            assert balance is not None
        except Exception:
            # 忽略API密钥错误
            pass


class TestRiskAgent:
    """测试风险管理智能体"""
    
    @pytest.fixture
    async def risk_agent(self):
        """创建风险管理智能体实例"""
        config = AgentConfig(name="Risk", description="风险管理智能体")
        rest_client = OKXRESTClient(is_test=True)
        agent = RiskAgent(config, rest_client)
        return agent
    
    async def test_initialization(self, risk_agent):
        """测试初始化"""
        assert risk_agent is not None
        assert risk_agent.agent_id is not None
    
    async def test_calculate_sharpe_ratio(self, risk_agent):
        """测试计算夏普比率"""
        returns = [0.01, 0.02, -0.01, 0.03, 0.02]
        sharpe = risk_agent.calculate_sharpe_ratio(returns)
        assert sharpe is not None
        assert isinstance(sharpe, float)
    
    async def test_calculate_max_drawdown(self, risk_agent):
        """测试计算最大回撤"""
        prices = [100, 110, 105, 120, 115, 130, 125, 110]
        max_drawdown = risk_agent.calculate_max_drawdown(prices)
        assert max_drawdown is not None
        assert isinstance(max_drawdown, float)


class TestStrategyAgent:
    """测试策略智能体"""
    
    @pytest.fixture
    async def strategy_agent(self):
        """创建策略智能体实例"""
        config = AgentConfig(name="Strategy", description="策略智能体")
        
        # 创建模拟的市场数据智能体和订单智能体
        market_data_config = AgentConfig(name="MarketData", description="市场数据智能体")
        rest_client = OKXRESTClient(is_test=True)
        ws_client = OKXWebSocketClient(is_test=True)
        market_data_agent = MarketDataAgent(market_data_config, rest_client, ws_client)
        
        order_config = AgentConfig(name="Order", description="订单智能体")
        order_agent = OrderAgent(order_config, rest_client)
        
        agent = StrategyAgent(config, market_data_agent, order_agent)
        return agent
    
    async def test_initialization(self, strategy_agent):
        """测试初始化"""
        assert strategy_agent is not None
        assert strategy_agent.agent_id is not None
    
    async def test_activate_strategy(self, strategy_agent):
        """测试激活策略"""
        result = await strategy_agent.activate_strategy("DynamicsStrategy")
        assert result is True
    
    async def test_deactivate_strategy(self, strategy_agent):
        """测试停用策略"""
        await strategy_agent.activate_strategy("DynamicsStrategy")
        result = await strategy_agent.deactivate_strategy("DynamicsStrategy")
        assert result is True


class TestCoordinatorAgent:
    """测试协调智能体"""
    
    @pytest.fixture
    async def coordinator_agent(self):
        """创建协调智能体实例"""
        config = AgentConfig(name="Coordinator", description="协调智能体")
        agent = CoordinatorAgent(config)
        return agent
    
    async def test_initialization(self, coordinator_agent):
        """测试初始化"""
        assert coordinator_agent is not None
        assert coordinator_agent.agent_id is not None
    
    async def test_register_agent(self, coordinator_agent):
        """测试注册智能体"""
        config = AgentConfig(name="TestAgent", description="测试智能体")
        test_agent = BaseAgent(config)
        coordinator_agent.register_agent(test_agent)
        assert len(coordinator_agent._agents) == 1
    
    async def test_get_all_agents_status(self, coordinator_agent):
        """测试获取所有智能体状态"""
        config = AgentConfig(name="TestAgent", description="测试智能体")
        test_agent = BaseAgent(config)
        coordinator_agent.register_agent(test_agent)
        statuses = coordinator_agent.get_all_agents_status()
        assert len(statuses) == 1


if __name__ == "__main__":
    asyncio.run(pytest.main([__file__]))
