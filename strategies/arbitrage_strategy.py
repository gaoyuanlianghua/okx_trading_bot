"""
套利策略

在不同市场或不同交易对之间进行套利交易
"""

import logging
from typing import Dict, List, Optional

from .base_strategy import BaseStrategy
from core.utils.logger import get_logger

logger = get_logger(__name__)


class ArbitrageStrategy(BaseStrategy):
    """
    套利策略
    
    在不同市场或不同交易对之间进行套利交易
    """
    
    def __init__(self, api_client=None, config=None):
        """
        初始化套利策略
        
        Args:
            api_client: API客户端
            config: 策略配置
        """
        super().__init__(api_client, config)
        
        # 配置参数
        self.arb_pairs = config.get("arb_pairs", [])  # 套利交易对列表
        self.min_profit = config.get("min_profit", 0.001)  # 最小利润阈值
        self.max_trade_amount = config.get("max_trade_amount", 0.01)  # 最大交易金额
        
        # 价格缓存
        self.price_cache = {}
        
        # 套利历史
        self.arb_history = []
        
        logger.info(f"套利策略初始化完成: {self.name}")
    
    def _execute_strategy(self, market_data):
        """
        执行套利策略
        
        Args:
            market_data: 市场数据
            
        Returns:
            dict: 交易信号
        """
        # 更新价格缓存
        inst_id = market_data.get("inst_id", "")
        price = market_data.get("price", 0)
        
        if inst_id:
            self.price_cache[inst_id] = price
        
        # 检查所有套利对
        for arb_pair in self.arb_pairs:
            signal = self._check_arb_opportunity(arb_pair)
            if signal:
                return signal
        
        return None
    
    def _check_arb_opportunity(self, arb_pair):
        """
        检查套利机会
        
        Args:
            arb_pair: 套利交易对配置
            
        Returns:
            dict: 交易信号
        """
        try:
            # 获取套利对信息
            inst_id1 = arb_pair.get("inst_id1")
            inst_id2 = arb_pair.get("inst_id2")
            ratio = arb_pair.get("ratio", 1.0)  # 比率，用于不同交易对之间的转换
            
            # 检查价格缓存
            if inst_id1 not in self.price_cache or inst_id2 not in self.price_cache:
                return None
            
            # 获取价格
            price1 = self.price_cache[inst_id1]
            price2 = self.price_cache[inst_id2]
            
            # 计算价格差异
            # 假设inst_id1是基础交易对，inst_id2是比较交易对
            # 价格差异 = (price2 - price1 * ratio) / price1
            if price1 > 0:
                price_diff = (price2 - price1 * ratio) / price1
            else:
                return None
            
            # 检查是否有套利机会
            if abs(price_diff) < self.min_profit:
                return None
            
            # 生成套利信号
            if price_diff > 0:
                # price2 > price1 * ratio，买入inst_id1，卖出inst_id2
                signal = {
                    "strategy": self.name,
                    "side": "buy",
                    "price": price1,
                    "amount": str(min(self.max_trade_amount, 0.001)),  # 限制交易金额
                    "inst_id": inst_id1,
                    "signal_type": "arbitrage",
                    "confidence": min(price_diff / (self.min_profit * 2), 1.0),
                    "arb_info": {
                        "pair": arb_pair,
                        "price1": price1,
                        "price2": price2,
                        "price_diff": price_diff,
                        "action": "buy_low_sell_high",
                        "sell_inst_id": inst_id2,
                        "sell_price": price2
                    }
                }
            else:
                # price2 < price1 * ratio，买入inst_id2，卖出inst_id1
                signal = {
                    "strategy": self.name,
                    "side": "buy",
                    "price": price2,
                    "amount": str(min(self.max_trade_amount, 0.001)),  # 限制交易金额
                    "inst_id": inst_id2,
                    "signal_type": "arbitrage",
                    "confidence": min(abs(price_diff) / (self.min_profit * 2), 1.0),
                    "arb_info": {
                        "pair": arb_pair,
                        "price1": price1,
                        "price2": price2,
                        "price_diff": price_diff,
                        "action": "buy_low_sell_high",
                        "sell_inst_id": inst_id1,
                        "sell_price": price1
                    }
                }
            
            # 记录套利机会
            self._log_arb_opportunity(arb_pair, price1, price2, price_diff, signal)
            
            return signal
        
        except Exception as e:
            logger.error(f"检查套利机会失败: {e}")
            return None
    
    def _log_arb_opportunity(self, arb_pair, price1, price2, price_diff, signal):
        """
        记录套利机会
        
        Args:
            arb_pair: 套利交易对配置
            price1: 第一个交易对的价格
            price2: 第二个交易对的价格
            price_diff: 价格差异
            signal: 交易信号
        """
        arb_log = {
            "timestamp": signal.get("timestamp", ""),
            "strategy": self.name,
            "arb_pair": arb_pair,
            "price1": price1,
            "price2": price2,
            "price_diff": price_diff,
            "signal": signal
        }
        
        self.arb_history.append(arb_log)
        logger.info(f"套利机会: {arb_log}")
    
    def backtest(self, historical_data):
        """
        回测策略
        
        Args:
            historical_data: 历史数据
            
        Returns:
            dict: 回测结果
        """
        logger.info(f"开始回测: {self.name}")
        
        # 重置价格缓存
        self.price_cache = {}
        self.arb_history = []
        
        # 模拟交易
        total_trades = 0
        win_trades = 0
        total_profit = 0
        max_drawdown = 0
        current_drawdown = 0
        peak = 0
        
        for data in historical_data:
            # 执行策略
            signal = self.execute(data)
            
            # 模拟交易
            if signal:
                total_trades += 1
                
                # 假设交易成功，计算收益
                # 简化计算：使用套利机会的价格差异作为收益
                arb_info = signal.get("arb_info", {})
                price_diff = arb_info.get("price_diff", 0)
                
                # 计算收益
                amount = float(signal.get("amount", 0))
                price = float(signal.get("price", 0))
                profit = abs(price_diff) * price * amount
                
                total_profit += profit
                win_trades += 1  # 套利策略假设总是盈利
                
                # 计算回撤
                peak = max(peak, total_profit)
                current_drawdown = (peak - total_profit) / max(peak, 1)
                max_drawdown = max(max_drawdown, current_drawdown)
        
        # 计算回测结果
        win_rate = win_trades / total_trades if total_trades > 0 else 0
        sharpe_ratio = win_rate * 2 - 1  # 简化的夏普比率计算
        
        result = {
            "strategy": self.name,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "total_profit": total_profit,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio
        }
        
        logger.info(f"回测完成: {result}")
        return result
    
    def get_status(self):
        """
        获取策略状态
        
        Returns:
            dict: 策略状态
        """
        base_status = super().get_status()
        base_status.update({
            "arb_pairs": self.arb_pairs,
            "min_profit": self.min_profit,
            "max_trade_amount": self.max_trade_amount,
            "price_cache": self.price_cache,
            "arb_history_length": len(self.arb_history)
        })
        return base_status
    
    def add_arb_pair(self, arb_pair):
        """
        添加套利交易对
        
        Args:
            arb_pair: 套利交易对配置
        """
        self.arb_pairs.append(arb_pair)
        logger.info(f"添加套利交易对: {arb_pair}")
    
    def remove_arb_pair(self, index):
        """
        移除套利交易对
        
        Args:
            index: 交易对索引
        """
        if 0 <= index < len(self.arb_pairs):
            removed = self.arb_pairs.pop(index)
            logger.info(f"移除套利交易对: {removed}")
        else:
            logger.error(f"无效的套利交易对索引: {index}")
    
    def get_arb_history(self, limit=100):
        """
        获取套利历史
        
        Args:
            limit: 限制数量
            
        Returns:
            list: 套利历史列表
        """
        return self.arb_history[-limit:]