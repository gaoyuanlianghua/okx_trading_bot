#!/usr/bin/env python3
"""
测试策略模块加载和初始化
"""

import sys
import os
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, level="INFO")

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_dynamics_strategy():
    """测试动力学策略加载"""
    logger.info("🚀 测试动力学策略加载...")
    try:
        from strategies.dynamics_strategy import DynamicsStrategy
        logger.info("✅ 成功导入DynamicsStrategy")
        
        # 测试初始化（不传入api_client，避免网络连接）
        strategy = DynamicsStrategy()
        logger.info("✅ 成功初始化DynamicsStrategy")
        
        # 测试基本方法
        status = strategy.get_status()
        logger.info(f"✅ 策略状态: {status}")
        
        # 测试参数获取
        params = strategy.get_params()
        logger.info("✅ 成功获取策略参数")
        
        assert True
    except Exception as e:
        logger.error(f"❌ 动力学策略测试失败: {e}")
        import traceback
        traceback.print_exc()
        assert False

def test_passivbot_integrator():
    """测试Passivbot集成策略加载"""
    logger.info("🚀 测试Passivbot集成策略加载...")
    try:
        from strategies.passivbot_integrator import PassivbotIntegrator
        logger.info("✅ 成功导入PassivbotIntegrator")
        
        # 测试初始化（不传入api_client，避免网络连接）
        strategy = PassivbotIntegrator()
        logger.info("✅ 成功初始化PassivbotIntegrator")
        
        # 测试基本方法
        status = strategy.get_status()
        logger.info(f"✅ 策略状态: {status}")
        
        # 测试参数获取
        params = strategy.get_params()
        logger.info("✅ 成功获取策略参数")
        
        assert True
    except Exception as e:
        logger.error(f"❌ Passivbot集成策略测试失败: {e}")
        import traceback
        traceback.print_exc()
        assert False

def test_base_strategy():
    """测试策略基类"""
    logger.info("🚀 测试策略基类...")
    try:
        from strategies.base_strategy import BaseStrategy
        logger.info("✅ 成功导入BaseStrategy")
        
        # 测试初始化
        strategy = BaseStrategy()
        logger.info("✅ 成功初始化BaseStrategy")
        
        # 测试基本方法
        status = strategy.get_status()
        logger.info(f"✅ 策略状态: {status}")
        
        # 测试参数设置
        strategy.set_params({"test_param": "value"})
        params = strategy.get_params()
        logger.info(f"✅ 策略参数: {params}")
        
        assert True
    except Exception as e:
        logger.error(f"❌ 策略基类测试失败: {e}")
        import traceback
        traceback.print_exc()
        assert False

def main():
    """主测试函数"""
    logger.info("🎯 开始策略模块加载测试")
    
    # 运行测试，使用try-except捕获断言失败
    test_functions = {
        "BaseStrategy": test_base_strategy,
        "DynamicsStrategy": test_dynamics_strategy,
        "PassivbotIntegrator": test_passivbot_integrator
    }
    
    results = {}
    for strategy_name, test_func in test_functions.items():
        try:
            test_func()
            results[strategy_name] = True
        except AssertionError:
            results[strategy_name] = False
    
    logger.info("\n📊 测试结果汇总:")
    all_passed = True
    for strategy_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        logger.info(f"  {strategy_name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        logger.info("\n🎉 所有策略模块测试通过！")
        return 0
    else:
        logger.error("\n❌ 部分策略模块测试失败！")
        return 1

if __name__ == "__main__":
    sys.exit(main())
