import asyncio
import aiohttp
import json
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

from core.events.event_bus import EventBus
from core.utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class SentimentData:
    """情绪数据类"""
    timestamp: float
    cryptocurrency: str
    sentiment_score: float  # -1.0 to 1.0
    source: str  # 'twitter', 'reddit', 'news'
    confidence: float  # 0.0 to 1.0

class MarketSentimentAnalyzer:
    """市场情绪分析器"""
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        """初始化市场情绪分析器"""
        self.event_bus = event_bus
        self.session = None
        self.sentiment_history: Dict[str, List[SentimentData]] = {}
        self.is_running = False
        
    async def initialize(self):
        """初始化分析器"""
        self.session = aiohttp.ClientSession()
        logger.info("市场情绪分析器初始化完成")
    
    async def shutdown(self):
        """关闭分析器"""
        if self.session:
            await self.session.close()
        logger.info("市场情绪分析器已关闭")
    
    async def analyze_sentiment(self, cryptocurrency: str) -> float:
        """分析指定加密货币的情绪"""
        try:
            # 并行获取不同来源的情绪数据
            tasks = [
                self._get_twitter_sentiment(cryptocurrency),
                self._get_reddit_sentiment(cryptocurrency),
                self._get_news_sentiment(cryptocurrency)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果
            valid_results = []
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"获取情绪数据时出错: {result}")
                else:
                    valid_results.append(result)
            
            if not valid_results:
                return 0.0
            
            # 计算加权平均情绪得分
            weighted_score = 0.0
            total_weight = 0.0
            
            for score, weight in valid_results:
                weighted_score += score * weight
                total_weight += weight
            
            if total_weight == 0:
                return 0.0
            
            final_score = weighted_score / total_weight
            
            # 保存情绪数据
            sentiment_data = SentimentData(
                timestamp=time.time(),
                cryptocurrency=cryptocurrency,
                sentiment_score=final_score,
                source="combined",
                confidence=min(1.0, total_weight / 3.0)
            )
            
            if cryptocurrency not in self.sentiment_history:
                self.sentiment_history[cryptocurrency] = []
            
            self.sentiment_history[cryptocurrency].append(sentiment_data)
            
            # 限制历史数据大小
            if len(self.sentiment_history[cryptocurrency]) > 1000:
                self.sentiment_history[cryptocurrency] = self.sentiment_history[cryptocurrency][-1000:]
            
            # 发布情绪分析事件
            if self.event_bus:
                await self.event_bus.publish("market_sentiment_updated", {
                    "cryptocurrency": cryptocurrency,
                    "sentiment_score": final_score,
                    "timestamp": sentiment_data.timestamp,
                    "confidence": sentiment_data.confidence
                })
            
            return final_score
            
        except Exception as e:
            logger.error(f"分析情绪时出错: {e}")
            return 0.0
    
    async def _get_twitter_sentiment(self, cryptocurrency: str) -> Tuple[float, float]:
        """获取Twitter情绪"""
        # 模拟Twitter API调用
        # 实际实现中，这里应该调用Twitter API获取相关推文并进行情绪分析
        await asyncio.sleep(0.1)
        # 返回模拟的情绪得分和权重
        return (0.2, 0.3)
    
    async def _get_reddit_sentiment(self, cryptocurrency: str) -> Tuple[float, float]:
        """获取Reddit情绪"""
        # 模拟Reddit API调用
        await asyncio.sleep(0.1)
        return (0.3, 0.3)
    
    async def _get_news_sentiment(self, cryptocurrency: str) -> Tuple[float, float]:
        """获取新闻情绪"""
        # 模拟新闻API调用
        await asyncio.sleep(0.1)
        return (0.1, 0.4)
    
    def get_historical_sentiment(self, cryptocurrency: str, hours: int = 24) -> List[SentimentData]:
        """获取历史情绪数据"""
        if cryptocurrency not in self.sentiment_history:
            return []
        
        cutoff_time = time.time() - (hours * 3600)
        return [data for data in self.sentiment_history[cryptocurrency] if data.timestamp >= cutoff_time]
    
    def get_sentiment_trend(self, cryptocurrency: str, hours: int = 24) -> float:
        """获取情绪趋势"""
        historical_data = self.get_historical_sentiment(cryptocurrency, hours)
        if len(historical_data) < 2:
            return 0.0
        
        # 计算情绪变化率
        first_score = historical_data[0].sentiment_score
        last_score = historical_data[-1].sentiment_score
        
        if first_score == 0:
            return 0.0
        
        trend = (last_score - first_score) / abs(first_score)
        return trend
    
    async def start_monitoring(self, cryptocurrencies: List[str], interval: int = 60):
        """开始监控指定加密货币的情绪"""
        self.is_running = True
        logger.info(f"开始监控市场情绪，加密货币: {cryptocurrencies}, 间隔: {interval}秒")
        
        while self.is_running:
            try:
                for crypto in cryptocurrencies:
                    await self.analyze_sentiment(crypto)
                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"监控市场情绪时出错: {e}")
                await asyncio.sleep(interval)
    
    def stop_monitoring(self):
        """停止监控"""
        self.is_running = False
        logger.info("市场情绪监控已停止")