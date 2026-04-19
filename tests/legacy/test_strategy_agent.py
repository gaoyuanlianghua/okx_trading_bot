#!/usr/bin/env python3
"""
测试策略智能体导入
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("测试导入 StrategyAgent...")
    from core.agents import StrategyAgent
    print("✓ StrategyAgent 导入成功")
except Exception as e:
    print(f"✗ StrategyAgent 导入失败: {e}")
    import traceback
    traceback.print_exc()

print("\n导入测试完成")