#!/usr/bin/env python3
"""
简单测试脚本
测试环境管理器和基本API配置
"""

print("开始测试...")

# 测试环境管理器
print("\n1. 测试环境管理器")
try:
    from core.config.env_manager import env_manager
    print("✅ 环境管理器导入成功")
    
    # 测试环境信息
    env_info = env_manager.get_env_info()
    print(f"当前环境: {env_info['current_env']}")
    print(f"实盘环境: {'是' if env_info['is_live'] else '否'}")
    print(f"模拟盘环境: {'是' if env_info['is_test'] else '否'}")
    
    # 测试API配置
    api_config = env_manager.get_api_config()
    print(f"API Key: {api_config['api_key'][:8]}...")
    print(f"模拟盘模式: {api_config['is_test']}")
    
    print("✅ 环境管理器测试通过")
    
except Exception as e:
    print(f"❌ 环境管理器测试失败: {e}")
    import traceback
    traceback.print_exc()

print("\n测试完成！")
