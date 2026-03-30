"""
事件系统模块 - 提供智能体间通信的基础设施
"""

from .event_bus import EventBus, Event, EventType
from .agent_communication import AgentCommunicationProtocol, Message, MessageType

__all__ = [
    "EventBus",
    "Event",
    "EventType",
    "AgentCommunicationProtocol",
    "Message",
    "MessageType",
]
