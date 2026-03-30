import asyncio
import json
import time
from typing import Dict, List, Optional, Any
from core.utils.logger import get_logger
from core.events.event_bus import EventBus

logger = get_logger(__name__)

class SocialTradingManager:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.strategy_leaderboard: Dict[str, Dict[str, Any]] = {}
        self.followers: Dict[str, List[str]] = {}
        self.follower_settings: Dict[str, Dict[str, Any]] = {}
        self.strategy_performance: Dict[str, Dict[str, Any]] = {}
        self.event_bus.subscribe('strategy_update', self.handle_strategy_update)
    
    async def register_strategy(self, strategy_id: str, strategy_name: str, description: str, owner: str):
        if strategy_id not in self.strategy_leaderboard:
            self.strategy_leaderboard[strategy_id] = {
                'strategy_name': strategy_name,
                'description': description,
                'owner': owner,
                'created_at': time.time(),
                'performance': [],
                'followers_count': 0
            }
            logger.info(f"Strategy registered: {strategy_name} (ID: {strategy_id})")
    
    async def update_strategy_performance(self, strategy_id: str, performance_data: Dict[str, Any]):
        if strategy_id in self.strategy_leaderboard:
            timestamp = time.time()
            performance_data['timestamp'] = timestamp
            self.strategy_leaderboard[strategy_id]['performance'].append(performance_data)
            
            if len(self.strategy_leaderboard[strategy_id]['performance']) > 100:
                self.strategy_leaderboard[strategy_id]['performance'] = self.strategy_leaderboard[strategy_id]['performance'][-100:]
            
            logger.info(f"Strategy performance updated: {strategy_id}")
    
    async def follow_strategy(self, user_id: str, strategy_id: str, settings: Dict[str, Any]):
        if strategy_id not in self.strategy_leaderboard:
            logger.error(f"Strategy not found: {strategy_id}")
            return False
        
        if strategy_id not in self.followers:
            self.followers[strategy_id] = []
        
        if user_id not in self.followers[strategy_id]:
            self.followers[strategy_id].append(user_id)
            self.strategy_leaderboard[strategy_id]['followers_count'] = len(self.followers[strategy_id])
        
        self.follower_settings[f"{user_id}_{strategy_id}"] = settings
        logger.info(f"User {user_id} is now following strategy {strategy_id}")
        return True
    
    async def unfollow_strategy(self, user_id: str, strategy_id: str):
        if strategy_id in self.followers and user_id in self.followers[strategy_id]:
            self.followers[strategy_id].remove(user_id)
            self.strategy_leaderboard[strategy_id]['followers_count'] = len(self.followers[strategy_id])
            
            key = f"{user_id}_{strategy_id}"
            if key in self.follower_settings:
                del self.follower_settings[key]
            
            logger.info(f"User {user_id} has unfollowed strategy {strategy_id}")
            return True
        return False
    
    async def get_strategy_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        sorted_strategies = sorted(
            self.strategy_leaderboard.values(),
            key=lambda x: x.get('performance', [{}])[-1].get('total_return', 0) if x.get('performance') else 0,
            reverse=True
        )
        return sorted_strategies[:limit]
    
    async def get_strategy_details(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        return self.strategy_leaderboard.get(strategy_id)
    
    async def handle_strategy_update(self, event: Dict[str, Any]):
        strategy_id = event.get('strategy_id')
        action = event.get('action')
        params = event.get('params', {})
        
        if strategy_id in self.followers:
            for follower_id in self.followers[strategy_id]:
                settings = self.follower_settings.get(f"{follower_id}_{strategy_id}", {})
                await self._execute_follower_action(follower_id, strategy_id, action, params, settings)
    
    async def _execute_follower_action(self, follower_id: str, strategy_id: str, action: str, params: Dict[str, Any], settings: Dict[str, Any]):
        scaling_factor = settings.get('scaling_factor', 1.0)
        max_position_size = settings.get('max_position_size', None)
        
        if action == 'place_order':
            order_params = params.copy()
            if 'size' in order_params:
                order_params['size'] = float(order_params['size']) * scaling_factor
                if max_position_size and order_params['size'] > max_position_size:
                    order_params['size'] = max_position_size
            
            await self.event_bus.publish('social_trading_order', {
                'follower_id': follower_id,
                'strategy_id': strategy_id,
                'action': action,
                'params': order_params
            })
            logger.info(f"Executed social trading order for follower {follower_id} from strategy {strategy_id}")
    
    async def get_follower_stats(self, user_id: str) -> Dict[str, Any]:
        followed_strategies = []
        for strategy_id, followers in self.followers.items():
            if user_id in followers:
                settings = self.follower_settings.get(f"{user_id}_{strategy_id}", {})
                strategy_info = self.strategy_leaderboard.get(strategy_id, {})
                followed_strategies.append({
                    'strategy_id': strategy_id,
                    'strategy_name': strategy_info.get('strategy_name'),
                    'settings': settings
                })
        
        return {
            'user_id': user_id,
            'followed_strategies': followed_strategies,
            'total_followed': len(followed_strategies)
        }
