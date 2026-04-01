import asyncio
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from core.events.event_bus import EventBus, EventType
from core.utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class NotificationRule:
    """通知规则类"""
    rule_id: str
    user_id: str
    event_type: str  # 事件类型，如 'trade_executed', 'price_alert', 'strategy_performance'
    condition: Dict[str, Any]  # 触发条件
    channels: List[str]  # 通知渠道，如 'email', 'sms', 'app'
    enabled: bool = True
    created_at: float = field(default_factory=time.time)

@dataclass
class Notification:
    """通知类"""
    notification_id: str
    user_id: str
    title: str
    message: str
    channels: List[str]
    priority: str  # 'low', 'medium', 'high'
    created_at: float = field(default_factory=time.time)
    delivered: bool = False
    delivered_at: Optional[float] = None

class SmartNotificationSystem:
    """智能通知系统"""
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        """初始化智能通知系统"""
        self.event_bus = event_bus
        self.rules: Dict[str, NotificationRule] = {}
        self.notifications: Dict[str, Notification] = {}
        self.notification_history: List[Notification] = []
        self.channel_handlers: Dict[str, Any] = {}
        self.is_running = False
        
        # 注册事件监听器
        if self.event_bus:
            self._register_event_listeners()
    
    def _register_event_listeners(self):
        """注册事件监听器"""
        events_to_listen = [
            EventType.ORDER_FILLED,
            EventType.STRATEGY_SIGNAL,
            EventType.RISK_ALERT
        ]
        
        for event_type in events_to_listen:
            self.event_bus.subscribe(event_type, self._handle_event)
    
    async def _handle_event(self, event):
        """处理事件"""
        try:
            event_type = event.type.name
            event_data = event.data
            
            # 查找匹配的规则
            matching_rules = [
                rule for rule in self.rules.values() 
                if rule.event_type == event_type and rule.enabled
            ]
            
            for rule in matching_rules:
                # 检查条件是否满足
                if self._check_condition(rule.condition, event_data):
                    # 生成通知
                    notification = self._generate_notification(rule, event_type, event_data)
                    if notification:
                        # 发送通知
                        await self.send_notification(notification)
        except Exception as e:
            logger.error(f"处理事件时出错: {e}")
    
    def _check_condition(self, condition: Dict[str, Any], event_data: Dict[str, Any]) -> bool:
        """检查条件是否满足"""
        # 这里实现条件检查逻辑
        # 例如，价格警报的条件检查
        if "price_threshold" in condition:
            if "price" in event_data:
                operator = condition.get("operator", "gt")
                threshold = condition["price_threshold"]
                price = event_data["price"]
                
                if operator == "gt" and price > threshold:
                    return True
                elif operator == "lt" and price < threshold:
                    return True
                elif operator == "eq" and price == threshold:
                    return True
        
        # 策略绩效条件检查
        if "performance_threshold" in condition:
            if "performance" in event_data:
                operator = condition.get("operator", "gt")
                threshold = condition["performance_threshold"]
                performance = event_data["performance"]
                
                if operator == "gt" and performance > threshold:
                    return True
                elif operator == "lt" and performance < threshold:
                    return True
        
        # 市场情绪条件检查
        if "sentiment_threshold" in condition:
            if "sentiment_score" in event_data:
                operator = condition.get("operator", "gt")
                threshold = condition["sentiment_threshold"]
                sentiment = event_data["sentiment_score"]
                
                if operator == "gt" and sentiment > threshold:
                    return True
                elif operator == "lt" and sentiment < threshold:
                    return True
        
        # 默认返回True，即没有条件时总是触发
        return True
    
    def _generate_notification(self, rule: NotificationRule, event_type: str, event_data: Dict[str, Any]) -> Optional[Notification]:
        """生成通知"""
        notification_id = f"notification_{int(time.time())}_{hash(str(event_data)) % 10000}"
        
        # 根据事件类型生成通知内容
        if event_type == "trade_executed":
            title = "交易执行通知"
            message = f"您的{event_data.get('side', '买入')}订单已执行，交易对: {event_data.get('symbol', '未知')}，价格: {event_data.get('price', '0')}，数量: {event_data.get('quantity', '0')}"
        elif event_type == "price_alert_triggered":
            title = "价格警报触发"
            message = f"{event_data.get('symbol', '未知')}价格达到{event_data.get('price', '0')}，触发警报"
        elif event_type == "strategy_performance_updated":
            title = "策略绩效更新"
            message = f"您的策略{event_data.get('strategy_name', '未知')}绩效更新: {event_data.get('performance', '0')}%"
        elif event_type == "market_sentiment_updated":
            title = "市场情绪更新"
            message = f"{event_data.get('cryptocurrency', '未知')}市场情绪: {event_data.get('sentiment_score', '0')}，置信度: {event_data.get('confidence', '0')}"
        elif event_type == "risk_threshold_exceeded":
            title = "风险阈值警报"
            message = f"风险指标超过阈值: {event_data.get('risk_type', '未知')}，当前值: {event_data.get('value', '0')}，阈值: {event_data.get('threshold', '0')}"
        else:
            title = "系统通知"
            message = f"发生事件: {event_type}"
        
        # 确定优先级
        priority = "medium"
        if event_type in ["risk_threshold_exceeded", "trade_executed"]:
            priority = "high"
        elif event_type in ["price_alert_triggered"]:
            priority = "high"
        
        return Notification(
            notification_id=notification_id,
            user_id=rule.user_id,
            title=title,
            message=message,
            channels=rule.channels,
            priority=priority
        )
    
    async def send_notification(self, notification: Notification):
        """发送通知"""
        try:
            # 保存通知
            self.notifications[notification.notification_id] = notification
            self.notification_history.append(notification)
            
            # 限制历史记录大小
            if len(self.notification_history) > 1000:
                self.notification_history = self.notification_history[-1000:]
            
            # 通过各个渠道发送通知
            for channel in notification.channels:
                if channel in self.channel_handlers:
                    try:
                        await self.channel_handlers[channel].send(notification)
                    except Exception as e:
                        logger.error(f"通过{channel}发送通知时出错: {e}")
                else:
                    logger.warning(f"未找到{channel}的处理程序")
            
            # 标记为已发送
            notification.delivered = True
            notification.delivered_at = time.time()
            
            logger.info(f"通知已发送: {notification.title}")
        except Exception as e:
            logger.error(f"发送通知时出错: {e}")
    
    def add_rule(self, rule: NotificationRule):
        """添加通知规则"""
        self.rules[rule.rule_id] = rule
        logger.info(f"添加通知规则: {rule.rule_id}")
    
    def remove_rule(self, rule_id: str):
        """删除通知规则"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            logger.info(f"删除通知规则: {rule_id}")
    
    def update_rule(self, rule_id: str, updates: Dict[str, Any]):
        """更新通知规则"""
        if rule_id in self.rules:
            rule = self.rules[rule_id]
            for key, value in updates.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)
            logger.info(f"更新通知规则: {rule_id}")
    
    def get_rules(self, user_id: Optional[str] = None) -> List[NotificationRule]:
        """获取通知规则"""
        if user_id:
            return [rule for rule in self.rules.values() if rule.user_id == user_id]
        return list(self.rules.values())
    
    def get_notifications(self, user_id: Optional[str] = None, limit: int = 50) -> List[Notification]:
        """获取通知"""
        if user_id:
            user_notifications = [n for n in self.notification_history if n.user_id == user_id]
            return user_notifications[-limit:]
        return self.notification_history[-limit:]
    
    def register_channel_handler(self, channel: str, handler: Any):
        """注册渠道处理程序"""
        self.channel_handlers[channel] = handler
        logger.info(f"注册渠道处理程序: {channel}")
    
    async def start(self):
        """启动通知系统"""
        self.is_running = True
        logger.info("智能通知系统已启动")
    
    async def stop(self):
        """停止通知系统"""
        self.is_running = False
        logger.info("智能通知系统已停止")
        
        # 清理资源
        for handler in self.channel_handlers.values():
            if hasattr(handler, "close"):
                try:
                    await handler.close()
                except Exception as e:
                    logger.error(f"关闭渠道处理程序时出错: {e}")