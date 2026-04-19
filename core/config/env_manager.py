"""
环境配置管理模块
管理实盘和模拟盘的切换
"""

import os
import json
import logging
from typing import Dict, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class EnvironmentManager:
    """
    环境管理器
    
    管理实盘和模拟盘的配置切换
    """
    
    # 环境类型
    ENV_LIVE = "live"
    ENV_TEST = "test"
    
    # 配置文件
    DEFAULT_CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
    LIVE_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config_live.yaml"
    TEST_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config_test.yaml"
    CURRENT_ENV_FILE = DEFAULT_CONFIG_DIR / "current_env.json"
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        初始化环境管理器
        
        Args:
            config_dir: 配置文件目录，如果为None则使用默认目录
        """
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = self.DEFAULT_CONFIG_DIR
        
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # 确保当前环境文件存在
        if not self.CURRENT_ENV_FILE.exists():
            self._save_current_env(self.ENV_LIVE)
        
        logger.info(f"环境管理器初始化完成，配置目录: {self.config_dir}")
    
    def _get_current_env(self) -> str:
        """
        获取当前环境
        
        Returns:
            str: 当前环境类型
        """
        try:
            if self.CURRENT_ENV_FILE.exists():
                with open(self.CURRENT_ENV_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('current_env', self.ENV_LIVE)
        except Exception as e:
            logger.warning(f"读取当前环境失败: {e}")
        
        return self.ENV_LIVE
    
    def _save_current_env(self, env: str):
        """
        保存当前环境
        
        Args:
            env: 环境类型
        """
        try:
            with open(self.CURRENT_ENV_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'current_env': env,
                    'updated_at': self._get_timestamp()
                }, f, indent=2, ensure_ascii=False)
            logger.info(f"当前环境已切换为: {env}")
        except Exception as e:
            logger.error(f"保存当前环境失败: {e}")
    
    def _get_timestamp(self) -> str:
        """获取ISO格式的时间戳"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
    
    def is_live_env(self) -> bool:
        """
        检查是否为实盘环境
        
        Returns:
            bool: 是否为实盘环境
        """
        return self._get_current_env() == self.ENV_LIVE
    
    def is_test_env(self) -> bool:
        """
        检查是否为模拟盘环境
        
        Returns:
            bool: 是否为模拟盘环境
        """
        return self._get_current_env() == self.ENV_TEST
    
    def get_current_env(self) -> str:
        """
        获取当前环境类型
        
        Returns:
            str: 当前环境类型
        """
        return self._get_current_env()
    
    def switch_to_live(self) -> bool:
        """
        切换到实盘环境
        
        Returns:
            bool: 是否切换成功
        """
        try:
            self._save_current_env(self.ENV_LIVE)
            return True
        except Exception as e:
            logger.error(f"切换到实盘环境失败: {e}")
            return False
    
    def switch_to_test(self) -> bool:
        """
        切换到模拟盘环境
        
        Returns:
            bool: 是否切换成功
        """
        try:
            self._save_current_env(self.ENV_TEST)
            return True
        except Exception as e:
            logger.error(f"切换到模拟盘环境失败: {e}")
            return False
    
    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """
        验证配置
        
        Args:
            config: 配置信息
            
        Returns:
            bool: 是否验证通过
        """
        try:
            # 验证 API 配置
            api_config = config.get('api', {})
            required_api_fields = ['api_key', 'api_secret', 'passphrase']
            for field in required_api_fields:
                if field not in api_config:
                    logger.warning(f"API 配置缺少必要字段: {field}")
            
            # 验证交易配置
            trading_config = config.get('trading', {})
            valid_trading_modes = ['cash', 'cross', 'isolated']
            if 'default_trading_mode' in trading_config and trading_config['default_trading_mode'] not in valid_trading_modes:
                logger.warning(f"无效的交易模式: {trading_config['default_trading_mode']}")
            
            # 验证策略配置
            strategy_config = config.get('strategy', {})
            if 'default_strategy' not in strategy_config:
                logger.warning("策略配置缺少必要字段: default_strategy")
            
            # 验证市场配置
            market_config = config.get('market', {})
            if 'cryptocurrencies' in market_config and not isinstance(market_config['cryptocurrencies'], list):
                logger.warning("市场配置中的 cryptocurrencies 必须是列表")
            
            # 验证通知配置
            notification_config = config.get('notification', {})
            if 'email' in notification_config and notification_config['email'].get('enabled', False):
                required_email_fields = ['smtp_server', 'smtp_port', 'sender_email', 'sender_password', 'receiver_email']
                for field in required_email_fields:
                    if field not in notification_config['email']:
                        logger.warning(f"邮件配置缺少必要字段: {field}")
            
            if 'telegram' in notification_config and notification_config['telegram'].get('enabled', False):
                required_telegram_fields = ['bot_token', 'chat_id']
                for field in required_telegram_fields:
                    if field not in notification_config['telegram']:
                        logger.warning(f"Telegram 配置缺少必要字段: {field}")
            
            return True
        except Exception as e:
            logger.error(f"配置验证失败: {e}")
            return False
    
    def get_env_config(self, env: Optional[str] = None) -> Dict[str, Any]:
        """
        获取指定环境的配置
        
        Args:
            env: 环境类型，如果为None则使用当前环境
            
        Returns:
            Dict[str, Any]: 配置信息
        """
        if env is None:
            env = self._get_current_env()
        
        config_file = self.LIVE_CONFIG_FILE if env == self.ENV_LIVE else self.TEST_CONFIG_FILE
        
        if not config_file.exists():
            # 如果环境配置文件不存在，尝试使用默认配置文件
            default_config_file = self.config_dir / "config.yaml"
            if default_config_file.exists():
                logger.warning(f"{env} 环境配置文件不存在，使用默认配置文件")
                config_file = default_config_file
            else:
                logger.error(f"配置文件不存在: {config_file}")
                return {}
        
        try:
            import yaml
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
                # 验证配置
                self._validate_config(config)
                return config
        except Exception as e:
            logger.error(f"读取配置文件失败: {config_file}, 错误: {e}")
            return {}
    
    def get_api_config(self, env: Optional[str] = None) -> Dict[str, str]:
        """
        获取API配置

        Args:
            env: 环境类型，如果为None则使用当前环境
            
        Returns:
            Dict[str, str]: API配置
        """
        config = self.get_env_config(env)
        api_config = config.get('api', {})
        
        return {
            'api_key': api_config.get('api_key', ''),
            'api_secret': api_config.get('api_secret', ''),
            'passphrase': api_config.get('passphrase', ''),
            'is_test': api_config.get('is_test', env == self.ENV_TEST if env else self.is_test_env()),
            'timeout': api_config.get('timeout', 30)
        }
    
    def get_trading_config(self, env: Optional[str] = None) -> Dict[str, Any]:
        """
        获取交易配置

        Args:
            env: 环境类型，如果为None则使用当前环境
            
        Returns:
            Dict[str, Any]: 交易配置
        """
        config = self.get_env_config(env)
        trading_config = config.get('trading', {})
        
        return {
            'default_trading_mode': trading_config.get('default_trading_mode', 'cash'),
            'max_position_size': trading_config.get('max_position_size', 1000),
            'min_order_amount': trading_config.get('min_order_amount', 1),
            'fixed_trade_amount': trading_config.get('fixed_trade_amount', 1),
            'leverage': trading_config.get('leverage', 1),
            'risk_per_trade': trading_config.get('risk_per_trade', 0.01),
            'stop_loss_percent': trading_config.get('stop_loss_percent', 0.02),
            'take_profit_percent': trading_config.get('take_profit_percent', 0.05)
        }
    
    def get_strategy_config(self, env: Optional[str] = None) -> Dict[str, Any]:
        """
        获取策略配置

        Args:
            env: 环境类型，如果为None则使用当前环境
            
        Returns:
            Dict[str, Any]: 策略配置
        """
        config = self.get_env_config(env)
        strategy_config = config.get('strategy', {})
        
        return {
            'default_strategy': strategy_config.get('default_strategy', 'NuclearDynamicsStrategy'),
            'enabled_strategies': strategy_config.get('enabled_strategies', ['NuclearDynamicsStrategy']),
            'strategy_params': strategy_config.get('strategy_params', {}),
            'signal_threshold': strategy_config.get('signal_threshold', 0.5),
            'signal_cooldown': strategy_config.get('signal_cooldown', 60)
        }
    
    def get_market_config(self, env: Optional[str] = None) -> Dict[str, Any]:
        """
        获取市场配置

        Args:
            env: 环境类型，如果为None则使用当前环境
            
        Returns:
            Dict[str, Any]: 市场配置
        """
        config = self.get_env_config(env)
        market_config = config.get('market', {})
        
        return {
            'cryptocurrencies': market_config.get('cryptocurrencies', ['BTC', 'ETH']),
            'update_interval': market_config.get('update_interval', 5),
            'orderbook_depth': market_config.get('orderbook_depth', 5),
            'candle_interval': market_config.get('candle_interval', '1m')
        }
    
    def get_notification_config(self, env: Optional[str] = None) -> Dict[str, Any]:
        """
        获取通知配置

        Args:
            env: 环境类型，如果为None则使用当前环境
            
        Returns:
            Dict[str, Any]: 通知配置
        """
        config = self.get_env_config(env)
        notification_config = config.get('notification', {})
        
        return {
            'email': notification_config.get('email', {}),
            'telegram': notification_config.get('telegram', {}),
            'webhook': notification_config.get('webhook', {})
        }
    
    def get_env_info(self) -> Dict[str, Any]:
        """
        获取环境信息

        Returns:
            Dict[str, Any]: 环境信息
        """
        current_env = self._get_current_env()
        return {
            'current_env': current_env,
            'is_live': current_env == self.ENV_LIVE,
            'is_test': current_env == self.ENV_TEST,
            'live_config_exists': self.LIVE_CONFIG_FILE.exists(),
            'test_config_exists': self.TEST_CONFIG_FILE.exists(),
            'config_dir': str(self.config_dir),
            'trading_config': self.get_trading_config(),
            'strategy_config': self.get_strategy_config(),
            'market_config': self.get_market_config(),
            'notification_config': self.get_notification_config()
        }
    
    def reload_config(self) -> bool:
        """
        重新加载配置

        Returns:
            bool: 是否成功
        """
        try:
            # 重新加载环境配置
            current_env = self._get_current_env()
            config_file = self.LIVE_CONFIG_FILE if current_env == self.ENV_LIVE else self.TEST_CONFIG_FILE
            
            if not config_file.exists():
                # 如果环境配置文件不存在，尝试使用默认配置文件
                default_config_file = self.config_dir / "config.yaml"
                if default_config_file.exists():
                    config_file = default_config_file
                else:
                    logger.error(f"配置文件不存在: {config_file}")
                    return False
            
            import yaml
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
                # 验证配置
                self._validate_config(config)
                
            logger.info("配置已重新加载")
            return True
        except Exception as e:
            logger.error(f"重新加载配置失败: {e}")
            return False
    
    def switch_trading_mode(self, trading_mode: str) -> bool:
        """
        切换交易模式

        Args:
            trading_mode: 交易模式 (cash/cross/isolated)
            
        Returns:
            bool: 是否切换成功
        """
        try:
            # 验证交易模式
            valid_modes = ['cash', 'cross', 'isolated']
            if trading_mode not in valid_modes:
                logger.error(f"无效的交易模式: {trading_mode}")
                return False
            
            # 更新配置文件
            config = self.get_env_config()
            if 'trading' not in config:
                config['trading'] = {}
            config['trading']['default_trading_mode'] = trading_mode
            
            # 保存配置
            env = self._get_current_env()
            config_file = self.LIVE_CONFIG_FILE if env == self.ENV_LIVE else self.TEST_CONFIG_FILE
            
            import yaml
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"交易模式已切换为: {trading_mode}")
            return True
        except Exception as e:
            logger.error(f"切换交易模式失败: {e}")
            return False
    
    def switch_strategy(self, strategy_name: str) -> bool:
        """
        切换默认策略

        Args:
            strategy_name: 策略名称
            
        Returns:
            bool: 是否切换成功
        """
        try:
            # 更新配置文件
            config = self.get_env_config()
            if 'strategy' not in config:
                config['strategy'] = {}
            config['strategy']['default_strategy'] = strategy_name
            
            # 保存配置
            env = self._get_current_env()
            config_file = self.LIVE_CONFIG_FILE if env == self.ENV_LIVE else self.TEST_CONFIG_FILE
            
            import yaml
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"默认策略已切换为: {strategy_name}")
            return True
        except Exception as e:
            logger.error(f"切换策略失败: {e}")
            return False


# 创建全局环境管理器实例
env_manager = EnvironmentManager()
