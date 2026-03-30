import asyncio
import aiohttp
import json
from typing import Dict, List, Optional, Any
from core.utils.logger import get_logger

logger = get_logger(__name__)

class FundamentalAnalyzer:
    def __init__(self):
        self.session = None
    
    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_coin_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            await self._ensure_session()
            url = f"https://api.coingecko.com/api/v3/coins/{symbol.lower()}"
            params = {
                'localization': 'false',
                'tickers': 'false',
                'market_data': 'true',
                'community_data': 'true',
                'developer_data': 'true',
                'sparkline': 'false'
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    logger.error(f"Failed to get market data for {symbol}: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error getting market data: {e}")
            return None
    
    async def get_coin_market_cap_rank(self, symbol: str) -> Optional[int]:
        data = await self.get_coin_market_data(symbol)
        if data and 'market_data' in data:
            return data['market_data'].get('market_cap_rank')
        return None
    
    async def get_coin_volume(self, symbol: str) -> Optional[Dict[str, float]]:
        data = await self.get_coin_market_data(symbol)
        if data and 'market_data' in data:
            return data['market_data'].get('total_volume', {})
        return None
    
    async def get_coin_market_metrics(self, symbol: str) -> Optional[Dict[str, Any]]:
        data = await self.get_coin_market_data(symbol)
        if not data or 'market_data' not in data:
            return None
        
        market_data = data['market_data']
        metrics = {
            'market_cap': market_data.get('market_cap', {}).get('usd'),
            'total_volume': market_data.get('total_volume', {}).get('usd'),
            'circulating_supply': market_data.get('circulating_supply'),
            'total_supply': market_data.get('total_supply'),
            'max_supply': market_data.get('max_supply'),
            'ath': market_data.get('ath', {}).get('usd'),
            'atl': market_data.get('atl', {}).get('usd'),
            'price_change_percentage_24h': market_data.get('price_change_percentage_24h'),
            'price_change_percentage_7d': market_data.get('price_change_percentage_7d'),
            'price_change_percentage_30d': market_data.get('price_change_percentage_30d'),
        }
        return metrics
    
    async def get_coin_community_metrics(self, symbol: str) -> Optional[Dict[str, Any]]:
        data = await self.get_coin_market_data(symbol)
        if not data or 'community_data' not in data:
            return None
        
        community_data = data['community_data']
        metrics = {
            'facebook_likes': community_data.get('facebook_likes'),
            'twitter_followers': community_data.get('twitter_followers'),
            'reddit_average_posts_48h': community_data.get('reddit_average_posts_48h'),
            'reddit_average_comments_48h': community_data.get('reddit_average_comments_48h'),
            'reddit_subscribers': community_data.get('reddit_subscribers'),
            'reddit_accounts_active_48h': community_data.get('reddit_accounts_active_48h'),
        }
        return metrics
    
    async def get_coin_developer_metrics(self, symbol: str) -> Optional[Dict[str, Any]]:
        data = await self.get_coin_market_data(symbol)
        if not data or 'developer_data' not in data:
            return None
        
        developer_data = data['developer_data']
        metrics = {
            'forks': developer_data.get('forks'),
            'stars': developer_data.get('stars'),
            'subscribers': developer_data.get('subscribers'),
            'total_issues': developer_data.get('total_issues'),
            'closed_issues': developer_data.get('closed_issues'),
            'pull_requests_merged': developer_data.get('pull_requests_merged'),
            'pull_request_contributors': developer_data.get('pull_request_contributors'),
            'commit_count_4_weeks': developer_data.get('commit_count_4_weeks'),
        }
        return metrics
    
    async def analyze_coin_fundamentals(self, symbol: str) -> Optional[Dict[str, Any]]:
        market_metrics = await self.get_coin_market_metrics(symbol)
        community_metrics = await self.get_coin_community_metrics(symbol)
        developer_metrics = await self.get_coin_developer_metrics(symbol)
        
        if not market_metrics:
            return None
        
        analysis = {
            'symbol': symbol,
            'market_metrics': market_metrics,
            'community_metrics': community_metrics,
            'developer_metrics': developer_metrics,
            'overall_score': self._calculate_fundamental_score(market_metrics, community_metrics, developer_metrics)
        }
        
        return analysis
    
    def _calculate_fundamental_score(self, market_metrics: Dict[str, Any], community_metrics: Optional[Dict[str, Any]], developer_metrics: Optional[Dict[str, Any]]) -> float:
        score = 0.0
        weights = {
            'market': 0.4,
            'community': 0.3,
            'developer': 0.3
        }
        
        market_score = self._calculate_market_score(market_metrics)
        community_score = self._calculate_community_score(community_metrics)
        developer_score = self._calculate_developer_score(developer_metrics)
        
        score = (market_score * weights['market'] +
                community_score * weights['community'] +
                developer_score * weights['developer'])
        
        return score
    
    def _calculate_market_score(self, market_metrics: Dict[str, Any]) -> float:
        score = 0.0
        
        if market_metrics.get('market_cap_rank') is not None:
            rank_score = max(0, 100 - (market_metrics['market_cap_rank'] / 10))
            score += rank_score * 0.3
        
        if market_metrics.get('price_change_percentage_24h') is not None:
            change_score = min(100, max(0, 50 + market_metrics['price_change_percentage_24h']))
            score += change_score * 0.2
        
        if market_metrics.get('total_volume') is not None and market_metrics.get('market_cap') is not None:
            if market_metrics['market_cap'] > 0:
                volume_ratio = market_metrics['total_volume'] / market_metrics['market_cap']
                volume_score = min(100, volume_ratio * 1000)
                score += volume_score * 0.2
        
        if market_metrics.get('circulating_supply') is not None and market_metrics.get('max_supply') is not None:
            if market_metrics['max_supply'] > 0:
                supply_ratio = market_metrics['circulating_supply'] / market_metrics['max_supply']
                supply_score = min(100, supply_ratio * 100)
                score += supply_score * 0.3
        
        return score
    
    def _calculate_community_score(self, community_metrics: Optional[Dict[str, Any]]) -> float:
        if not community_metrics:
            return 50.0
        
        score = 0.0
        
        if community_metrics.get('twitter_followers') is not None:
            twitter_score = min(100, community_metrics['twitter_followers'] / 10000)
            score += twitter_score * 0.4
        
        if community_metrics.get('reddit_subscribers') is not None:
            reddit_score = min(100, community_metrics['reddit_subscribers'] / 1000)
            score += reddit_score * 0.3
        
        if community_metrics.get('reddit_average_comments_48h') is not None:
            comments_score = min(100, community_metrics['reddit_average_comments_48h'] * 10)
            score += comments_score * 0.3
        
        return score if score > 0 else 50.0
    
    def _calculate_developer_score(self, developer_metrics: Optional[Dict[str, Any]]) -> float:
        if not developer_metrics:
            return 50.0
        
        score = 0.0
        
        if developer_metrics.get('stars') is not None:
            stars_score = min(100, developer_metrics['stars'] / 100)
            score += stars_score * 0.3
        
        if developer_metrics.get('forks') is not None:
            forks_score = min(100, developer_metrics['forks'] / 10)
            score += forks_score * 0.2
        
        if developer_metrics.get('commit_count_4_weeks') is not None:
            commit_score = min(100, developer_metrics['commit_count_4_weeks'] * 2)
            score += commit_score * 0.3
        
        if developer_metrics.get('pull_request_contributors') is not None:
            contributors_score = min(100, developer_metrics['pull_request_contributors'] * 5)
            score += contributors_score * 0.2
        
        return score if score > 0 else 50.0
