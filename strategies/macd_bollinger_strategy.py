import time
import numpy as np
import logging

logger = logging.getLogger("Strategy")
from strategies.base_strategy import BaseStrategy


class MacdBollingerStrategy(BaseStrategy):
    """MACD和布林带结合的交易策略"""

    def __init__(self, api_client=None, config=None):
        """
        初始化MACD和布林带策略

        Args:
            api_client (OKXAPIClient, optional): OKX API客户端实例
            config (dict, optional): 策略配置
        """
        super().__init__(api_client, config)

        # 策略参数
        self.strategy_params = {
            "macd_fast": 12,     # MACD快线周期
            "macd_slow": 26,     # MACD慢线周期
            "macd_signal": 9,    # MACD信号线周期
            "bollinger_period": 20,  # 布林带周期
            "bollinger_std": 2,      # 布林带标准差倍数
            "signal_threshold": 0.001,  # 信号阈值
        }

        # 数据容器
        self.price_history = []
        self.macd_history = []
        self.signal_history = []
        self.histogram_history = []
        self.bollinger_upper = []
        self.bollinger_middle = []
        self.bollinger_lower = []

        # 更新配置
        if config and "strategy" in config:
            self.strategy_params.update(config["strategy"])

        logger.info("MACD和布林带策略初始化完成")

    def calculate_ema(self, prices, period):
        """计算指数移动平均线"""
        if len(prices) < period:
            return None
        
        ema = []
        multiplier = 2 / (period + 1)
        # 初始EMA为简单移动平均
        initial_ema = np.mean(prices[:period])
        ema.append(initial_ema)
        
        # 计算后续EMA
        for price in prices[period:]:
            current_ema = (price - ema[-1]) * multiplier + ema[-1]
            ema.append(current_ema)
        
        return ema[-1]

    def calculate_macd(self, prices):
        """计算MACD指标"""
        if len(prices) < max(self.strategy_params["macd_slow"], self.strategy_params["macd_signal"]):
            return None, None, None
        
        # 计算EMA
        ema_fast = self.calculate_ema(prices, self.strategy_params["macd_fast"])
        ema_slow = self.calculate_ema(prices, self.strategy_params["macd_slow"])
        
        if ema_fast is None or ema_slow is None:
            return None, None, None
        
        # 计算MACD线
        macd_line = ema_fast - ema_slow
        
        # 计算信号线
        if len(self.macd_history) >= self.strategy_params["macd_signal"]:
            signal_line = self.calculate_ema(self.macd_history, self.strategy_params["macd_signal"])
        else:
            signal_line = None
        
        # 计算柱状图
        histogram = macd_line - signal_line if signal_line is not None else None
        
        return macd_line, signal_line, histogram

    def calculate_bollinger_bands(self, prices):
        """计算布林带"""
        if len(prices) < self.strategy_params["bollinger_period"]:
            return None, None, None
        
        # 计算移动平均
        period = self.strategy_params["bollinger_period"]
        middle_band = np.mean(prices[-period:])
        # 计算标准差
        std_dev = np.std(prices[-period:])
        # 计算上下轨
        upper_band = middle_band + (self.strategy_params["bollinger_std"] * std_dev)
        lower_band = middle_band - (self.strategy_params["bollinger_std"] * std_dev)
        
        return upper_band, middle_band, lower_band

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

        # 计算MACD
        macd_line, signal_line, histogram = self.calculate_macd(self.price_history)
        
        if macd_line:
            self.macd_history.append(macd_line)
        if signal_line:
            self.signal_history.append(signal_line)
        if histogram:
            self.histogram_history.append(histogram)

        # 计算布林带
        upper_band, middle_band, lower_band = self.calculate_bollinger_bands(self.price_history)
        
        if upper_band:
            self.bollinger_upper.append(upper_band)
        if middle_band:
            self.bollinger_middle.append(middle_band)
        if lower_band:
            self.bollinger_lower.append(lower_band)

        # 获取当前价格
        current_price = self.price_history[-1]

        # 生成交易信号
        side = "neutral"
        signal_strength = 0

        # MACD信号
        if len(self.macd_history) > 1 and len(self.signal_history) > 1:
            # MACD金叉：MACD线上穿信号线
            if self.macd_history[-1] > self.signal_history[-1] and self.macd_history[-2] <= self.signal_history[-2]:
                if histogram and histogram > 0:
                    side = "buy"
                    signal_strength = 0.6
            # MACD死叉：MACD线下穿信号线
            elif self.macd_history[-1] < self.signal_history[-1] and self.macd_history[-2] >= self.signal_history[-2]:
                if histogram and histogram < 0:
                    side = "sell"
                    signal_strength = -0.6

        # 布林带信号
        if upper_band and lower_band and middle_band:
            # 价格突破上轨
            if current_price > upper_band:
                side = "sell"
                signal_strength = -0.7
            # 价格突破下轨
            elif current_price < lower_band:
                side = "buy"
                signal_strength = 0.7
            # 价格回归中轨
            elif abs(current_price - middle_band) < self.strategy_params["signal_threshold"]:
                # 根据MACD方向决定
                if len(self.histogram_history) > 0 and self.histogram_history[-1] > 0:
                    side = "buy"
                    signal_strength = 0.5
                elif len(self.histogram_history) > 0 and self.histogram_history[-1] < 0:
                    side = "sell"
                    signal_strength = -0.5

        # 构建交易信号
        signal = {
            "strategy": self.name,
            "side": side,
            "price": current_price,
            "signal_strength": signal_strength,
            "timestamp": market_data.get("timestamp", time.time()),
            "inst_id": market_data.get("inst_id", "BTC-USDT-SWAP"),
            "indicators": {
                "macd_line": macd_line,
                "signal_line": signal_line,
                "histogram": histogram,
                "bollinger_upper": upper_band,
                "bollinger_middle": middle_band,
                "bollinger_lower": lower_band
            }
        }

        logger.info(f"策略信号生成: {signal}")
        return signal