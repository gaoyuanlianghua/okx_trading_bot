"""
安全管理器

负责系统安全性，包括双因素认证、IP白名单等功能
"""

import os
import json
import time
import ipaddress
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pyotp
from cryptography.fernet import Fernet

from core.utils.logger import get_logger

logger = get_logger(__name__)


class SecurityManager:
    """
    安全管理器
    
    负责系统安全性，包括双因素认证、IP白名单等功能
    """
    
    def __init__(self, config_file: str = "security_config.json"):
        """
        初始化安全管理器
        
        Args:
            config_file: 安全配置文件路径
        """
        self.config_file = config_file
        self._config = self._load_config()
        self._fernet = self._load_encryption_key()
    
    def _load_config(self) -> Dict:
        """
        加载安全配置
        
        Returns:
            Dict: 安全配置
        """
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载安全配置失败: {e}")
                return self._get_default_config()
        else:
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """
        获取默认安全配置
        
        Returns:
            Dict: 默认安全配置
        """
        return {
            "2fa": {
                "enabled": False,
                "secret": None,
                "backup_codes": []
            },
            "ip_whitelist": {
                "enabled": False,
                "allowed_ips": []
            },
            "session": {
                "timeout": 3600,  # 会话超时时间（秒）
                "max_sessions": 5  # 最大会话数
            },
            "api_rate_limit": {
                "enabled": True,
                "requests_per_minute": 60
            }
        }
    
    def _load_encryption_key(self) -> Fernet:
        """
        加载或生成加密密钥
        
        Returns:
            Fernet: 加密对象
        """
        key_file = "security_encryption.key"
        
        if os.path.exists(key_file):
            try:
                with open(key_file, "rb") as f:
                    key = f.read()
                return Fernet(key)
            except Exception as e:
                logger.error(f"加载加密密钥失败: {e}")
        
        # 生成新的加密密钥
        key = Fernet.generate_key()
        with open(key_file, "wb") as f:
            f.write(key)
        
        # 设置文件权限
        if os.name == "nt":
            import win32security
            import win32api
            import win32con
            
            hfile = win32api.CreateFile(
                key_file,
                win32con.GENERIC_READ,
                0,
                None,
                win32con.OPEN_EXISTING,
                win32con.FILE_ATTRIBUTE_NORMAL,
                None,
            )
            
            sd = win32security.GetFileSecurity(
                key_file, win32security.DACL_SECURITY_INFORMATION
            )
            
            user = win32api.GetUserName()
            domain = win32api.GetUserNameEx(win32api.NameSamCompatible).split("\\")[0]
            user_sid = win32security.LookupAccountName(domain, user)[0]
            
            ace = win32security.ACL()
            ace.AddAccessAllowedAce(
                win32security.ACL_REVISION, win32con.FILE_ALL_ACCESS, user_sid
            )
            
            sd.SetSecurityDescriptorDacl(1, ace, 0)
            win32security.SetFileSecurity(
                key_file, win32security.DACL_SECURITY_INFORMATION, sd
            )
        else:
            os.chmod(key_file, 0o600)
        
        return Fernet(key)
    
    def _save_config(self):
        """
        保存安全配置
        """
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存安全配置失败: {e}")
    
    # ========== 双因素认证功能 ==========
    
    def enable_2fa(self) -> Dict:
        """
        启用双因素认证
        
        Returns:
            Dict: 包含密钥和备份码的字典
        """
        # 生成TOTP密钥
        secret = pyotp.random_base32()
        
        # 生成备份码
        backup_codes = [self._generate_backup_code() for _ in range(10)]
        
        # 加密存储
        encrypted_secret = self._fernet.encrypt(secret.encode()).decode()
        encrypted_codes = [self._fernet.encrypt(code.encode()).decode() for code in backup_codes]
        
        # 更新配置
        self._config["2fa"]["enabled"] = True
        self._config["2fa"]["secret"] = encrypted_secret
        self._config["2fa"]["backup_codes"] = encrypted_codes
        
        self._save_config()
        
        # 生成QR码URL
        totp = pyotp.TOTP(secret)
        qr_url = totp.provisioning_uri("OKX Trading Bot", issuer_name="OKX Trading Bot")
        
        return {
            "secret": secret,
            "backup_codes": backup_codes,
            "qr_url": qr_url
        }
    
    def disable_2fa(self):
        """
        禁用双因素认证
        """
        self._config["2fa"]["enabled"] = False
        self._config["2fa"]["secret"] = None
        self._config["2fa"]["backup_codes"] = []
        self._save_config()
        logger.info("双因素认证已禁用")
    
    def verify_2fa(self, code: str) -> bool:
        """
        验证双因素认证代码
        
        Args:
            code: 2FA代码
            
        Returns:
            bool: 是否验证成功
        """
        if not self._config["2fa"]["enabled"]:
            return True
        
        try:
            encrypted_secret = self._config["2fa"]["secret"]
            if not encrypted_secret:
                return False
            
            secret = self._fernet.decrypt(encrypted_secret.encode()).decode()
            totp = pyotp.TOTP(secret)
            return totp.verify(code)
        except Exception as e:
            logger.error(f"验证2FA代码失败: {e}")
            return False
    
    def verify_backup_code(self, code: str) -> bool:
        """
        验证备份码
        
        Args:
            code: 备份码
            
        Returns:
            bool: 是否验证成功
        """
        if not self._config["2fa"]["enabled"]:
            return True
        
        try:
            encrypted_codes = self._config["2fa"]["backup_codes"]
            
            for i, encrypted_code in enumerate(encrypted_codes):
                decrypted_code = self._fernet.decrypt(encrypted_code.encode()).decode()
                if decrypted_code == code:
                    # 使用后删除该备份码
                    encrypted_codes.pop(i)
                    self._save_config()
                    logger.info("备份码验证成功并已删除")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"验证备份码失败: {e}")
            return False
    
    def _generate_backup_code(self) -> str:
        """
        生成备份码
        
        Returns:
            str: 备份码
        """
        import secrets
        return secrets.token_hex(4).upper()
    
    # ========== IP白名单功能 ==========
    
    def enable_ip_whitelist(self):
        """
        启用IP白名单
        """
        self._config["ip_whitelist"]["enabled"] = True
        self._save_config()
        logger.info("IP白名单已启用")
    
    def disable_ip_whitelist(self):
        """
        禁用IP白名单
        """
        self._config["ip_whitelist"]["enabled"] = False
        self._save_config()
        logger.info("IP白名单已禁用")
    
    def add_ip_to_whitelist(self, ip: str) -> bool:
        """
        添加IP到白名单
        
        Args:
            ip: IP地址
            
        Returns:
            bool: 是否添加成功
        """
        try:
            # 验证IP地址格式
            ipaddress.ip_address(ip)
            
            if ip not in self._config["ip_whitelist"]["allowed_ips"]:
                self._config["ip_whitelist"]["allowed_ips"].append(ip)
                self._save_config()
                logger.info(f"IP {ip} 已添加到白名单")
                return True
            else:
                logger.warning(f"IP {ip} 已在白名单中")
                return False
        except ValueError as e:
            logger.error(f"无效的IP地址: {e}")
            return False
    
    def remove_ip_from_whitelist(self, ip: str) -> bool:
        """
        从白名单中移除IP
        
        Args:
            ip: IP地址
            
        Returns:
            bool: 是否移除成功
        """
        if ip in self._config["ip_whitelist"]["allowed_ips"]:
            self._config["ip_whitelist"]["allowed_ips"].remove(ip)
            self._save_config()
            logger.info(f"IP {ip} 已从白名单中移除")
            return True
        else:
            logger.warning(f"IP {ip} 不在白名单中")
            return False
    
    def check_ip_whitelist(self, ip: str) -> bool:
        """
        检查IP是否在白名单中
        
        Args:
            ip: IP地址
            
        Returns:
            bool: 是否在白名单中
        """
        if not self._config["ip_whitelist"]["enabled"]:
            return True
        
        try:
            client_ip = ipaddress.ip_address(ip)
            
            for allowed_ip in self._config["ip_whitelist"]["allowed_ips"]:
                try:
                    # 检查是否为CIDR范围
                    if "/" in allowed_ip:
                        network = ipaddress.ip_network(allowed_ip)
                        if client_ip in network:
                            return True
                    else:
                        allowed_ip_obj = ipaddress.ip_address(allowed_ip)
                        if client_ip == allowed_ip_obj:
                            return True
                except ValueError:
                    continue
            
            logger.warning(f"IP {ip} 不在白名单中")
            return False
        except ValueError as e:
            logger.error(f"无效的IP地址: {e}")
            return False
    
    # ========== 会话管理 ==========
    
    def check_session_timeout(self, last_activity: float) -> bool:
        """
        检查会话是否超时
        
        Args:
            last_activity: 最后活动时间戳
            
        Returns:
            bool: 是否超时
        """
        timeout = self._config["session"]["timeout"]
        return time.time() - last_activity > timeout
    
    def get_max_sessions(self) -> int:
        """
        获取最大会话数
        
        Returns:
            int: 最大会话数
        """
        return self._config["session"]["max_sessions"]
    
    # ========== API速率限制 ==========
    
    def is_rate_limit_enabled(self) -> bool:
        """
        检查API速率限制是否启用
        
        Returns:
            bool: 是否启用
        """
        return self._config["api_rate_limit"]["enabled"]
    
    def get_requests_per_minute(self) -> int:
        """
        获取每分钟允许的请求数
        
        Returns:
            int: 每分钟请求数
        """
        return self._config["api_rate_limit"]["requests_per_minute"]
    
    # ========== 安全状态 ==========
    
    def get_security_status(self) -> Dict:
        """
        获取安全状态
        
        Returns:
            Dict: 安全状态
        """
        return {
            "2fa_enabled": self._config["2fa"]["enabled"],
            "ip_whitelist_enabled": self._config["ip_whitelist"]["enabled"],
            "ip_whitelist_count": len(self._config["ip_whitelist"]["allowed_ips"]),
            "session_timeout": self._config["session"]["timeout"],
            "max_sessions": self._config["session"]["max_sessions"],
            "api_rate_limit_enabled": self._config["api_rate_limit"]["enabled"],
            "requests_per_minute": self._config["api_rate_limit"]["requests_per_minute"]
        }


# 创建全局安全管理器实例
security_manager = SecurityManager()