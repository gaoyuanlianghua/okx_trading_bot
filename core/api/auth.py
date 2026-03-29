"""
OKX API认证模块 - 处理API签名和认证
"""
import base64
import hmac
import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Optional


class OKXAuth:
    """
    OKX API认证类
    
    处理API请求的签名生成和认证头构建
    """
    
    def __init__(self, api_key: str, api_secret: str, passphrase: str, is_test: bool = False):
        """
        初始化认证器
        
        Args:
            api_key: API密钥
            api_secret: API密钥密码
            passphrase: 密码短语
            is_test: 是否为模拟盘
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.is_test = is_test
    
    def get_timestamp(self) -> str:
        """
        获取ISO格式的时间戳
        
        Returns:
            str: ISO格式时间戳，如 2020-12-08T09:08:57.715Z
        """
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    
    def sign(self, timestamp: str, method: str, request_path: str, body: str = '') -> str:
        """
        生成请求签名
        
        签名算法：
        sign = Base64(HMAC-SHA256(timestamp + method + requestPath + body, secretKey))
        
        Args:
            timestamp: 时间戳
            method: HTTP方法 (GET/POST)
            request_path: 请求路径
            body: 请求体（JSON字符串）
            
        Returns:
            str: Base64编码的签名
        """
        message = timestamp + method.upper() + request_path + body
        
        # 使用HMAC-SHA256生成签名
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        # Base64编码
        return base64.b64encode(signature).decode('utf-8')
    
    def get_headers(self, method: str, request_path: str, body: str = '') -> Dict[str, str]:
        """
        获取请求头
        
        Args:
            method: HTTP方法
            request_path: 请求路径
            body: 请求体
            
        Returns:
            Dict[str, str]: 请求头字典
        """
        timestamp = self.get_timestamp()
        signature = self.sign(timestamp, method, request_path, body)
        
        headers = {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
        
        # 模拟盘需要添加特殊头
        if self.is_test:
            headers['x-simulated-trading'] = '1'
        
        return headers
    
    def sign_websocket_login(self, timestamp: str) -> str:
        """
        生成WebSocket登录签名
        
        Args:
            timestamp: Unix时间戳（秒）
            
        Returns:
            str: Base64编码的签名
        """
        message = str(timestamp) + 'GET' + '/users/self/verify'
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        return base64.b64encode(signature).decode('utf-8')
    
    def get_websocket_login_params(self) -> Dict:
        """
        获取WebSocket登录参数
        
        Returns:
            Dict: 登录参数字典
        """
        import time
        timestamp = str(int(time.time()))
        signature = self.sign_websocket_login(timestamp)
        
        return {
            'op': 'login',
            'args': [
                {
                    'apiKey': self.api_key,
                    'passphrase': self.passphrase,
                    'timestamp': timestamp,
                    'sign': signature
                }
            ]
        }
    
    def is_configured(self) -> bool:
        """
        检查认证信息是否已配置
        
        Returns:
            bool: 是否已配置
        """
        return all([
            self.api_key and self.api_key != '-1',
            self.api_secret and self.api_secret != '-1',
            self.passphrase and self.passphrase != '-1'
        ])
