"""
分布式配置管理器 - 支持跨节点的配置同步
"""

import os
import json
import time
import threading
from typing import Dict, Any, Optional
import redis
import logging

from core.utils.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class DistributedConfigManager:
    """
    分布式配置管理器
    
    使用Redis作为配置存储，实现跨节点的配置同步
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0", config_file: str = "config.json"):
        """
        初始化分布式配置管理器
        
        Args:
            redis_url: Redis连接URL
            config_file: 本地配置文件路径
        """
        if self._initialized:
            return
        
        # 本地配置管理器
        self._local_config = ConfigManager(config_file)
        
        # Redis连接
        self._redis_url = redis_url
        self._redis = None
        
        # 配置键
        self._config_key = "okx_trading_bot:config"
        
        # 初始化Redis连接
        self._init_redis()
        
        # 配置版本
        self._version = 0
        
        # 运行状态
        self._running = False
        
        # 配置更新线程
        self._update_thread = None
        
        # 配置更新间隔（秒）
        self._update_interval = 5
        
        self._initialized = True
        
        logger.info("分布式配置管理器初始化完成")
    
    def _init_redis(self):
        """
        初始化Redis连接
        """
        try:
            self._redis = redis.from_url(self._redis_url, decode_responses=True)
            logger.info("Redis连接成功")
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            self._redis = None
    
    def start(self):
        """
        启动分布式配置管理器
        """
        self._running = True
        
        # 启动配置更新线程
        self._update_thread = threading.Thread(target=self._update_config_loop, daemon=True)
        self._update_thread.start()
        
        # 同步配置到Redis
        self._sync_config_to_redis()
        
        logger.info("分布式配置管理器已启动")
    
    def stop(self):
        """
        停止分布式配置管理器
        """
        self._running = False
        
        # 等待更新线程结束
        if self._update_thread and self._update_thread.is_alive():
            self._update_thread.join(timeout=2.0)
        
        # 关闭Redis连接
        if self._redis:
            self._redis.close()
        
        logger.info("分布式配置管理器已停止")
    
    def _update_config_loop(self):
        """
        配置更新循环
        """
        while self._running:
            try:
                # 从Redis同步配置
                self._sync_config_from_redis()
                
                # 等待一段时间
                time.sleep(self._update_interval)
            except Exception as e:
                logger.error(f"配置更新循环错误: {e}")
                time.sleep(self._update_interval)
    
    def _sync_config_to_redis(self):
        """
        同步配置到Redis
        """
        if not self._redis:
            return
        
        try:
            # 获取本地配置
            local_config = self._local_config.get_config()
            
            # 添加版本号和时间戳
            config_data = {
                "config": local_config,
                "version": self._version + 1,
                "timestamp": time.time()
            }
            
            # 序列化并存储到Redis
            config_json = json.dumps(config_data)
            self._redis.set(self._config_key, config_json)
            
            # 更新版本号
            self._version = config_data["version"]
            
            logger.debug(f"配置已同步到Redis, 版本: {self._version}")
        except Exception as e:
            logger.error(f"同步配置到Redis失败: {e}")
    
    def _sync_config_from_redis(self):
        """
        从Redis同步配置
        """
        if not self._redis:
            return
        
        try:
            # 从Redis获取配置
            config_json = self._redis.get(self._config_key)
            if not config_json:
                return
            
            # 解析配置
            config_data = json.loads(config_json)
            remote_config = config_data.get("config", {})
            remote_version = config_data.get("version", 0)
            
            # 检查版本号
            if remote_version > self._version:
                # 更新本地配置
                self._local_config.set_config(remote_config)
                self._version = remote_version
                logger.info(f"从Redis同步配置, 版本: {self._version}")
        except Exception as e:
            logger.error(f"从Redis同步配置失败: {e}")
    
    def get_config(self) -> Dict[str, Any]:
        """
        获取配置
        
        Returns:
            Dict[str, Any]: 配置
        """
        return self._local_config.get_config()
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            Any: 配置值
        """
        return self._local_config.get(key, default)
    
    def set(self, key: str, value: Any):
        """
        设置配置项
        
        Args:
            key: 配置键
            value: 配置值
        """
        self._local_config.set(key, value)
        self._sync_config_to_redis()
    
    def set_config(self, config: Dict[str, Any]):
        """
        设置完整配置
        
        Args:
            config: 配置
        """
        self._local_config.set_config(config)
        self._sync_config_to_redis()
    
    def reload(self):
        """
        重新加载配置
        """
        self._local_config.reload()
        self._sync_config_to_redis()
    
    def save(self):
        """
        保存配置
        """
        self._local_config.save()
        self._sync_config_to_redis()
    
    def get_version(self) -> int:
        """
        获取配置版本
        
        Returns:
            int: 版本号
        """
        return self._version
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            "version": self._version,
            "redis_connected": self._redis is not None,
            "update_interval": self._update_interval,
            "local_config_size": len(str(self._local_config.get_config()))
        }


# 全局分布式配置管理器实例
distributed_config_manager = DistributedConfigManager()