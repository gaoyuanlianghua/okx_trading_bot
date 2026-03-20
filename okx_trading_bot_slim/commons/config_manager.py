import os
import json
import threading
from typing import Dict, Any, Callable, Optional

# 初始化日志配置
from commons.logger_config import global_logger as logger

class ConfigManager:
    """
    集中化配置管理器，负责配置的加载、验证、热更新和提供
    """
    
    def __init__(self, config_path: str = "config/okx_config.json"):
        """
        初始化配置管理器
        
        Args:
            config_path (str): 配置文件路径
        """
        self.config_path = os.path.normpath(config_path)
        self._config: Dict[str, Any] = {}
        self._listeners: list[Callable[[Dict[str, Any]], None]] = []
        self._lock = threading.RLock()
        self._last_modified_time = 0
        self._default_config = self._get_default_config()
        
        # 加载初始配置
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
                "is_test": False,
                "timeout": 30,
                "api_url": "https://www.okx.com",
                "api_ips": [],
                "ws_ip": "",
                "ws_ips": [],
                "ws_open_timeout": 15.0,
                "ws_ping_timeout": 10.0,
                "ws_close_timeout": 5.0,
                "ws_max_queue": 1000,
                "ws_ping_interval": 20.0,
                "ssl_check_hostname": True,
                "ssl_verify_mode": "CERT_REQUIRED",
                "ssl_min_version": "TLSv1_2",
                "proxy": {
                    "enabled": False,
                    "http": "",
                    "https": "",
                    "socks5": ""
                },
                "api_ip": ""
            },
            "passivbot": {
                "config_path": "okx_trading_bot/strategies/passivbot/configs/default_config.json",
                "symbol": "BTC-USDT-SWAP",
                "timeframe": "1h"
            },
            "risk_management": {
                "max_leverage": 5,
                "stop_loss_percent": 0.03,
                "take_profit_percent": 0.05,
                "max_order_value": 1000,
                "max_position_value": 5000,
                "position_size_limit": 0.001,
                "risk_reward_ratio": 2,
                "max_daily_loss": 0.05,
                "max_drawdown": 0.1,
                "cooldown_period": 300,
                "leverage_adjustment_threshold": 0.02
            },
            "market_data": {
                "update_interval": 10,
                "candle_limit": 100,
                "order_book_depth": 10
            },
            "trading": {
                "enabled": False,
                "backtest_mode": True,
                "auto_restart": False,
                "notification_enabled": False
            },
            "network": {
                "enable_adaptation": True,
                "use_custom_dns": True
            }
        }
    
    def load_config(self) -> bool:
        """
        加载配置文件
        
        Returns:
            bool: 加载是否成功
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(self.config_path):
                logger.error(f"配置文件不存在: {self.config_path}")
                self._config = self._default_config.copy()
                return False
            
            # 检查文件修改时间
            file_modified_time = os.path.getmtime(self.config_path)
            if file_modified_time <= self._last_modified_time:
                return True
            
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            # 验证配置
            validated_config = self._validate_config(config)
            
            # 更新配置
            with self._lock:
                self._config = validated_config
                self._last_modified_time = file_modified_time
            
            logger.info(f"配置文件加载成功: {self.config_path}")
            
            # 通知监听器
            self._notify_listeners()
            
            return True
        except json.JSONDecodeError as e:
            logger.error(f"配置文件格式错误: {e}")
            self._config = self._default_config.copy()
            return False
        except PermissionError as e:
            logger.error(f"没有权限访问配置文件: {e}")
            self._config = self._default_config.copy()
            return False
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            self._config = self._default_config.copy()
            return False
    
    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证配置参数的有效性
        
        Args:
            config (Dict[str, Any]): 原始配置
            
        Returns:
            Dict[str, Any]: 验证后的配置
        """
        validated_config = self._default_config.copy()
        
        # 递归合并配置
        def merge_dict(dest: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
            for key, value in src.items():
                if key in dest and isinstance(dest[key], dict) and isinstance(value, dict):
                    dest[key] = merge_dict(dest[key], value)
                elif key in dest:
                    dest[key] = value
            return dest
        
        merged_config = merge_dict(validated_config, config)
        
        # 执行特定验证
        self._validate_api_config(merged_config["api"])
        self._validate_risk_config(merged_config["risk_management"])
        self._validate_market_data_config(merged_config["market_data"])
        self._validate_trading_config(merged_config["trading"])
        self._validate_passivbot_config(merged_config["passivbot"])
        
        # 确保network配置存在
        if "network" not in merged_config:
            merged_config["network"] = self._default_config["network"]
        else:
            # 确保network配置中的所有必要字段都存在
            for key, value in self._default_config["network"].items():
                if key not in merged_config["network"]:
                    merged_config["network"][key] = value
        
        return merged_config
    
    def _validate_api_config(self, api_config: Dict[str, Any]) -> None:
        """
        验证API配置
        
        Args:
            api_config (Dict[str, Any]): API配置
        """
        # 验证超时时间
        if api_config["timeout"] < 5:
            logger.warning("API超时时间过短，已调整为5秒")
            api_config["timeout"] = 5
        elif api_config["timeout"] > 60:
            logger.warning("API超时时间过长，已调整为60秒")
            api_config["timeout"] = 60
        
        # 验证代理配置
        if api_config["proxy"]["enabled"]:
            has_proxy_url = any(
                api_config["proxy"][proxy_type] 
                for proxy_type in ["socks5", "https", "http"]
            )
            if not has_proxy_url:
                logger.warning("代理已启用，但未配置代理URL，将禁用代理")
                api_config["proxy"]["enabled"] = False
    
    def _validate_risk_config(self, risk_config: Dict[str, Any]) -> None:
        """
        验证风险配置
        
        Args:
            risk_config (Dict[str, Any]): 风险配置
        """
        # 验证最大杠杆
        if risk_config["max_leverage"] < 1:
            logger.warning("最大杠杆不能小于1，已调整为1")
            risk_config["max_leverage"] = 1
        elif risk_config["max_leverage"] > 100:
            logger.warning("最大杠杆不能大于100，已调整为100")
            risk_config["max_leverage"] = 100
        
        # 验证止损和止盈百分比
        if risk_config["stop_loss_percent"] < 0:
            logger.warning("止损百分比不能为负，已调整为0.01")
            risk_config["stop_loss_percent"] = 0.01
        
        if risk_config["take_profit_percent"] < 0:
            logger.warning("止盈百分比不能为负，已调整为0.01")
            risk_config["take_profit_percent"] = 0.01
    
    def _validate_market_data_config(self, market_config: Dict[str, Any]) -> None:
        """
        验证市场数据配置
        
        Args:
            market_config (Dict[str, Any]): 市场数据配置
        """
        # 验证更新间隔
        if market_config["update_interval"] < 1:
            logger.warning("市场数据更新间隔过短，已调整为1秒")
            market_config["update_interval"] = 1
        elif market_config["update_interval"] > 60:
            logger.warning("市场数据更新间隔过长，已调整为60秒")
            market_config["update_interval"] = 60
    
    def _validate_trading_config(self, trading_config: Dict[str, Any]) -> None:
        """
        验证交易配置
        
        Args:
            trading_config (Dict[str, Any]): 交易配置
        """
        # 验证交易配置
        if trading_config["backtest_mode"] and trading_config["enabled"]:
            logger.warning("回测模式与实盘交易不能同时启用，已禁用实盘交易")
            trading_config["enabled"] = False
        
        # 验证自动重启配置
        if trading_config["auto_restart"] and not trading_config["enabled"]:
            logger.warning("自动重启仅在实盘交易启用时生效，已禁用自动重启")
            trading_config["auto_restart"] = False
    
    def _validate_passivbot_config(self, passivbot_config: Dict[str, Any]) -> None:
        """
        验证Passivbot配置
        
        Args:
            passivbot_config (Dict[str, Any]): Passivbot配置
        """
        # 验证时间周期
        valid_timeframes = ["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
        if passivbot_config["timeframe"] not in valid_timeframes:
            logger.warning(f"无效的时间周期: {passivbot_config['timeframe']}，已调整为1h")
            passivbot_config["timeframe"] = "1h"
    
    def get_config(self) -> Dict[str, Any]:
        """
        获取完整配置
        
        Returns:
            Dict[str, Any]: 配置字典
        """
        with self._lock:
            return self._config.copy()
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取指定键的配置值
        
        Args:
            key (str): 配置键，支持点分隔符（如 "api.timeout"）
            default (Any): 默认值
            
        Returns:
            Any: 配置值
        """
        with self._lock:
            keys = key.split(".")
            value = self._config
            
            try:
                for k in keys:
                    value = value[k]
                return value
            except (KeyError, TypeError):
                return default
    
    def add_listener(self, listener: Callable[[Dict[str, Any]], None]) -> None:
        """
        添加配置更新监听器
        
        Args:
            listener (Callable[[Dict[str, Any]], None]): 监听器函数
        """
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)
    
    def remove_listener(self, listener: Callable[[Dict[str, Any]], None]) -> None:
        """
        移除配置更新监听器
        
        Args:
            listener (Callable[[Dict[str, Any]], None]): 监听器函数
        """
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)
    
    def _notify_listeners(self) -> None:
        """
        通知所有监听器配置已更新
        """
        with self._lock:
            config_copy = self._config.copy()
            listeners = self._listeners.copy()
        
        for listener in listeners:
            try:
                listener(config_copy)
            except Exception as e:
                logger.error(f"通知配置更新监听器失败: {e}")
    
    def save_config(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        保存配置到文件
        
        Args:
            config (Optional[Dict[str, Any]]): 要保存的配置，默认为当前配置
            
        Returns:
            bool: 保存是否成功
        """
        try:
            if config is None:
                with self._lock:
                    config = self._config.copy()
            
            # 确保配置目录存在
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"配置已保存到文件: {self.config_path}")
            
            # 重新加载配置以更新修改时间
            self.load_config()
            
            return True
        except PermissionError as e:
            logger.error(f"没有权限写入配置文件: {e}")
            return False
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            return False
    
    def update_config(self, updates: Dict[str, Any]) -> bool:
        """
        更新配置
        
        Args:
            updates (Dict[str, Any]): 要更新的配置
            
        Returns:
            bool: 更新是否成功
        """
        try:
            with self._lock:
                # 递归更新配置
                def update_dict(dest: Dict[str, Any], src: Dict[str, Any]) -> None:
                    for key, value in src.items():
                        if key in dest and isinstance(dest[key], dict) and isinstance(value, dict):
                            update_dict(dest[key], value)
                        else:
                            dest[key] = value
                
                update_dict(self._config, updates)
                
                # 验证更新后的配置
                self._config = self._validate_config(self._config)
            
            # 保存到文件
            if self.save_config():
                logger.info("配置已更新")
                return True
            return False
        except Exception as e:
            logger.error(f"更新配置失败: {e}")
            return False

# 创建全局配置管理器实例
global_config_manager = ConfigManager()
