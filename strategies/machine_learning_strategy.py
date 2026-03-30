"""
机器学习策略

使用机器学习模型预测价格趋势，生成交易信号
"""

import logging
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

from .base_strategy import BaseStrategy
from core.utils.logger import get_logger

logger = get_logger(__name__)


class MachineLearningStrategy(BaseStrategy):
    """
    机器学习策略
    
    使用线性回归模型预测价格趋势，生成交易信号
    """
    
    def __init__(self, api_client=None, config=None):
        """
        初始化机器学习策略
        
        Args:
            api_client: API客户端
            config: 策略配置
        """
        super().__init__(api_client, config)
        
        # 配置参数
        self.window_size = config.get("window_size", 20)  # 滑动窗口大小
        self.threshold = config.get("threshold", 0.001)  # 预测阈值
        self.lookback = config.get("lookback", 100)  # 历史数据长度
        
        # 模型初始化
        self.model = make_pipeline(StandardScaler(), LinearRegression())
        
        # 历史价格数据
        self.price_history = []
        
        # 特征和标签
        self.features = []
        self.labels = []
        
        logger.info(f"机器学习策略初始化完成: {self.name}")
    
    def _execute_strategy(self, market_data):
        """
        执行机器学习策略
        
        Args:
            market_data: 市场数据
            
        Returns:
            dict: 交易信号
        """
        # 提取价格数据
        price = market_data.get("price", 0)
        inst_id = market_data.get("inst_id", "BTC-USDT-SWAP")
        
        # 更新价格历史
        self.price_history.append(price)
        
        # 保持历史数据长度
        if len(self.price_history) > self.lookback:
            self.price_history = self.price_history[-self.lookback:]
        
        # 确保有足够的数据
        if len(self.price_history) < self.window_size + 1:
            return None
        
        # 准备特征和标签
        self._prepare_data()
        
        # 训练模型
        self._train_model()
        
        # 预测价格
        predicted_price = self._predict_price()
        
        # 生成交易信号
        signal = self._generate_signal(price, predicted_price, inst_id)
        
        return signal
    
    def _prepare_data(self):
        """
        准备训练数据
        """
        self.features = []
        self.labels = []
        
        # 生成滑动窗口特征
        for i in range(len(self.price_history) - self.window_size):
            # 窗口内的价格
            window = self.price_history[i:i + self.window_size]
            # 下一个价格作为标签
            next_price = self.price_history[i + self.window_size]
            
            # 计算特征：窗口内的价格变化率
            features = []
            for j in range(1, len(window)):
                if window[j-1] > 0:
                    change_rate = (window[j] - window[j-1]) / window[j-1]
                    features.append(change_rate)
            
            if features:
                self.features.append(features)
                self.labels.append(next_price)
    
    def _train_model(self):
        """
        训练机器学习模型
        """
        if len(self.features) < 5:  # 至少需要5个样本
            return
        
        try:
            X = np.array(self.features)
            y = np.array(self.labels)
            
            # 训练模型
            self.model.fit(X, y)
        except Exception as e:
            logger.error(f"模型训练失败: {e}")
    
    def _predict_price(self):
        """
        预测价格
        
        Returns:
            float: 预测价格
        """
        if len(self.features) < 1:
            return self.price_history[-1]
        
        try:
            # 使用最新的窗口数据进行预测
            latest_window = self.price_history[-self.window_size:]
            
            # 计算特征
            features = []
            for i in range(1, len(latest_window)):
                if latest_window[i-1] > 0:
                    change_rate = (latest_window[i] - latest_window[i-1]) / latest_window[i-1]
                    features.append(change_rate)
            
            if features:
                X = np.array([features])
                predicted_price = self.model.predict(X)[0]
                return predicted_price
        except Exception as e:
            logger.error(f"价格预测失败: {e}")
        
        return self.price_history[-1]
    
    def _generate_signal(self, current_price, predicted_price, inst_id):
        """
        生成交易信号
        
        Args:
            current_price: 当前价格
            predicted_price: 预测价格
            inst_id: 产品ID
            
        Returns:
            dict: 交易信号
        """
        # 计算价格变化率
        if current_price > 0:
            price_change = (predicted_price - current_price) / current_price
        else:
            price_change = 0
        
        # 根据价格变化率生成信号
        if price_change > self.threshold:
            # 预测价格上涨，买入
            return {
                "strategy": self.name,
                "side": "buy",
                "price": current_price,
                "amount": "0.001",  # 默认交易金额
                "inst_id": inst_id,
                "signal_type": "machine_learning",
                "confidence": min(price_change / (self.threshold * 10), 1.0),
                "predicted_change": price_change
            }
        elif price_change < -self.threshold:
            # 预测价格下跌，卖出
            return {
                "strategy": self.name,
                "side": "sell",
                "price": current_price,
                "amount": "0.001",  # 默认交易金额
                "inst_id": inst_id,
                "signal_type": "machine_learning",
                "confidence": min(abs(price_change) / (self.threshold * 10), 1.0),
                "predicted_change": price_change
            }
        
        # 价格变化不大，不生成信号
        return None
    
    def backtest(self, historical_data):
        """
        回测策略
        
        Args:
            historical_data: 历史数据
            
        Returns:
            dict: 回测结果
        """
        logger.info(f"开始回测: {self.name}")
        
        # 重置历史数据
        self.price_history = []
        self.features = []
        self.labels = []
        
        # 模拟交易
        total_trades = 0
        win_trades = 0
        total_profit = 0
        max_drawdown = 0
        current_drawdown = 0
        peak = 0
        
        for i, data in enumerate(historical_data):
            # 执行策略
            signal = self.execute(data)
            
            # 模拟交易
            if signal:
                total_trades += 1
                
                # 假设交易成功，计算收益
                # 简化计算：使用下一个时间点的价格作为成交价格
                if i + 1 < len(historical_data):
                    next_price = historical_data[i + 1].get("price", 0)
                    current_price = data.get("price", 0)
                    
                    if signal["side"] == "buy":
                        profit = (next_price - current_price) * float(signal["amount"])
                    else:
                        profit = (current_price - next_price) * float(signal["amount"])
                    
                    total_profit += profit
                    
                    if profit > 0:
                        win_trades += 1
                    
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
            "window_size": self.window_size,
            "threshold": self.threshold,
            "lookback": self.lookback,
            "price_history_length": len(self.price_history),
            "model_trained": len(self.features) >= 5
        })
        return base_status