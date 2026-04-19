#!/usr/bin/env python3
"""
测试日志大小限制功能
"""

import sys
import os
from core.utils.logger import LoggerConfig

def test_log_cleanup():
    """
    测试日志清理功能
    """
    print("开始测试日志大小限制功能...")
    
    # 创建日志配置实例
    logger_config = LoggerConfig()
    
    # 计算当前日志总大小
    current_size = logger_config.get_log_total_size()
    print(f"当前日志总大小: {current_size / (1024 * 1024 * 1024):.2f}GB")
    print(f"限制大小: {logger_config.max_total_size_gb}GB")
    
    # 执行清理
    print("执行日志清理...")
    logger_config.clean_old_logs()
    
    # 计算清理后的大小
    new_size = logger_config.get_log_total_size()
    print(f"清理后日志总大小: {new_size / (1024 * 1024 * 1024):.2f}GB")
    
    if new_size <= logger_config.max_total_size_bytes:
        print("✓ 测试通过: 日志大小已控制在限制范围内")
    else:
        print("✗ 测试失败: 日志大小仍超过限制")
    
    return new_size <= logger_config.max_total_size_bytes

if __name__ == "__main__":
    success = test_log_cleanup()
    sys.exit(0 if success else 1)
