"""
测试运行脚本
"""

import asyncio
import pytest
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_unit_tests():
    """运行单元测试"""
    print("=== 运行单元测试 ===")
    result = pytest.main(["-v", "tests/"])
    return result


def run_integration_tests():
    """运行集成测试"""
    print("\n=== 运行集成测试 ===")
    result = pytest.main(["-v", "test_new_architecture.py"])
    return result


async def run_all_tests():
    """运行所有测试"""
    print("开始运行所有测试...\n")
    
    # 运行单元测试
    unit_test_result = run_unit_tests()
    
    # 运行集成测试
    integration_test_result = run_integration_tests()
    
    print("\n=== 测试结果汇总 ===")
    print(f"单元测试结果: {'通过' if unit_test_result == 0 else '失败'}")
    print(f"集成测试结果: {'通过' if integration_test_result == 0 else '失败'}")
    
    if unit_test_result == 0 and integration_test_result == 0:
        print("\n✅ 所有测试通过！")
    else:
        print("\n❌ 部分测试失败！")
    
    return unit_test_result + integration_test_result


if __name__ == "__main__":
    asyncio.run(run_all_tests())
