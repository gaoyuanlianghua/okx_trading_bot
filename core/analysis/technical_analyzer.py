import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from core.utils.logger import get_logger

logger = get_logger(__name__)

class TechnicalAnalyzer:
    def __init__(self):
        pass
    
    def calculate_moving_average(self, prices: List[float], period: int) -> List[float]:
        if len(prices) < period:
            return [None] * len(prices)
        
        ma = []
        for i in range(len(prices)):
            if i < period - 1:
                ma.append(None)
            else:
                ma.append(sum(prices[i - period + 1:i + 1]) / period)
        return ma
    
    def calculate_ema(self, prices: List[float], period: int) -> List[float]:
        if len(prices) < period:
            return [None] * len(prices)
        
        ema = []
        multiplier = 2 / (period + 1)
        
        for i in range(len(prices)):
            if i == period - 1:
                current_ema = sum(prices[:period]) / period
            elif i > period - 1:
                current_ema = (prices[i] - ema[-1]) * multiplier + ema[-1]
            else:
                current_ema = None
            ema.append(current_ema)
        return ema
    
    def calculate_macd(self, prices: List[float], fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Dict[str, List[float]]:
        if len(prices) < slow_period:
            return {
                'macd': [None] * len(prices),
                'signal': [None] * len(prices),
                'histogram': [None] * len(prices)
            }
        
        fast_ema = self.calculate_ema(prices, fast_period)
        slow_ema = self.calculate_ema(prices, slow_period)
        
        macd = []
        for i in range(len(prices)):
            if fast_ema[i] is not None and slow_ema[i] is not None:
                macd.append(fast_ema[i] - slow_ema[i])
            else:
                macd.append(None)
        
        signal = self.calculate_ema([x for x in macd if x is not None], signal_period)
        signal = [None] * (len(prices) - len(signal)) + signal
        
        histogram = []
        for i in range(len(prices)):
            if macd[i] is not None and signal[i] is not None:
                histogram.append(macd[i] - signal[i])
            else:
                histogram.append(None)
        
        return {
            'macd': macd,
            'signal': signal,
            'histogram': histogram
        }
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> List[float]:
        if len(prices) < period + 1:
            return [None] * len(prices)
        
        rsi = [None] * len(prices)
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
            
            if i >= period:
                avg_gain = sum(gains[-period:]) / period
                avg_loss = sum(losses[-period:]) / period
                
                if avg_loss == 0:
                    rsi[i] = 100
                else:
                    rs = avg_gain / avg_loss
                    rsi[i] = 100 - (100 / (1 + rs))
        
        return rsi
    
    def calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: float = 2) -> Dict[str, List[float]]:
        if len(prices) < period:
            return {
                'upper': [None] * len(prices),
                'middle': [None] * len(prices),
                'lower': [None] * len(prices)
            }
        
        middle = self.calculate_moving_average(prices, period)
        upper = []
        lower = []
        
        for i in range(len(prices)):
            if i < period - 1:
                upper.append(None)
                lower.append(None)
            else:
                window = prices[i - period + 1:i + 1]
                std = np.std(window)
                upper.append(middle[i] + (std * std_dev))
                lower.append(middle[i] - (std * std_dev))
        
        return {
            'upper': upper,
            'middle': middle,
            'lower': lower
        }
    
    def calculate_stochastic_oscillator(self, high_prices: List[float], low_prices: List[float], close_prices: List[float], period: int = 14) -> Dict[str, List[float]]:
        if len(close_prices) < period:
            return {
                'k': [None] * len(close_prices),
                'd': [None] * len(close_prices)
            }
        
        k_values = [None] * len(close_prices)
        
        for i in range(period - 1, len(close_prices)):
            window_high = max(high_prices[i - period + 1:i + 1])
            window_low = min(low_prices[i - period + 1:i + 1])
            current_close = close_prices[i]
            
            if window_high - window_low == 0:
                k_values[i] = 50
            else:
                k_values[i] = ((current_close - window_low) / (window_high - window_low)) * 100
        
        d_values = self.calculate_moving_average([x for x in k_values if x is not None], 3)
        d_values = [None] * (len(close_prices) - len(d_values)) + d_values
        
        return {
            'k': k_values,
            'd': d_values
        }
    
    def calculate_atr(self, high_prices: List[float], low_prices: List[float], close_prices: List[float], period: int = 14) -> List[float]:
        if len(close_prices) < period + 1:
            return [None] * len(close_prices)
        
        tr = []
        for i in range(1, len(close_prices)):
            true_range = max(
                high_prices[i] - low_prices[i],
                abs(high_prices[i] - close_prices[i-1]),
                abs(low_prices[i] - close_prices[i-1])
            )
            tr.append(true_range)
        
        atr = [None] * (len(close_prices))
        atr[period] = sum(tr[:period]) / period
        
        for i in range(period + 1, len(close_prices)):
            atr[i] = ((atr[i-1] * (period - 1)) + tr[i-1]) / period
        
        return atr
    
    def analyze_trend(self, prices: List[float], short_period: int = 5, long_period: int = 20) -> str:
        short_ma = self.calculate_moving_average(prices, short_period)
        long_ma = self.calculate_moving_average(prices, long_period)
        
        if short_ma[-1] is None or long_ma[-1] is None:
            return 'insufficient_data'
        
        if short_ma[-1] > long_ma[-1] and short_ma[-2] > long_ma[-2]:
            return 'uptrend'
        elif short_ma[-1] < long_ma[-1] and short_ma[-2] < long_ma[-2]:
            return 'downtrend'
        else:
            return 'sideways'
