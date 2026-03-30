import asyncio
import time
import functools
from typing import Dict, List, Optional, Any, Callable
from core.utils.logger import get_logger

logger = get_logger(__name__)

class APIPerformanceOptimizer:
    def __init__(self):
        self.cache = {}
        self.rate_limits = {}
        self.request_history = {}
        self.consecutive_failures = {}
        self.retry_delays = {}
    
    def cache_response(self, ttl: int = 30):
        """
        缓存装饰器，缓存API响应
        
        Args:
            ttl: 缓存过期时间（秒）
        """
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # 生成缓存键
                cache_key = f"{func.__name__}_{str(args)}_{str(kwargs)}"
                
                # 检查缓存
                if cache_key in self.cache:
                    cached_data, timestamp = self.cache[cache_key]
                    if time.time() - timestamp < ttl:
                        logger.debug(f"Cache hit for {func.__name__}")
                        return cached_data
                
                # 调用原始函数
                result = await func(*args, **kwargs)
                
                # 更新缓存
                self.cache[cache_key] = (result, time.time())
                logger.debug(f"Cache set for {func.__name__}")
                
                # 清理过期缓存
                await self._cleanup_cache()
                
                return result
            return wrapper
        return decorator
    
    def rate_limit(self, max_calls: int, period: int):
        """
        速率限制装饰器，限制API调用频率
        
        Args:
            max_calls: 最大调用次数
            period: 时间窗口（秒）
        """
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                func_name = func.__name__
                
                # 初始化速率限制记录
                if func_name not in self.rate_limits:
                    self.rate_limits[func_name] = []
                
                # 清理过期的调用记录
                now = time.time()
                self.rate_limits[func_name] = [t for t in self.rate_limits[func_name] if now - t < period]
                
                # 检查是否达到速率限制
                if len(self.rate_limits[func_name]) >= max_calls:
                    # 计算需要等待的时间
                    wait_time = period - (now - self.rate_limits[func_name][0])
                    if wait_time > 0:
                        logger.debug(f"Rate limit hit for {func_name}, waiting {wait_time:.2f}s")
                        await asyncio.sleep(wait_time)
                
                # 记录本次调用
                self.rate_limits[func_name].append(time.time())
                
                # 调用原始函数
                return await func(*args, **kwargs)
            return wrapper
        return decorator
    
    def retry_on_failure(self, max_retries: int = 3, backoff_factor: float = 0.5):
        """
        失败重试装饰器
        
        Args:
            max_retries: 最大重试次数
            backoff_factor: 退避因子
        """
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                func_name = func.__name__
                
                # 初始化失败计数
                if func_name not in self.consecutive_failures:
                    self.consecutive_failures[func_name] = 0
                
                # 初始化重试延迟
                if func_name not in self.retry_delays:
                    self.retry_delays[func_name] = 0
                
                retries = 0
                while retries <= max_retries:
                    try:
                        # 调用原始函数
                        result = await func(*args, **kwargs)
                        
                        # 重置失败计数和延迟
                        self.consecutive_failures[func_name] = 0
                        self.retry_delays[func_name] = 0
                        
                        return result
                    except Exception as e:
                        retries += 1
                        if retries > max_retries:
                            logger.error(f"Max retries reached for {func_name}: {e}")
                            raise
                        
                        # 增加失败计数
                        self.consecutive_failures[func_name] += 1
                        
                        # 计算退避时间
                        delay = backoff_factor * (2 ** (retries - 1)) + self.retry_delays[func_name]
                        self.retry_delays[func_name] = delay
                        
                        logger.warning(f"Retry {retries}/{max_retries} for {func_name} after {delay:.2f}s: {e}")
                        await asyncio.sleep(delay)
            return wrapper
        return decorator
    
    async def _cleanup_cache(self):
        """
        清理过期缓存
        """
        now = time.time()
        expired_keys = []
        
        for key, (_, timestamp) in self.cache.items():
            # 检查缓存是否过期（默认30秒）
            if now - timestamp > 30:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def batch_request(self, max_batch_size: int = 10):
        """
        批量请求装饰器
        
        Args:
            max_batch_size: 最大批量大小
        """
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # 检查是否需要批量处理
                if 'batch' in kwargs and kwargs['batch']:
                    items = kwargs.get('items', [])
                    results = []
                    
                    # 分批处理
                    for i in range(0, len(items), max_batch_size):
                        batch_items = items[i:i + max_batch_size]
                        batch_kwargs = kwargs.copy()
                        batch_kwargs['items'] = batch_items
                        batch_kwargs['batch'] = False
                        
                        batch_result = await func(*args, **batch_kwargs)
                        results.extend(batch_result)
                    
                    return results
                else:
                    # 正常调用
                    return await func(*args, **kwargs)
            return wrapper
        return decorator
    
    def track_performance(self, func: Callable) -> Callable:
        """
        性能跟踪装饰器
        
        Args:
            func: 要跟踪的函数
            
        Returns:
            Callable: 装饰后的函数
        """
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # 记录执行时间
                func_name = func.__name__
                if func_name not in self.request_history:
                    self.request_history[func_name] = []
                
                self.request_history[func_name].append(execution_time)
                
                # 限制历史记录长度
                if len(self.request_history[func_name]) > 100:
                    self.request_history[func_name] = self.request_history[func_name][-100:]
                
                logger.debug(f"{func_name} executed in {execution_time:.4f}s")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"{func.__name__} failed in {execution_time:.4f}s: {e}")
                raise
        return wrapper
    
    def get_performance_stats(self, func_name: Optional[str] = None) -> Dict[str, Any]:
        """
        获取性能统计信息
        
        Args:
            func_name: 函数名称，None表示获取所有函数的统计信息
            
        Returns:
            Dict: 性能统计信息
        """
        if func_name:
            if func_name not in self.request_history:
                return {}
            
            times = self.request_history[func_name]
            return {
                'function': func_name,
                'calls': len(times),
                'avg_time': sum(times) / len(times),
                'min_time': min(times),
                'max_time': max(times),
                'last_calls': times[-10:]
            }
        else:
            stats = {}
            for name, times in self.request_history.items():
                stats[name] = {
                    'calls': len(times),
                    'avg_time': sum(times) / len(times),
                    'min_time': min(times),
                    'max_time': max(times)
                }
            return stats
    
    def clear_cache(self, func_name: Optional[str] = None):
        """
        清除缓存
        
        Args:
            func_name: 函数名称，None表示清除所有缓存
        """
        if func_name:
            # 清除特定函数的缓存
            keys_to_delete = []
            for key in self.cache:
                if func_name in key:
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self.cache[key]
            
            logger.info(f"Cleared cache for {func_name}")
        else:
            # 清除所有缓存
            cache_size = len(self.cache)
            self.cache.clear()
            logger.info(f"Cleared all cache ({cache_size} entries)")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            Dict: 缓存统计信息
        """
        now = time.time()
        cache_age = []
        
        for _, (_, timestamp) in self.cache.items():
            cache_age.append(now - timestamp)
        
        if cache_age:
            return {
                'total_entries': len(self.cache),
                'avg_age': sum(cache_age) / len(cache_age),
                'max_age': max(cache_age),
                'min_age': min(cache_age)
            }
        else:
            return {
                'total_entries': 0
            }
