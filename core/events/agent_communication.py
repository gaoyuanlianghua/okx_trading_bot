"""
智能体通信协议 - 定义智能体间的消息格式和通信规范
"""
import json
import time
import uuid
from enum import Enum, auto
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


class MessageType(Enum):
    """消息类型枚举"""
    # 命令消息
    COMMAND_START = auto()               # 启动命令
    COMMAND_STOP = auto()                # 停止命令
    COMMAND_PAUSE = auto()               # 暂停命令
    COMMAND_RESUME = auto()              # 恢复命令
    COMMAND_RESTART = auto()             # 重启命令
    
    # 请求/响应消息
    REQUEST_DATA = auto()                # 数据请求
    RESPONSE_DATA = auto()               # 数据响应
    REQUEST_STATUS = auto()              # 状态请求
    RESPONSE_STATUS = auto()             # 状态响应
    
    # 通知消息
    NOTIFY_STATUS_CHANGE = auto()        # 状态变更通知
    NOTIFY_ERROR = auto()                # 错误通知
    NOTIFY_WARNING = auto()              # 警告通知
    NOTIFY_INFO = auto()                 # 信息通知
    
    # 协调消息
    COORDINATE_TASK = auto()             # 任务协调
    COORDINATE_DECISION = auto()         # 决策协调
    COORDINATE_CONFLICT = auto()         # 冲突协调
    
    # 心跳消息
    HEARTBEAT = auto()                   # 心跳
    HEARTBEAT_RESPONSE = auto()          # 心跳响应
    
    # 广播消息
    BROADCAST = auto()                   # 广播消息
    
    # 自定义消息
    CUSTOM = auto()                      # 自定义消息


class MessagePriority(Enum):
    """消息优先级"""
    CRITICAL = 0      # 紧急 - 立即处理
    HIGH = 1          # 高优先级
    NORMAL = 2        # 普通优先级
    LOW = 3           # 低优先级
    BACKGROUND = 4    # 后台处理


