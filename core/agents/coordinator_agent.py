"""
协调智能体 - 负责智能体间协调
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base_agent import BaseAgent, AgentConfig, AgentStatus
from core.events.event_bus import Event, EventType
from core.events.agent_communication import Message, MessageType, MessageTemplates

logger = logging.getLogger(__name__)


class CoordinatorAgent(BaseAgent):
    """
    协调智能体
    
    职责：
    1. 管理所有智能体的生命周期
    2. 协调智能体间的通信
    3. 监控系统健康状态
    4. 处理系统级决策
    """
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        
        # 管理的智能体
        self._agents: Dict[str, BaseAgent] = {}
        
        # 系统状态
        self._system_health = 'healthy'  # healthy/degraded/unhealthy
        self._system_stats = {
            'start_time': datetime.now(),
            'total_messages': 0,
            'total_errors': 0
        }
        
        # 决策配置
        self._auto_recovery = True
        self._emergency_stop_threshold = 5  # 连续错误阈值
        
        logger.info(f"协调智能体初始化完成: {self.agent_id}")
    
    async def _initialize(self):
        """初始化"""
        # 订阅系统事件
        self.event_bus.subscribe(EventType.AGENT_REGISTERED, self._on_agent_registered, async_callback=True)
        self.event_bus.subscribe(EventType.AGENT_UNREGISTERED, self._on_agent_unregistered, async_callback=True)
        self.event_bus.subscribe(EventType.SYSTEM_ERROR, self._on_system_error, async_callback=True)
        self.event_bus.subscribe(EventType.STRATEGY_SIGNAL, self._on_strategy_signal, async_callback=True)
        self.event_bus.subscribe(EventType.RISK_ALERT, self._on_risk_alert, async_callback=True)
        
        logger.info("协调智能体初始化完成")
    
    async def _cleanup(self):
        """清理"""
        # 停止所有管理的智能体
        for agent_id, agent in list(self._agents.items()):
            await agent.stop()
        
        self._agents.clear()
        logger.info("协调智能体已清理")
    
    async def _execute_cycle(self):
        """执行周期"""
        # 检查系统健康
        await self._check_system_health()
        
        # 协调智能体间通信
        await self._coordinate_agents()
        
        await asyncio.sleep(5)
    
    async def _check_system_health(self):
        """检查系统健康"""
        healthy_count = 0
        unhealthy_count = 0
        
        for agent_id, agent in self._agents.items():
            if agent.is_healthy():
                healthy_count += 1
            else:
                unhealthy_count += 1
                
                # 尝试恢复
                if self._auto_recovery and agent.status == AgentStatus.ERROR:
                    logger.info(f"尝试恢复智能体: {agent_id}")
                    await agent.start()
        
        # 更新系统健康状态
        total = len(self._agents)
        if total > 0:
            health_ratio = healthy_count / total
            if health_ratio >= 0.8:
                self._system_health = 'healthy'
            elif health_ratio >= 0.5:
                self._system_health = 'degraded'
            else:
                self._system_health = 'unhealthy'
    
    async def _coordinate_agents(self):
        """协调智能体间通信"""
        # 这里可以实现更复杂的协调逻辑
        pass
    
    async def _on_agent_registered(self, event: Event):
        """处理智能体注册事件"""
        agent_id = event.data.get('agent_id')
        name = event.data.get('name')
        logger.info(f"智能体注册: {name} ({agent_id})")
    
    async def _on_agent_unregistered(self, event: Event):
        """处理智能体注销事件"""
        agent_id = event.data.get('agent_id')
        logger.info(f"智能体注销: {agent_id}")
    
    async def _on_system_error(self, event: Event):
        """处理系统错误"""
        self._system_stats['total_errors'] += 1
        logger.error(f"系统错误: {event.data}")
    
    async def _on_strategy_signal(self, event: Event):
        """处理策略信号"""
        signal = event.data.get('signal', {})
        logger.info(f"收到策略信号: {signal}")
        
        # 这里可以实现信号路由逻辑
        # 例如：将信号发送给订单智能体执行
    
    async def _on_risk_alert(self, event: Event):
        """处理风险警报"""
        logger.warning(f"收到风险警报: {event.data}")
        
        # 根据风险等级采取相应措施
        level = event.data.get('level', 'low')
        if level == 'critical':
            logger.error("系统风险等级为critical，执行紧急停止")
            await self._emergency_stop()
    
    async def _emergency_stop(self):
        """紧急停止"""
        logger.critical("执行系统紧急停止")
        
        # 停止所有智能体
        for agent_id, agent in self._agents.items():
            await agent.stop()
        
        # 发布系统关闭事件
        await self.event_bus.publish_async(Event(
            type=EventType.SYSTEM_SHUTDOWN,
            source=self.agent_id,
            data={'reason': 'emergency_stop'}
        ))
    
    # ========== 公共接口 ==========
    
    def register_agent(self, agent: BaseAgent):
        """
        注册智能体
        
        Args:
            agent: 智能体实例
        """
        self._agents[agent.agent_id] = agent
        logger.info(f"注册智能体: {agent.name} ({agent.agent_id})")
    
    def unregister_agent(self, agent_id: str):
        """
        注销智能体
        
        Args:
            agent_id: 智能体ID
        """
        if agent_id in self._agents:
            del self._agents[agent_id]
            logger.info(f"注销智能体: {agent_id}")
    
    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """
        获取智能体
        
        Args:
            agent_id: 智能体ID
            
        Returns:
            Optional[BaseAgent]: 智能体实例
        """
        return self._agents.get(agent_id)
    
    def get_all_agents_status(self) -> List[Dict]:
        """获取所有智能体状态"""
        return [agent.get_status() for agent in self._agents.values()]
    
    def get_trading_summary(self) -> Dict[str, Any]:
        """
        获取交易摘要信息
        
        Returns:
            Dict: 包含交易历史、收益和账户信息的摘要
        """
        summary = {
            'total_trades': 0,
            'total_pnl': 0.0,
            'total_fees': 0.0,
            'account_info': None,
            'asset_distribution': {},
            'trade_history': []
        }
        
        # 收集各智能体的信息
        for agent_id, agent in self._agents.items():
            # 订单智能体 - 交易历史和收益
            if hasattr(agent, 'get_trade_history') and hasattr(agent, 'get_pnl'):
                summary['trade_history'] = agent.get_trade_history()
                summary['total_trades'] = len(summary['trade_history'])
                
                pnl_info = agent.get_pnl()
                summary['total_pnl'] = pnl_info.get('total_pnl', 0.0)
                summary['total_fees'] = pnl_info.get('total_fees', 0.0)
            
            # 风险管理智能体 - 账户信息
            if hasattr(agent, 'get_account_info') and hasattr(agent, 'get_asset_distribution'):
                summary['account_info'] = agent.get_account_info()
                summary['asset_distribution'] = agent.get_asset_distribution()
        
        return summary
    
    async def broadcast_command(self, command: str, params: Dict = None):
        """
        广播命令给所有智能体
        
        Args:
            command: 命令名称
            params: 命令参数
        """
        for agent_id in self._agents.keys():
            msg = Message.create_command(
                sender=self.agent_id,
                receiver=agent_id,
                command_type=getattr(MessageType, f'COMMAND_{command.upper()}', MessageType.COMMAND_START),
                payload=params or {}
            )
            await self.send_message(msg)
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        base_status = super().get_status()
        base_status.update({
            'system_health': self._system_health,
            'registered_agents': list(self._agents.keys()),
            'agent_count': len(self._agents),
            'system_stats': self._system_stats
        })
        return base_status
