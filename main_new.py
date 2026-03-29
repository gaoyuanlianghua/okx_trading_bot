"""
OKX交易机器人 - 主程序入口

新的架构实现，基于OKX API指南和策略系统
"""
import asyncio
import logging
import os
import sys
from typing import Dict, Any

# 创建日志目录
os.makedirs('logs', exist_ok=True)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/trading_bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 导入核心组件
from core import (
    EventBus, Event, EventType,
    BaseAgent, AgentConfig,
    MarketDataAgent, OrderAgent, RiskAgent, StrategyAgent, CoordinatorAgent,
    OKXRESTClient, OKXWebSocketClient
)


class TradingBot:
    """
    交易机器人主类
    
    负责：
    1. 初始化所有组件
    2. 管理智能体生命周期
    3. 处理系统启动和关闭
    """
    
    def __init__(self):
        """初始化交易机器人"""
        self.event_bus = EventBus()
        self.coordinator: CoordinatorAgent = None
        self.market_data_agent: MarketDataAgent = None
        self.order_agent: OrderAgent = None
        self.risk_agent: RiskAgent = None
        self.strategy_agent: StrategyAgent = None
        
        # API客户端
        self.rest_client: OKXRESTClient = None
        self.ws_client: OKXWebSocketClient = None
        
        # 运行状态
        self._running = False
        
        logger.info("交易机器人初始化完成")
    
    async def initialize(self, config: Dict[str, Any] = None):
        """
        初始化所有组件
        
        Args:
            config: 配置字典
        """
        config = config or {}
        
        # 获取API配置
        api_config = config.get('api', {})
        api_key = api_config.get('api_key', os.getenv('OKX_API_KEY', ''))
        api_secret = api_config.get('api_secret', os.getenv('OKX_API_SECRET', ''))
        passphrase = api_config.get('passphrase', os.getenv('OKX_PASSPHRASE', ''))
        is_test = api_config.get('is_test', True)
        
        # 创建API客户端
        self.rest_client = OKXRESTClient(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            is_test=is_test
        )
        
        self.ws_client = OKXWebSocketClient(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            is_test=is_test
        )
        
        # 创建协调智能体
        coordinator_config = AgentConfig(
            name='Coordinator',
            description='系统协调智能体'
        )
        self.coordinator = CoordinatorAgent(coordinator_config)
        
        # 创建市场数据智能体
        market_data_config = AgentConfig(
            name='MarketData',
            description='市场数据智能体'
        )
        self.market_data_agent = MarketDataAgent(
            config=market_data_config,
            rest_client=self.rest_client,
            ws_client=self.ws_client
        )
        
        # 创建订单智能体
        order_config = AgentConfig(
            name='Order',
            description='订单管理智能体'
        )
        self.order_agent = OrderAgent(
            config=order_config,
            rest_client=self.rest_client
        )
        
        # 创建风险管理智能体
        risk_config = AgentConfig(
            name='Risk',
            description='风险管理智能体'
        )
        self.risk_agent = RiskAgent(
            config=risk_config,
            rest_client=self.rest_client
        )
        
        # 创建策略智能体
        strategy_config = AgentConfig(
            name='Strategy',
            description='策略执行智能体'
        )
        self.strategy_agent = StrategyAgent(
            config=strategy_config,
            market_data_agent=self.market_data_agent,
            order_agent=self.order_agent
        )
        
        # 注册智能体到协调器
        self.coordinator.register_agent(self.coordinator)
        self.coordinator.register_agent(self.market_data_agent)
        self.coordinator.register_agent(self.order_agent)
        self.coordinator.register_agent(self.risk_agent)
        self.coordinator.register_agent(self.strategy_agent)
        
        logger.info("所有组件初始化完成")
    
    async def start(self):
        """启动交易机器人"""
        if self._running:
            logger.warning("交易机器人已在运行中")
            return
        
        self._running = True
        
        try:
            # 启动事件总线
            self.event_bus.start()
            
            # 启动协调智能体
            await self.coordinator.start()
            
            # 启动其他智能体
            await self.market_data_agent.start()
            await self.order_agent.start()
            await self.risk_agent.start()
            await self.strategy_agent.start()
            
            # 连接WebSocket
            await self.ws_client.connect()
            
            # 激活默认策略
            await self.strategy_agent.activate_strategy('DynamicsStrategy')
            
            logger.info("交易机器人启动成功")
            
            # 发布系统启动事件
            await self.event_bus.publish_async(Event(
                type=EventType.SYSTEM_STARTUP,
                source='trading_bot',
                data={'status': 'started'}
            ))
            
            # 保持运行
            while self._running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"交易机器人运行错误: {e}")
            await self.stop()
    
    async def stop(self):
        """停止交易机器人"""
        if not self._running:
            return
        
        self._running = False
        logger.info("正在停止交易机器人...")
        
        try:
            # 停止所有智能体
            if self.strategy_agent:
                await self.strategy_agent.stop()
            if self.risk_agent:
                await self.risk_agent.stop()
            if self.order_agent:
                await self.order_agent.stop()
            if self.market_data_agent:
                await self.market_data_agent.stop()
            if self.coordinator:
                await self.coordinator.stop()
            
            # 关闭API客户端
            if self.ws_client:
                await self.ws_client.close()
            if self.rest_client:
                await self.rest_client.close()
            
            # 停止事件总线
            self.event_bus.stop()
            
            logger.info("交易机器人已停止")
            
        except Exception as e:
            logger.error(f"停止交易机器人时出错: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            'running': self._running,
            'coordinator': self.coordinator.get_status() if self.coordinator else None,
            'agents': self.coordinator.get_all_agents_status() if self.coordinator else [],
            'trading_summary': self.get_trading_summary() if self.coordinator else None
        }
    
    def get_trading_summary(self) -> Dict[str, Any]:
        """获取交易摘要"""
        if self.coordinator and hasattr(self.coordinator, 'get_trading_summary'):
            return self.coordinator.get_trading_summary()
        return {}


async def main():
    """主函数"""
    # 创建日志目录
    os.makedirs('logs', exist_ok=True)
    
    # 创建交易机器人
    bot = TradingBot()
    
    try:
        # 初始化
        await bot.initialize({
            'api': {
                'is_test': True  # 默认使用模拟盘
            }
        })
        
        # 启动
        await bot.start()
        
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止...")
        await bot.stop()
    except Exception as e:
        logger.error(f"主程序错误: {e}")
        await bot.stop()


if __name__ == '__main__':
    # 运行主程序
    asyncio.run(main())
