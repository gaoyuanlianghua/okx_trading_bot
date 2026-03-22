"""
错误处理器单元测试
"""

import unittest
from commons.error_handler import (
    ErrorLevel, TradingBotError, NetworkError, APIError, ValidationError,
    ConfigurationError, ResourceError, TradingError, RiskError,
    ErrorHandler, error_handler, retry, global_error_handler
)


class TestErrorHandler(unittest.TestCase):
    """测试错误处理器功能"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.error_handler = ErrorHandler()
    
    def test_error_creation(self):
        """测试错误对象创建"""
        error = TradingBotError("测试错误", "TEST_ERROR", ErrorLevel.WARNING)
        
        self.assertEqual(error.message, "测试错误")
        self.assertEqual(error.error_code, "TEST_ERROR")
        self.assertEqual(error.error_level, ErrorLevel.WARNING)
    
    def test_network_error(self):
        """测试网络错误"""
        error = NetworkError("网络连接失败")
        
        self.assertEqual(error.message, "网络连接失败")
        self.assertEqual(error.error_code, "NETWORK_ERROR")
        self.assertEqual(error.error_level, ErrorLevel.ERROR)
    
    def test_api_error(self):
        """测试API错误"""
        error = APIError("API请求失败", "API_404", 404)
        
        self.assertEqual(error.message, "API请求失败")
        self.assertEqual(error.error_code, "API_404")
        self.assertEqual(error.http_status, 404)
    
    def test_validation_error(self):
        """测试验证错误"""
        error = ValidationError("参数验证失败")
        
        self.assertEqual(error.message, "参数验证失败")
        self.assertEqual(error.error_code, "VALIDATION_ERROR")
        self.assertEqual(error.error_level, ErrorLevel.WARNING)
    
    def test_configuration_error(self):
        """测试配置错误"""
        error = ConfigurationError("配置文件错误")
        
        self.assertEqual(error.message, "配置文件错误")
        self.assertEqual(error.error_code, "CONFIG_ERROR")
        self.assertEqual(error.error_level, ErrorLevel.CRITICAL)
    
    def test_log_error(self):
        """测试错误日志记录"""
        error = TradingBotError("测试日志", "LOG_TEST")
        self.error_handler.log_error(error)
        
        # 验证错误计数更新
        stats = self.error_handler.get_error_stats()
        self.assertIn("LOG_TEST", stats)
        self.assertEqual(stats["LOG_TEST"], 1)
    
    def test_handle_error(self):
        """测试错误处理"""
        error = TradingBotError("测试处理", "HANDLE_TEST")
        result = self.error_handler.handle_error(error)
        
        # 默认情况下应该返回True
        self.assertTrue(result)
    
    def test_register_recovery_strategy(self):
        """测试注册恢复策略"""
        def recovery_strategy(error, context):
            return True
        
        self.error_handler.register_recovery_strategy("RECOVER_TEST", recovery_strategy)
        
        # 验证策略已注册
        error = TradingBotError("测试恢复", "RECOVER_TEST")
        result = self.error_handler.handle_error(error)
        
        self.assertTrue(result)
    
    def test_critical_error_handling(self):
        """测试关键错误处理"""
        error = TradingBotError("关键错误", "CRITICAL_TEST", ErrorLevel.CRITICAL)
        result = self.error_handler.handle_error(error)
        
        # 关键错误默认返回False
        self.assertFalse(result)


class TestDecorators(unittest.TestCase):
    """测试装饰器功能"""
    
    def test_error_handler_decorator(self):
        """测试错误处理装饰器"""
        
        @error_handler(return_value="fallback")
        def failing_function():
            raise ValueError("测试异常")
        
        result = failing_function()
        self.assertEqual(result, "fallback")
    
    def test_error_handler_re_raise(self):
        """测试错误处理装饰器重新抛出异常"""
        
        @error_handler(re_raise=True)
        def failing_function():
            raise ValueError("测试异常")
        
        with self.assertRaises(ValueError):
            failing_function()
    
    def test_retry_decorator(self):
        """测试重试装饰器"""
        call_count = 0
        
        @retry(max_attempts=3, delay=0.01)
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("临时失败")
            return "成功"
        
        result = failing_function()
        
        self.assertEqual(result, "成功")
        self.assertEqual(call_count, 3)
    
    def test_retry_max_attempts(self):
        """测试重试达到最大次数"""
        
        @retry(max_attempts=2, delay=0.01)
        def always_failing():
            raise ValueError("总是失败")
        
        with self.assertRaises(ValueError):
            always_failing()


class TestGlobalErrorHandler(unittest.TestCase):
    """测试全局错误处理器"""
    
    def test_global_error_handler(self):
        """测试全局错误处理器"""
        error = TradingBotError("全局测试", "GLOBAL_TEST")
        result = global_error_handler.handle_error(error)
        
        self.assertTrue(result)
        
        # 验证错误计数
        stats = global_error_handler.get_error_stats()
        self.assertIn("GLOBAL_TEST", stats)


if __name__ == '__main__':
    unittest.main()
