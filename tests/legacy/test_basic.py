#!/usr/bin/env python3
"""
基本测试脚本
"""

print("开始测试...")

# 测试基本功能
print("\n1. 测试基本打印")
print("Hello, World!")

# 测试环境变量
print("\n2. 测试环境变量")
import os
print(f"当前目录: {os.getcwd()}")

# 测试文件存在性
print("\n3. 测试文件存在性")
import os.path
print(f"策略文件存在: {os.path.exists('strategies/nuclear_dynamics_strategy.py')}")
print(f"配置文件存在: {os.path.exists('config/config_test.yaml')}")

print("\n测试完成！")
