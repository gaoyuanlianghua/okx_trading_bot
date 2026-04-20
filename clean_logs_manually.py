#!/usr/bin/env python3
"""
手动触发日志清理
"""
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.utils.logger import LoggerConfig

def main():
    print("=" * 80)
    print("手动日志清理")
    print("=" * 80)
    
    # 计算清理前大小
    def get_size(path):
        size = 0
        if os.path.isdir(path):
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.isfile(filepath):
                        size += os.path.getsize(filepath)
        elif os.path.isfile(path):
            size = os.path.getsize(path)
        return size
    
    logs_before = get_size("logs")
    print(f"清理前日志大小: {logs_before / (1024 * 1024 * 1024):.4f} GB")
    print()
    
    # 执行清理
    print("执行日志清理...")
    logger_config = LoggerConfig()
    try:
        logger_config.clean_old_logs()
        print("清理完成！")
    except Exception as e:
        print(f"清理出错: {e}")
        import traceback
        print(traceback.format_exc())
        return 1
    
    # 计算清理后大小
    logs_after = get_size("logs")
    print()
    print("=" * 80)
    print(f"清理后日志大小: {logs_after / (1024 * 1024 * 1024):.4f} GB")
    freed = logs_before - logs_after
    if freed > 0:
        print(f"释放空间: {freed / (1024 * 1024):.4f} MB")
    else:
        print("无需清理")
    print("=" * 80)
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
