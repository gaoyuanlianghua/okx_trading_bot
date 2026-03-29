"""
风险管理智能体 - 负责风险控制
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List

from .base_agent import BaseAgent, AgentConfig
from core.events.event_bus import Event, EventType
from core.events.agent_communication import Message, MessageType
from core.api.okx_rest_client import OKXRESTClient

logger = logging.getLogger(__name__)


class RiskAgent(BaseAgent):
    """
    风险管理智能体
    
    职责：
    1. 监控账户风险
    2. 检查订单风险
    3. 管理仓位限制
    4. 触发风险警报
    """
    
    def __init__(self, config: AgentConfig, rest_client: OKXRESTClient = None):
        super().__init__(config)
        self.rest_client = rest_client
        
        # 风险参数
        self._risk_params = {
            'max_position_ratio': 0.8,      # 最大仓位比例
            'max_daily_loss': 0.05,         # 最大日亏损
            'max_order_amount': 10000,      # 最大订单金额
            'max_leverage': 10,             # 最大杠杆
            'stop_loss_ratio': 0.03,        # 止损比例
            'take_profit_ratio': 0.05       # 止盈比例
        }
        
        # 风险状态
        self._account_balance = 0
        self._positions = []
        self._daily_pnl = 0
        self._risk_level = 'low'  # low/medium/high/critical
        
        # 账户信息
        self._account_info = {
            'total_balance': 0.0,
            'available_balance': 0.0,
            'margin': 0.0,
            'unrealized_pnl': 0.0
        }
        
        # 资产分布
        self._asset_distribution = {}
        
        # 警报状态
        self._alerts = []
        
        logger.info(f"风险管理智能体初始化完成: {self.agent_id}")
    
    async def _initialize(self):
        """初始化"""
        self.register_message_handler(MessageType.REQUEST_DATA, self._handle_risk_check)
        
        # 订阅相关事件
        self.event_bus.subscribe(EventType.ORDER_CREATED, self._on_order_event, async_callback=True)
        self.event_bus.subscribe(EventType.RISK_ALERT, self._on_risk_alert, async_callback=True)
        
        logger.info("风险管理智能体初始化完成")
    
    async def _cleanup(self):
        """清理"""
        self._alerts.clear()
        logger.info("风险管理智能体已清理")
    
    async def _execute_cycle(self):
        """执行周期"""
        await self._update_account_info()
        await self._assess_risk()
        await asyncio.sleep(30)
    
    async def _update_account_info(self):
        """更新账户信息"""
        if not self.rest_client:
            return
        
        try:
            # 获取账户余额
            balance = await self.rest_client.get_account_balance()
            if balance:
                self._account_balance = float(balance.get('totalEq', 0))
                
                # 提取账户信息
                self._account_info = {
                    'total_balance': float(balance.get('totalEq', 0)),
                    'available_balance': float(balance.get('availBal', 0)),
                    'margin': float(balance.get('margin', 0)),
                    'unrealized_pnl': float(balance.get('upl', 0))
                }
                
                # 构建资产分布
                self._asset_distribution = {}
                if 'details' in balance:
                    for detail in balance['details']:
                        ccy = detail.get('ccy')
                        if ccy:
                            self._asset_distribution[ccy] = {
                                'balance': float(detail.get('bal', 0)),
                                'available': float(detail.get('availBal', 0))
                            }
            
            # 获取持仓
            positions = await self.rest_client.get_positions()
            self._positions = positions
            
        except Exception as e:
            logger.error(f"更新账户信息失败: {e}")
    
    async def _assess_risk(self):
        """评估风险"""
        # 计算仓位比例
        position_value = sum(
            float(pos.get('pos', 0)) * float(pos.get('avgPx', 0))
            for pos in self._positions
        )
        
        position_ratio = position_value / self._account_balance if self._account_balance > 0 else 0
        
        # 确定风险等级
        if position_ratio > self._risk_params['max_position_ratio']:
            self._risk_level = 'critical'
            await self._trigger_alert('仓位过高', position_ratio)
        elif position_ratio > 0.6:
            self._risk_level = 'high'
        elif position_ratio > 0.3:
            self._risk_level = 'medium'
        else:
            self._risk_level = 'low'
    
    async def _trigger_alert(self, reason: str, value: float):
        """触发警报"""
        alert = {
            'timestamp': asyncio.get_event_loop().time(),
            'reason': reason,
            'value': value,
            'level': self._risk_level
        }
        self._alerts.append(alert)
        logger.warning(f"风险警报: {reason} = {value}")
    
    async def _handle_risk_check(self, message: Message):
        """处理风险检查请求"""
        payload = message.payload
        check_type = payload.get('check_type')
        
        if check_type == 'order':
            result = await self.check_order_risk(payload.get('order', {}))
        elif check_type == 'account':
            result = await self.check_account_risk()
        else:
            result = {'allowed': False, 'reason': '未知检查类型'}
        
        response = Message.create_response(
            sender=self.agent_id,
            receiver=message.sender,
            request_message=message,
            payload=result
        )
        await self.send_message(response)
    
    async def _on_order_event(self, event: Event):
        """处理订单事件"""
        self.metrics.update_activity()
    
    async def _on_risk_alert(self, event: Event):
        """处理风险警报事件"""
        logger.warning(f"收到风险警报: {event.data}")
    
    # ========== 公共接口 ==========
    
    async def check_order_risk(self, order: Dict) -> Dict:
        """
        检查订单风险
        
        Args:
            order: 订单信息
            
        Returns:
            Dict: 检查结果
        """
        # 检查订单金额
        amount = float(order.get('sz', 0)) * float(order.get('px', 0))
        if amount > self._risk_params['max_order_amount']:
            return {'allowed': False, 'reason': f'订单金额超过限制: {amount}'}
        
        # 检查风险等级
        if self._risk_level == 'critical':
            return {'allowed': False, 'reason': '当前风险等级为critical，禁止新订单'}
        
        return {'allowed': True}
    
    async def check_account_risk(self) -> Dict:
        """
        检查账户风险
        
        Returns:
            Dict: 检查结果
        """
        return {
            'allowed': self._risk_level != 'critical',
            'risk_level': self._risk_level,
            'account_balance': self._account_balance,
            'position_count': len(self._positions)
        }
    
    def get_risk_params(self) -> Dict:
        """获取风险参数"""
        return self._risk_params.copy()
    
    def set_risk_params(self, params: Dict):
        """设置风险参数"""
        self._risk_params.update(params)
    
    def get_account_info(self) -> Dict[str, float]:
        """获取账户信息"""
        return self._account_info.copy()
    
    def get_asset_distribution(self) -> Dict[str, Dict]:
        """获取资产分布"""
        return self._asset_distribution.copy()
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        base_status = super().get_status()
        base_status.update({
            'risk_level': self._risk_level,
            'account_balance': self._account_balance,
            'position_count': len(self._positions),
            'alert_count': len(self._alerts),
            'account_info': self._account_info,
            'asset_distribution': self._asset_distribution
        })
        return base_status