@dataclass
class Message:
    """
    智能体消息数据类
    
    用于智能体间的标准化通信
    """
    # 消息标识
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None  # 关联消息ID（用于请求-响应模式）
    
    # 消息路由
    sender: str = "unknown"               # 发送者ID
    receiver: Optional[str] = None        # 接收者ID（None表示广播）
    
    # 消息内容
    type: MessageType = MessageType.CUSTOM
    priority: MessagePriority = MessagePriority.NORMAL
    payload: Dict[str, Any] = field(default_factory=dict)
    
    # 时间戳
    timestamp: float = field(default_factory=time.time)
    ttl: int = 60                         # 消息生存时间（秒）
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """检查消息是否过期"""
        return time.time() - self.timestamp > self.ttl
    
    def is_broadcast(self) -> bool:
        """检查是否为广播消息"""
        return self.receiver is None
    
    def is_response(self) -> bool:
        """检查是否为响应消息"""
        return self.type in [
            MessageType.RESPONSE_DATA,
            MessageType.RESPONSE_STATUS,
            MessageType.HEARTBEAT_RESPONSE
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'message_id': self.message_id,
            'correlation_id': self.correlation_id,
            'sender': self.sender,
            'receiver': self.receiver,
            'type': self.type.name,
            'priority': self.priority.name,
            'payload': self.payload,
            'timestamp': self.timestamp,
            'ttl': self.ttl,
            'metadata': self.metadata
        }
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """从字典创建消息"""
        return cls(
            message_id=data.get('message_id', str(uuid.uuid4())),
            correlation_id=data.get('correlation_id'),
            sender=data.get('sender', 'unknown'),
            receiver=data.get('receiver'),
            type=MessageType[data.get('type', 'CUSTOM')],
            priority=MessagePriority[data.get('priority', 'NORMAL')],
            payload=data.get('payload', {}),
            timestamp=data.get('timestamp', time.time()),
            ttl=data.get('ttl', 60),
            metadata=data.get('metadata', {})
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """从JSON字符串创建消息"""
        return cls.from_dict(json.loads(json_str))
    
    @classmethod
    def create_command(cls, sender: str, receiver: str, command_type: MessageType,
                      payload: Dict[str, Any] = None, priority: MessagePriority = MessagePriority.HIGH) -> 'Message':
        """
        创建命令消息
        
        Args:
            sender: 发送者ID
            receiver: 接收者ID
            command_type: 命令类型
            payload: 命令参数
            priority: 优先级
        """
        return cls(
            sender=sender,
            receiver=receiver,
            type=command_type,
            priority=priority,
            payload=payload or {}
        )
    
    @classmethod
    def create_request(cls, sender: str, receiver: str, request_type: MessageType,
                      payload: Dict[str, Any] = None, 
                      priority: MessagePriority = MessagePriority.NORMAL) -> 'Message':
        """
        创建请求消息
        
        Args:
            sender: 发送者ID
            receiver: 接收者ID
            request_type: 请求类型
            payload: 请求参数
            priority: 优先级
        """
        return cls(
            sender=sender,
            receiver=receiver,
            type=request_type,
            priority=priority,
            payload=payload or {}
        )
    
    @classmethod
    def create_response(cls, sender: str, receiver: str, request_message: 'Message',
                       payload: Dict[str, Any] = None) -> 'Message':
        """
        创建响应消息
        
        Args:
            sender: 发送者ID
            receiver: 接收者ID
            request_message: 请求消息
            payload: 响应数据
        """
        response_type = MessageType.RESPONSE_DATA
        if request_message.type == MessageType.REQUEST_STATUS:
            response_type = MessageType.RESPONSE_STATUS
        
        return cls(
            sender=sender,
            receiver=receiver,
            type=response_type,
            priority=request_message.priority,
            payload=payload or {},
            correlation_id=request_message.message_id
        )
    
    @classmethod
    def create_notification(cls, sender: str, notification_type: MessageType,
                           payload: Dict[str, Any] = None,
                           priority: MessagePriority = MessagePriority.NORMAL) -> 'Message':
        """
        创建通知消息（广播）
        
        Args:
            sender: 发送者ID
            notification_type: 通知类型
            payload: 通知内容
            priority: 优先级
        """
        return cls(
            sender=sender,
            receiver=None,  # 广播
            type=notification_type,
            priority=priority,
            payload=payload or {}
        )
    
    @classmethod
    def create_heartbeat(cls, sender: str) -> 'Message':
        """创建心跳消息"""
        return cls(
            sender=sender,
            type=MessageType.HEARTBEAT,
            priority=MessagePriority.LOW,
            payload={'status': 'alive'}
        )


class AgentCommunicationProtocol:
    """
    智能体通信协议
    
    提供标准化的智能体间通信接口
    """
    
    # 协议版本
    VERSION = "1.0.0"
    
    # 默认超时时间（秒）
    DEFAULT_TIMEOUT = 30
    
    @staticmethod
    def validate_message(message: Message) -> bool:
        """
        验证消息格式
        
        Args:
            message: 消息对象
            
        Returns:
            bool: 是否有效
        """
        if not message.message_id:
            return False
        
        if not message.sender:
            return False
        
        if message.is_expired():
            return False
        
        return True
    
    @staticmethod
    def create_error_response(sender: str, receiver: str, request_message: Message,
                             error_code: str, error_message: str) -> Message:
        """
        创建错误响应
        
        Args:
            sender: 发送者ID
            receiver: 接收者ID
            request_message: 请求消息
            error_code: 错误码
            error_message: 错误信息
        """
        return Message.create_response(
            sender=sender,
            receiver=receiver,
            request_message=request_message,
            payload={
                'success': False,
                'error_code': error_code,
                'error_message': error_message
            }
        )
    
    @staticmethod
    def create_success_response(sender: str, receiver: str, request_message: Message,
                               data: Dict[str, Any] = None) -> Message:
        """
        创建成功响应
        
        Args:
            sender: 发送者ID
            receiver: 接收者ID
            request_message: 请求消息
            data: 响应数据
        """
        return Message.create_response(
            sender=sender,
            receiver=receiver,
            request_message=request_message,
            payload={
                'success': True,
                'data': data or {}
            }
        )


# 预定义的消息模板
class MessageTemplates:
    """消息模板类"""
    
    @staticmethod
    def start_agent(sender: str, receiver: str, config: Dict[str, Any] = None) -> Message:
        """启动智能体消息"""
        return Message.create_command(
            sender=sender,
            receiver=receiver,
            command_type=MessageType.COMMAND_START,
            payload={'config': config or {}}
        )
    
    @staticmethod
    def stop_agent(sender: str, receiver: str, reason: str = None) -> Message:
        """停止智能体消息"""
        return Message.create_command(
            sender=sender,
            receiver=receiver,
            command_type=MessageType.COMMAND_STOP,
            payload={'reason': reason}
        )
    
    @staticmethod
    def status_request(sender: str, receiver: str) -> Message:
        """状态请求消息"""
        return Message.create_request(
            sender=sender,
            receiver=receiver,
            request_type=MessageType.REQUEST_STATUS
        )
    
    @staticmethod
    def status_response(sender: str, receiver: str, request_message: Message,
                       status: str, details: Dict[str, Any] = None) -> Message:
        """状态响应消息"""
        return Message.create_response(
            sender=sender,
            receiver=receiver,
            request_message=request_message,
            payload={
                'status': status,
                'details': details or {}
            }
        )
    
    @staticmethod
    def error_notification(sender: str, error_code: str, error_message: str,
                          details: Dict[str, Any] = None) -> Message:
        """错误通知消息"""
        return Message.create_notification(
            sender=sender,
            notification_type=MessageType.NOTIFY_ERROR,
            payload={
                'error_code': error_code,
                'error_message': error_message,
                'details': details or {}
            },
            priority=MessagePriority.HIGH
        )
    
    @staticmethod
    def strategy_signal(sender: str, strategy_name: str, signal: Dict[str, Any]) -> Message:
        """策略信号消息"""
        return Message.create_notification(
            sender=sender,
            notification_type=MessageType.NOTIFY_INFO,
            payload={
                'event': 'strategy_signal',
                'strategy_name': strategy_name,
                'signal': signal
            },
            priority=MessagePriority.HIGH
        )
