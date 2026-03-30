"""
实时参数调整器

根据实时市场情况动态调整策略参数
"""

import time
import numpy as np
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
import asyncio

from core.utils.logger import get_logger
from core.optimization.parameter_optimizer import ParameterOptimizer

logger = get_logger(__name__)


@dataclass
class MarketState:
    """市场状态"""
    volatility: float  # 波动率
    trend_strength: float  # 趋势强度
    liquidity: float  # 流动性
    market_regime: str  # 市场 regime (trending, range, volatile)
    timestamp: float  # 时间戳


class RealtimeParameterAdjuster:
    """
    实时参数调整器
    
    根据实时市场情况动态调整策略参数
    """
    
    def __init__(self, strategy_instance):
        """
        初始化实时参数调整器
        
        Args:
            strategy_instance: 策略实例
        """
        self.strategy = strategy_instance
        self.parameter_optimizer = ParameterOptimizer(type(strategy_instance))
        self.adjustment_history = []
        self.last_adjustment_time = 0
        self.adjustment_interval = 300  # 默认5分钟调整一次
        
        # 市场状态历史
        self.market_state_history = []
        self.max_market_state_history = 100
    
    async def adjust_parameters(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        调整策略参数
        
        Args:
            market_data: 市场数据
            
        Returns:
            Dict[str, Any]: 调整后的参数
        """
        # 检查是否需要调整
        current_time = time.time()
        if current_time - self.last_adjustment_time < self.adjustment_interval:
            return self.strategy.dynamics_params
        
        # 计算市场状态
        market_state = self._calculate_market_state(market_data)
        
        # 保存市场状态
        self._save_market_state(market_state)
        
        # 基于市场状态调整参数
        adjusted_params = self._adjust_params_based_on_market_state(market_state)
        
        # 更新策略参数
        self.strategy.dynamics_params.update(adjusted_params)
        
        # 记录调整历史
        self._record_adjustment(market_state, adjusted_params)
        
        # 更新最后调整时间
        self.last_adjustment_time = current_time
        
        logger.info(f"实时参数调整: {adjusted_params}")
        return adjusted_params
    
    def _calculate_market_state(self, market_data: Dict[str, Any]) -> MarketState:
        """
        计算市场状态
        
        Args:
            market_data: 市场数据
            
        Returns:
            MarketState: 市场状态
        """
        # 计算波动率
        volatility = self._calculate_volatility(market_data)
        
        # 计算趋势强度
        trend_strength = self._calculate_trend_strength(market_data)
        
        # 计算流动性
        liquidity = self._calculate_liquidity(market_data)
        
        # 确定市场 regime
        market_regime = self._determine_market_regime(volatility, trend_strength)
        
        return MarketState(
            volatility=volatility,
            trend_strength=trend_strength,
            liquidity=liquidity,
            market_regime=market_regime,
            timestamp=time.time()
        )
    
    def _calculate_volatility(self, market_data: Dict[str, Any]) -> float:
        """
        计算波动率
        
        Args:
            market_data: 市场数据
            
        Returns:
            float: 波动率
        """
        # 从策略的价格历史计算波动率
        if hasattr(self.strategy, "price_history") and len(self.strategy.price_history) > 10:
            returns = np.diff(np.log(self.strategy.price_history[-10:]))
            return np.std(returns)
        return 0.01  # 默认值
    
    def _calculate_trend_strength(self, market_data: Dict[str, Any]) -> float:
        """
        计算趋势强度
        
        Args:
            market_data: 市场数据
            
        Returns:
            float: 趋势强度 (-1 到 1)
        """
        # 从策略的价格历史计算趋势强度
        if hasattr(self.strategy, "price_history") and len(self.strategy.price_history) > 20:
            # 计算简单移动平均线
            prices = self.strategy.price_history[-20:]
            ma5 = np.mean(prices[-5:])
            ma20 = np.mean(prices)
            
            # 计算趋势强度
            if ma20 > 0:
                trend_strength = (ma5 - ma20) / ma20
                return np.clip(trend_strength, -1, 1)
        return 0  # 默认值
    
    def _calculate_liquidity(self, market_data: Dict[str, Any]) -> float:
        """
        计算流动性
        
        Args:
            market_data: 市场数据
            
        Returns:
            float: 流动性 (0 到 1)
        """
        # 简化实现，实际应根据订单簿深度等数据计算
        # 这里使用交易量作为流动性的代理
        volume = market_data.get("volume", 1)
        return min(volume / 1000000, 1)  # 归一化到0-1
    
    def _determine_market_regime(self, volatility: float, trend_strength: float) -> str:
        """
        确定市场 regime
        
        Args:
            volatility: 波动率
            trend_strength: 趋势强度
            
        Returns:
            str: 市场 regime
        """
        if volatility > 0.02 and abs(trend_strength) < 0.01:
            return "volatile"
        elif abs(trend_strength) > 0.01:
            return "trending"
        else:
            return "range"
    
    def _adjust_params_based_on_market_state(self, market_state: MarketState) -> Dict[str, Any]:
        """
        基于市场状态调整参数
        
        Args:
            market_state: 市场状态
            
        Returns:
            Dict[str, Any]: 调整后的参数
        """
        adjusted_params = {}
        
        # 根据市场 regime 调整参数
        if market_state.market_regime == "trending":
            # 趋势市场：增加动量因子，减少均值回归因子
            adjusted_params["ε"] = np.sign(market_state.trend_strength) * 0.9
            adjusted_params["G_eff"] = 1.5e-3
            adjusted_params["η"] = 0.5
            adjusted_params["γ"] = 0.05
        elif market_state.market_regime == "range":
            # 区间市场：增加均值回归因子，减少动量因子
            adjusted_params["ε"] = 0.1
            adjusted_params["G_eff"] = 0.8e-3
            adjusted_params["η"] = 1.0
            adjusted_params["γ"] = 0.2
        elif market_state.market_regime == "volatile":
            # 波动市场：增加风险控制，减少交易频率
            adjusted_params["ε"] = 0.5
            adjusted_params["G_eff"] = 0.5e-3
            adjusted_params["η"] = 0.3
            adjusted_params["γ"] = 0.3
            adjusted_params["κ"] = 3.0
            adjusted_params["λ"] = 4.0
        
        # 根据波动率调整参数
        if market_state.volatility > 0.02:
            # 高波动率：增加风险控制
            adjusted_params["γ"] = min(adjusted_params.get("γ", 0.1) + 0.1, 0.5)
            adjusted_params["λ"] = min(adjusted_params.get("λ", 3.0) + 1.0, 8.0)
        elif market_state.volatility < 0.005:
            # 低波动率：减少风险控制
            adjusted_params["γ"] = max(adjusted_params.get("γ", 0.1) - 0.05, 0.05)
            adjusted_params["λ"] = max(adjusted_params.get("λ", 3.0) - 1.0, 1.0)
        
        # 根据流动性调整参数
        if market_state.liquidity < 0.3:
            # 低流动性：减少交易规模，增加滑点考虑
            adjusted_params["G_eff"] = max(adjusted_params.get("G_eff", 1.2e-3) * 0.8, 0.5e-3)
        
        return adjusted_params
    
    def _save_market_state(self, market_state: MarketState):
        """
        保存市场状态
        
        Args:
            market_state: 市场状态
        """
        self.market_state_history.append(market_state)
        if len(self.market_state_history) > self.max_market_state_history:
            self.market_state_history.pop(0)
    
    def _record_adjustment(self, market_state: MarketState, adjusted_params: Dict[str, Any]):
        """
        记录调整历史
        
        Args:
            market_state: 市场状态
            adjusted_params: 调整后的参数
        """
        self.adjustment_history.append({
            "timestamp": time.time(),
            "market_state": market_state.__dict__,
            "adjusted_params": adjusted_params
        })
        
        # 限制历史长度
        if len(self.adjustment_history) > 100:
            self.adjustment_history.pop(0)
    
    def get_adjustment_history(self) -> List[Dict[str, Any]]:
        """
        获取调整历史
        
        Returns:
            List[Dict[str, Any]]: 调整历史
        """
        return self.adjustment_history
    
    def get_market_state_history(self) -> List[MarketState]:
        """
        获取市场状态历史
        
        Returns:
            List[MarketState]: 市场状态历史
        """
        return self.market_state_history
    
    def set_adjustment_interval(self, interval: int):
        """
        设置调整间隔
        
        Args:
            interval: 调整间隔（秒）
        """
        self.adjustment_interval = interval
        logger.info(f"调整间隔设置为: {interval}秒")


# 全局实时参数调整器实例
realtime_parameter_adjuster = RealtimeParameterAdjuster(None)