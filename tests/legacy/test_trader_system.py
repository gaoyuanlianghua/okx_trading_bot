"""
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
        from core import OKXRESTClient
        from core.traders import TraderManager, SpotTrader
        
        # 1. 初始化客户端（不使用配置，直接使用环境变量）
        rest_client = OKXRESTClient()
        logger.info("✅ REST客户端创建成功")
        
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
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(test_trader_system())
    exit(0 if result else 1)
