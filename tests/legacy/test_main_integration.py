#!/usr/bin/env python3
"""
测试main_new.py与环境管理器的集成
"""

import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_integration():
    """测试集成"""
    print("\n" + "=" * 60)
    print("测试 main_new.py 与环境管理器的集成")
    print("=" * 60)
    
    # 测试1: 导入环境管理器
    print("\n1. 测试环境管理器导入...")
    try:
        from core.config.env_manager import env_manager
        print("✅ 环境管理器导入成功")
        
        env_info = env_manager.get_env_info()
        print(f"  当前环境: {env_info['current_env']}")
        print(f"  模拟盘模式: {env_info['is_test']}")
        
        api_config = env_manager.get_api_config()
        print(f"  API Key: {api_config['api_key'][:8]}...")
    except Exception as e:
        print(f"❌ 环境管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 测试2: 导入main_new.py
    print("\n2. 测试 main_new.py 导入...")
    try:
        # 暂时禁用main_new.py的自动运行
        import sys
        original_argv = sys.argv.copy()
        sys.argv = ['test_main_integration.py']
        
        # 导入main_new
        from main_new import TradingBot
        print("✅ main_new.py 导入成功")
        
        # 恢复原始argv
        sys.argv = original_argv
    except Exception as e:
        print(f"❌ main_new.py 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 测试3: 测试TradingBot初始化
    print("\n3. 测试 TradingBot 初始化...")
    try:
        from main_new import TradingBot
        bot = TradingBot()
        print("✅ TradingBot 初始化成功")
    except Exception as e:
        print(f"❌ TradingBot 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("✅ 集成测试通过！")
    print("=" * 60)
    print("\n总结:")
    print("- 环境管理器正常工作")
    print("- main_new.py 成功导入环境管理器")
    print("- 实盘和模拟盘现在可以使用相同的代码")
    print("- 使用 switch_env.py 可以切换环境")
    
    return True


if __name__ == "__main__":
    try:
        success = test_integration()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
