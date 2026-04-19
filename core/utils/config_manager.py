"""
配置管理模块

提供灵活的配置文件管理和热更新功能
"""

import os
import json
import yaml
import time
from typing import Dict, Any, Optional
import logging
from pathlib import Path

from core.utils.logger import get_logger

logger = get_logger(__name__)


class ConfigManager:
    """配置管理类"""
    
    def __init__(self, config_dir: str = "config", config_file: str = "config.yaml"):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置文件目录
            config_file: 配置文件名
        """
        self.config_dir = config_dir
        self.config_file = config_file
        self.config_path = os.path.join(config_dir, config_file)
        self._config: Dict[str, Any] = {}
        self._last_modified_time = 0
        self._watch_interval = 10  # 配置文件监控间隔（秒）
        self._watch_task = None
        
        # 创建配置目录
        os.makedirs(config_dir, exist_ok=True)
        
        # 加载配置
        self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        Returns:
            Dict[str, Any]: 配置字典
        """
        try:
            if os.path.exists(self.config_path):
                # 根据文件扩展名选择解析方式
                ext = os.path.splitext(self.config_file)[1].lower()
                
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    if ext in ['.yaml', '.yml']:
                        self._config = yaml.safe_load(f)
                    elif ext == '.json':
                        self._config = json.load(f)
                    else:
                        raise ValueError(f"不支持的配置文件格式: {ext}")
                
                # 更新最后修改时间
                self._last_modified_time = os.path.getmtime(self.config_path)
                logger.info(f"配置文件加载成功: {self.config_path}")
            else:
                # 创建默认配置
                self._config = self._get_default_config()
                self.save_config()
                logger.info(f"默认配置文件已创建: {self.config_path}")
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            # 使用默认配置
            self._config = self._get_default_config()
        
        return self._config
    
    def save_config(self) -> bool:
        """
        保存配置到文件
        
        Returns:
            bool: 是否保存成功
        """
        try:
            # 根据文件扩展名选择保存方式
            ext = os.path.splitext(self.config_file)[1].lower()
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                if ext in ['.yaml', '.yml']:
                    yaml.dump(self._config, f, default_flow_style=False, allow_unicode=True)
                elif ext == '.json':
                    json.dump(self._config, f, indent=2, ensure_ascii=False)
                else:
                    raise ValueError(f"不支持的配置文件格式: {ext}")
            
            # 更新最后修改时间
            self._last_modified_time = os.path.getmtime(self.config_path)
            logger.info(f"配置文件保存成功: {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键，支持点号分隔的路径
            default: 默认值
            
        Returns:
            Any: 配置值
        """
        # 检查配置文件是否有更新
        self._check_config_update()
        
        # 支持点号分隔的路径
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> bool:
        """
        设置配置值
        
        Args:
            key: 配置键，支持点号分隔的路径
            value: 配置值
            
        Returns:
            bool: 是否设置成功
        """
        # 支持点号分隔的路径
        keys = key.split('.')
        config = self._config
        
        # 遍历到最后一个键的父级
        for k in keys[:-1]:
            if k not in config or not isinstance(config[k], dict):
                config[k] = {}
            config = config[k]
        
        # 设置值
        config[keys[-1]] = value
        
        # 保存到文件
        return self.save_config()
    
    def update(self, config: Dict[str, Any]) -> bool:
        """
        更新配置
        
        Args:
            config: 配置字典
            
        Returns:
            bool: 是否更新成功
        """
        try:
            # 深度更新配置
            self._deep_update(self._config, config)
            # 保存到文件
            return self.save_config()
        except Exception as e:
            logger.error(f"更新配置失败: {e}")
            return False
    
    def _deep_update(self, target: Dict[str, Any], source: Dict[str, Any]):
        """
        深度更新字典
        
        Args:
            target: 目标字典
            source: 源字典
        """
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_update(target[key], value)
            else:
                target[key] = value
    
    def _check_config_update(self):
        """
        检查配置文件是否有更新
        """
        if os.path.exists(self.config_path):
            current_modified_time = os.path.getmtime(self.config_path)
            if current_modified_time > self._last_modified_time:
                logger.info("配置文件已更新，重新加载...")
                self.load_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        获取默认配置
        
        Returns:
            Dict[str, Any]: 默认配置
        """
        return {
            "api": {
                "api_key": "",
                "api_secret": "",
                "passphrase": "",
                "is_test": True,
                "timeout": 30
            },
            "strategy": {
                "default_strategy": "DynamicsStrategy",
                "strategies": {
                    "DynamicsStrategy": {
                        "ε": 0.85,
                        "G_eff": 1.2e-3,
                        "position_size": 0.1,
                        "max_position": 0.5,
                        "stop_loss": 0.02,
                        "take_profit": 0.05
                    }
                }
            },
            "market": {
                "default_inst_id": "BTC-USDT-SWAP",
                "subscribed_instruments": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
                "websocket": {
                    "ping_interval": 20,
                    "reconnect_attempts": 10,
                    "reconnect_delay": 5
                }
            },
            "risk": {
                "max_drawdown": 0.1,
                "max_leverage": 10,
                "max_position_percent": 0.5,
                "stop_loss_enabled": True,
                "take_profit_enabled": True,
                "alert_thresholds": {
                    "drawdown": 0.05,
                    "position_size": 0.4,
                    "leverage": 8
                }
            },
            "backtesting": {
                "initial_balance": 10000,
                "data_source": "okx",
                "timeframe": "1m",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31"
            },
            "gui": {
                "theme": "light",
                "refresh_interval": 2,
                "show_count": 20
            },
            "logging": {
                "level": "INFO",
                "structured": False,
                "log_dir": "logs"
            }
        }
    
    def get_full_config(self) -> Dict[str, Any]:
        """
        获取完整配置
        
        Returns:
            Dict[str, Any]: 完整配置
        """
        # 检查配置文件是否有更新
        self._check_config_update()
        return self._config
    
    def watch_config(self, callback: Optional[callable] = None):
        """
        开始监控配置文件变化
        
        Args:
            callback: 配置变化时的回调函数
        """
        import asyncio
        
        async def watch_task():
            while True:
                await asyncio.sleep(self._watch_interval)
                old_config = self._config.copy()
                self._check_config_update()
                if old_config != self._config and callback:
                    callback(self._config)
        
        if self._watch_task is None:
            self._watch_task = asyncio.ensure_future(watch_task())
            logger.info("配置文件监控已启动")
    
    def stop_watching(self):
        """
        停止监控配置文件变化
        """
        if self._watch_task:
            self._watch_task.cancel()
            self._watch_task = None
            logger.info("配置文件监控已停止")


# 全局配置管理器实例
config_manager = ConfigManager()


def get_config(key: str, default: Any = None) -> Any:
    """
    获取配置值的便捷函数
    
    Args:
        key: 配置键
        default: 默认值
        
    Returns:
        Any: 配置值
    """
    return config_manager.get(key, default)


def set_config(key: str, value: Any) -> bool:
    """
    设置配置值的便捷函数
    
    Args:
        key: 配置键
        value: 配置值
        
    Returns:
        bool: 是否设置成功
    """
    return config_manager.set(key, value)


def update_config(config: Dict[str, Any]) -> bool:
    """
    更新配置的便捷函数
    
    Args:
        config: 配置字典
        
    Returns:
        bool: 是否更新成功
    """
    return config_manager.update(config)


def get_full_config() -> Dict[str, Any]:
    """
    获取完整配置的便捷函数
    
    Returns:
        Dict[str, Any]: 完整配置
    """
    return config_manager.get_full_config()
