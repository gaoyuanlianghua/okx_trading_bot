import time
import numpy as np
import logging

logger = logging.getLogger("Strategy")
from strategies.base_strategy import BaseStrategy


class MARsiStrategy(BaseStrategy):
    """移动平均线和RSI结合的交易策略"""

    def __init__(self, api_client=None, config=None):
        """
        初始化移动平均线和RSI策略

        Args:
            api_client (OKXAPIClient, optional): OKX API客户端实例
            config (dict, optional): 策略配置
        """
        super().__init__(api_client, config)

        # 策略参数
        self.strategy_params = {
            "ma_short": 10,  # 短期移动平均线周期
            "ma_long": 30,   # 长期移动平均线周期
            "rsi_period": 14, # RSI周期
            "rsi_overbought": 70,  # RSI超买阈值
            "rsi_oversold": 30,    # RSI超卖阈值
            "trend_threshold": 0.001,  # 趋势阈值
        }

        # 数据容器
        self.price_history = []
        self.ma_short_history = []
        self.ma_long_history = []
        self.rsi_history = []

        # 更新配置
        if config and "strategy" in config:
            self.strategy_params.update(config["strategy"])

        logger.info("移动平均线和RSI策略初始化完成")

    def calculate_ma(self, prices, period):
        """计算移动平均线"""
        if len(prices) < period:
            return None
        return np.mean(prices[-period:])

    def calculate_rsi(self, prices, period):
        """计算RSI指标"""
        if len(prices) < period + 1:
            return None
        
        deltas = np.diff(prices)
        gains = deltas[deltas > 0]
        losses = -deltas[deltas < 0]
        
        avg_gain = np.mean(gains[-period:]) if len(gains) > 0 else 0
        avg_loss = np.mean(losses[-period:]) if len(losses) > 0 else 0
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_trend(self):
        """计算趋势"""
        if len(self.ma_short_history) < 2 or len(self.ma_long_history) < 2:
            return 0
        
        # 短期均线趋势
        ma_short_trend = self.ma_short_history[-1] - self.ma_short_history[-2]
        # 长期均线趋势
        ma_long_trend = self.ma_long_history[-1] - self.ma_long_history[-2]
        # 均线差趋势
        ma_diff = (self.ma_short_history[-1] - self.ma_long_history[-1])
        
        # 综合趋势
        trend = 0
        if ma_short_trend > self.strategy_params["trend_threshold"] and ma_long_trend > 0:
            trend = 1  # 多头趋势
        elif ma_short_trend < -self.strategy_params["trend_threshold"] and ma_long_trend < 0:
            trend = -1  # 空头趋势
        
        return trend

    def _execute_strategy(self, market_data):
        """执行策略，生成交易信号

        Args:
            market_data (dict): 市场数据

        Returns:
            dict: 交易信号，包含side, price, amount等信息
        """
        # 保存当前价格到历史数据
        if "price" in market_data:
            self.price_history.append(market_data["price"])
        elif "last" in market_data:
            self.price_history.append(float(market_data["last"]))
        else:
            logger.warning("市场数据中没有价格信息")
            return None

        # 计算移动平均线
        ma_short = self.calculate_ma(self.price_history, self.strategy_params["ma_short"])
        ma_long = self.calculate_ma(self.price_history, self.strategy_params["ma_long"])
        
        if ma_short:
            self.ma_short_history.append(ma_short)
        if ma_long:
            self.ma_long_history.append(ma_long)

        # 计算RSI
        rsi = self.calculate_rsi(self.price_history, self.strategy_params["rsi_period"])
        if rsi:
            self.rsi_history.append(rsi)

        # 获取当前价格
        current_price = self.price_history[-1]

        # 生成交易信号
        side = "neutral"
        signal_strength = 0

        # 趋势判断
        trend = self.calculate_trend()

        # 金叉死叉信号
        if len(self.ma_short_history) > 1 and len(self.ma_long_history) > 1:
            # 金叉：短期均线上穿长期均线
            if self.ma_short_history[-1] > self.ma_long_history[-1] and self.ma_short_history[-2] <= self.ma_long_history[-2]:
                if rsi and rsi < 50:
                    side = "buy"
                    signal_strength = 0.7
            # 死叉：短期均线下穿长期均线
            elif self.ma_short_history[-1] < self.ma_long_history[-1] and self.ma_short_history[-2] >= self.ma_long_history[-2]:
                if rsi and rsi > 50:
                    side = "sell"
                    signal_strength = -0.7

        # RSI超买超卖信号
        if rsi:
            if rsi < self.strategy_params["rsi_oversold"] and trend >= 0:
                side = "buy"
                signal_strength = 0.8
            elif rsi > self.strategy_params["rsi_overbought"] and trend <= 0:
                side = "sell"
                signal_strength = -0.8

        # 构建交易信号
        signal = {
            "strategy": self.name,
            "side": side,
            "price": current_price,
            "signal_strength": signal_strength,
            "timestamp": market_data.get("timestamp", time.time()),
            "inst_id": market_data.get("inst_id", "BTC-USDT-SWAP"),
            "indicators": {
                "ma_short": ma_short,
                "ma_long": ma_long,
                "rsi": rsi,
                "trend": trend
            }
        }

        logger.info(f"策略信号生成: {signal}")
        return signal