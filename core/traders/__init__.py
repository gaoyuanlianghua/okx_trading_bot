"""
交易器模块 - 提供不同交易方式的统一接口
"""

from .base_trader import BaseTrader, TradeResult, PositionInfo, AccountInfo, RiskInfo
from .base_trader import TradeMode, TradeSide, OrderType, PositionSide
from .spot_trader import SpotTrader
from .margin_trader import MarginTrader
from .contract_trader import ContractTrader
from .options_trader import OptionsTrader
from .trader_manager import TraderManager, get_trader_manager, reset_trader_manager

__all__ = [
    'BaseTrader',
    'TradeResult',
    'PositionInfo',
    'AccountInfo',
    'RiskInfo',
    'TradeMode',
    'TradeSide',
    'OrderType',
    'PositionSide',
    'SpotTrader',
    'MarginTrader',
    'ContractTrader',
    'OptionsTrader',
    'TraderManager',
    'get_trader_manager',
    'reset_trader_manager',
]
