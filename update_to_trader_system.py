"""
更新脚本 - 将交易机器人从原有架构迁移到新的交易器架构

使用方法:
1. 备份原有代码
2. 运行此脚本进行迁移
3. 测试新的交易器系统
"""

import os
import shutil
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def backup_original_files():
    """备份原有文件"""
    files_to_backup = [
        'core/agents/order_agent.py',
        'main_new.py'
    ]
    
    for file_path in files_to_backup:
        if os.path.exists(file_path):
            backup_path = f"{file_path}.backup"
            shutil.copy2(file_path, backup_path)
            logger.info(f"已备份: {file_path} -> {backup_path}")


def update_main_new_py():
    """更新 main_new.py 使用适配器"""
    main_file = 'main_new.py'
    
    if not os.path.exists(main_file):
        logger.error(f"找不到文件: {main_file}")
        return False
    
    # 读取原文件
    with open(main_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换导入语句
    if 'from core.agents.order_agent import OrderAgent' in content:
        content = content.replace(
            'from core.agents.order_agent import OrderAgent',
            'from core.agents.order_agent_adapter import OrderAgentAdapter as OrderAgent'
        )
        logger.info("已更新 OrderAgent 导入语句")
    
    # 保存修改后的文件
    with open(main_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    logger.info(f"已更新: {main_file}")
    return True


def verify_trader_system():
    """验证交易器系统是否正确安装"""
    required_files = [
        'core/traders/__init__.py',
        'core/traders/base_trader.py',
        'core/traders/spot_trader.py',
        'core/traders/trader_manager.py',
        'core/agents/order_agent_adapter.py'
    ]
    
    all_exist = True
    for file_path in required_files:
        if os.path.exists(file_path):
            logger.info(f"✅ {file_path}")
        else:
            logger.error(f"❌ {file_path} 不存在")
            all_exist = False
    
    return all_exist


def create_test_script():
    """创建测试脚本"""
    test_script = '''"""
测试脚本 - 验证交易器系统是否正常工作
"""

import asyncio
import logging
from decimal import Decimal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_trader_system():
    """测试交易器系统"""
    try:
        from core.api.okx_rest_client import OKXRESTClient
        from core.config import OKXConfig
        from core.traders import TraderManager, SpotTrader
        
        # 1. 初始化配置和客户端
        config = OKXConfig()
        rest_client = OKXRESTClient(config)
        
        # 2. 创建交易器管理器
        trader_manager = TraderManager(rest_client)
        logger.info("✅ 交易器管理器创建成功")
        
        # 3. 创建现货交易器
        spot_trader = trader_manager.create_trader('spot', 'test_spot')
        logger.info("✅ 现货交易器创建成功")
        
        # 4. 获取账户信息
        account_info = await trader_manager.get_account_info('test_spot')
        if account_info:
            logger.info(f"✅ 获取账户信息成功: 总权益={account_info.total_equity}")
        else:
            logger.warning("⚠️ 获取账户信息失败")
        
        # 5. 获取风险信息
        risk_info = await trader_manager.get_risk_info('test_spot')
        if risk_info:
            logger.info(f"✅ 获取风险信息成功: 风险等级={risk_info.risk_level}")
        else:
            logger.warning("⚠️ 获取风险信息失败")
        
        # 6. 获取持仓信息
        position = await trader_manager.get_position('BTC-USDT', None, 'test_spot')
        if position:
            logger.info(f"✅ 获取持仓成功: {position.size} BTC")
        else:
            logger.info("ℹ️ 无BTC持仓")
        
        logger.info("\n✅ 所有测试通过！交易器系统工作正常")
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_trader_system())
    exit(0 if result else 1)
'''
    
    with open('test_trader_system.py', 'w', encoding='utf-8') as f:
        f.write(test_script)
    
    logger.info("已创建测试脚本: test_trader_system.py")


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("开始迁移到新的交易器架构")
    logger.info("=" * 60)
    
    # 1. 备份原有文件
    logger.info("\n1. 备份原有文件...")
    backup_original_files()
    
    # 2. 验证交易器系统
    logger.info("\n2. 验证交易器系统...")
    if not verify_trader_system():
        logger.error("交易器系统文件不完整，请先创建交易器文件")
        return False
    
    # 3. 更新 main_new.py
    logger.info("\n3. 更新 main_new.py...")
    if not update_main_new_py():
        logger.error("更新 main_new.py 失败")
        return False
    
    # 4. 创建测试脚本
    logger.info("\n4. 创建测试脚本...")
    create_test_script()
    
    logger.info("\n" + "=" * 60)
    logger.info("迁移完成！")
    logger.info("=" * 60)
    logger.info("\n下一步:")
    logger.info("1. 运行测试: python test_trader_system.py")
    logger.info("2. 如果测试通过，启动机器人: python main_new.py")
    logger.info("3. 监控日志，确保交易正常执行")
    logger.info("\n回滚方法:")
    logger.info("- 恢复 main_new.py: cp main_new.py.backup main_new.py")
    logger.info("- 恢复 order_agent.py: cp core/agents/order_agent.py.backup core/agents/order_agent.py")
    
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
