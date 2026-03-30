#!/usr/bin/env python3
"""
测试导入脚本
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("测试导入 market_data_agent...")
    from core.agents import MarketDataAgent
    print("✓ market_data_agent 导入成功")
except Exception as e:
    print(f"✗ market_data_agent 导入失败: {e}")
    import traceback
    traceback.print_exc()

try:
    print("\n测试导入 order_agent...")
    from core.agents import OrderAgent
    print("✓ order_agent 导入成功")
except Exception as e:
    print(f"✗ order_agent 导入失败: {e}")
    import traceback
    traceback.print_exc()

try:
    print("\n测试导入 exchange_manager...")
    from core.api import exchange_manager
    print("✓ exchange_manager 导入成功")
except Exception as e:
    print(f"✗ exchange_manager 导入失败: {e}")
    import traceback
    traceback.print_exc()

try:
    print("\n测试导入 event_bus...")
    from core.events import event_bus
    print("✓ event_bus 导入成功")
except Exception as e:
    print(f"✗ event_bus 导入失败: {e}")
    import traceback
    traceback.print_exc()

print("\n导入测试完成")