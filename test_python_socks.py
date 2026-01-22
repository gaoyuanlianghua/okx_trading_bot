#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试python_socks模块导入情况
"""

import sys
import traceback

print(f"Python版本: {sys.version}")
print(f"Python路径: {sys.path}")

# 测试基本导入
try:
    import python_socks
    print(f"✅ 成功导入python_socks模块，版本: {python_socks.__version__}")
except Exception as e:
    print(f"❌ 无法导入python_socks模块: {e}")
    traceback.print_exc()

# 测试asyncio导入
try:
    from python_socks import ProxyConnector
    print(f"✅ 成功导入ProxyConnector")
except Exception as e:
    print(f"❌ 无法导入ProxyConnector: {e}")
    traceback.print_exc()

# 测试asyncio子模块
try:
    from python_socks.asyncio import ProxyConnector
    print(f"✅ 成功导入python_socks.asyncio.ProxyConnector")
except Exception as e:
    print(f"❌ 无法导入python_socks.asyncio.ProxyConnector: {e}")
    traceback.print_exc()

# 查看模块内容
try:
    import python_socks
    print(f"\npython_socks模块内容: {dir(python_socks)}")
    
    # 查看是否有asyncio属性
    if hasattr(python_socks, 'asyncio'):
        print(f"python_socks.asyncio内容: {dir(python_socks.asyncio)}")
    else:
        print("python_socks模块中没有asyncio属性")
        
    # 查看是否有其他相关属性
    for attr in dir(python_socks):
        if 'async' in attr.lower():
            print(f"找到async相关属性: {attr}")
            
except Exception as e:
    print(f"❌ 查看模块内容失败: {e}")
    traceback.print_exc()
