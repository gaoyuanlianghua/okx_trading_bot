#!/usr/bin/env python3
"""
环境切换脚本
在实盘和模拟盘之间切换
"""

import sys
import argparse
from core.config.env_manager import env_manager


def print_env_info():
    """打印环境信息"""
    info = env_manager.get_env_info()
    print("\n" + "=" * 50)
    print("环境信息")
    print("=" * 50)
    print(f"当前环境: {info['current_env'].upper()}")
    print(f"实盘环境: {'激活' if info['is_live'] else '未激活'}")
    print(f"模拟盘环境: {'激活' if info['is_test'] else '未激活'}")
    print(f"实盘配置文件: {'存在' if info['live_config_exists'] else '不存在'}")
    print(f"模拟盘配置文件: {'存在' if info['test_config_exists'] else '不存在'}")
    print(f"配置目录: {info['config_dir']}")
    print("=" * 50 + "\n")


def print_api_config():
    """打印当前环境的API配置（隐藏敏感信息）"""
    api_config = env_manager.get_api_config()
    print("\n" + "=" * 50)
    print("API配置")
    print("=" * 50)
    print(f"API Key: {api_config['api_key'][:8] if api_config['api_key'] else '未配置'}{'...' if api_config['api_key'] else ''}")
    print(f"API Secret: {api_config['api_secret'][:8] if api_config['api_secret'] else '未配置'}{'...' if api_config['api_secret'] else ''}")
    print(f"Passphrase: {api_config['passphrase'][:8] if api_config['passphrase'] else '未配置'}{'...' if api_config['passphrase'] else ''}")
    print(f"模拟盘模式: {'是' if api_config['is_test'] else '否'}")
    print(f"超时时间: {api_config['timeout']}秒")
    print("=" * 50 + "\n")


def main():
    parser = argparse.ArgumentParser(description="环境切换工具")
    parser.add_argument(
        "action",
        choices=["live", "test", "info"],
        help="操作类型: live(切换到实盘), test(切换到模拟盘), info(显示当前环境信息)"
    )
    
    args = parser.parse_args()
    
    if args.action == "info":
        print_env_info()
        print_api_config()
        return 0
    
    if args.action == "live":
        print("正在切换到实盘环境...")
        if env_manager.switch_to_live():
            print("✅ 成功切换到实盘环境！")
            print_env_info()
            return 0
        else:
            print("❌ 切换到实盘环境失败！")
            return 1
    
    if args.action == "test":
        print("正在切换到模拟盘环境...")
        if env_manager.switch_to_test():
            print("✅ 成功切换到模拟盘环境！")
            print_env_info()
            print("\n⚠️  注意：请确保 config/config_test.yaml 中配置了正确的模拟盘API密钥！")
            print("   模拟盘API密钥需要在OKX官网的'交易' -> '模拟交易' -> '个人中心' -> '创建模拟盘APIKey'中创建")
            return 0
        else:
            print("❌ 切换到模拟盘环境失败！")
            return 1


if __name__ == "__main__":
    sys.exit(main())
