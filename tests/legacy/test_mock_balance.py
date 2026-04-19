#!/usr/bin/env python3
"""
模拟盘账户余额测试脚本
测试账户余额和公共API功能
"""

import asyncio
import logging
from core.config.env_manager import env_manager
from core.api.okx_rest_client import OKXRESTClient

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_mock_balance():
    """测试模拟盘账户余额"""
    logger.info("\n" + "=" * 60)
    logger.info("模拟盘账户余额测试")
    logger.info("=" * 60)
    
    try:
        # 获取API配置
        api_config = env_manager.get_api_config()
        logger.info(f"当前环境: {env_manager.get_current_env().upper()}")
        logger.info(f"API Key: {api_config['api_key'][:8]}...")
        logger.info(f"模拟盘模式: {api_config['is_test']}")
        
        # 验证API配置
        if not api_config['api_key'] or not api_config['api_secret'] or not api_config['passphrase']:
            logger.error("❌ API配置不完整")
            return False
        
        # 创建REST客户端
        rest_client = OKXRESTClient(
            api_key=api_config['api_key'],
            api_secret=api_config['api_secret'],
            passphrase=api_config['passphrase'],
            is_test=api_config['is_test']
        )
        
        # 1. 测试服务器时间（公共API）
        logger.info("\n1. 测试服务器时间")
        server_time = await rest_client.get_server_time()
        if server_time:
            logger.info(f"✅ 服务器时间获取成功: {server_time}")
        else:
            logger.error("❌ 服务器时间获取失败")
        
        # 2. 测试行情数据（公共API）
        logger.info("\n2. 测试行情数据")
        ticker = await rest_client.get_ticker('BTC-USDT')
        if ticker:
            logger.info("✅ 行情数据获取成功")
            logger.info(f"  BTC-USDT 最新价: {ticker.get('last')} USDT")
        else:
            logger.error("❌ 行情数据获取失败")
        
        # 3. 测试账户余额（私有API）
        logger.info("\n3. 测试账户余额")
        balance = await rest_client.get_account_balance()
        if balance:
            logger.info("✅ 账户余额获取成功")
            if isinstance(balance, list) and len(balance) > 0:
                for item in balance:
                    if isinstance(item, dict):
                        logger.info(f"  总权益: {item.get('totalEq', 'N/A')}")
                        for detail in item.get('details', []):
                            if isinstance(detail, dict) and float(detail.get('cashBal', '0')) > 0:
                                logger.info(f"  {detail.get('ccy')}: {detail.get('cashBal')} (可用: {detail.get('availBal')})")
        else:
            logger.error("❌ 账户余额获取失败")
        
        # 4. 测试持仓信息（私有API）
        logger.info("\n4. 测试持仓信息")
        positions = await rest_client.get_positions(inst_type='MARGIN')
        if positions:
            logger.info(f"✅ 持仓信息获取成功，共 {len(positions)} 个持仓")
            for pos in positions[:3]:
                if isinstance(pos, dict):
                    logger.info(f"  {pos.get('instId')}: 持仓 {pos.get('pos')}, 均价 {pos.get('avgPx')}")
        else:
            logger.info("ℹ️  无持仓信息")
        
        # 5. 测试未成交订单（私有API）
        logger.info("\n5. 测试未成交订单")
        pending_orders = await rest_client.get_orders_pending()
        if pending_orders:
            logger.info(f"✅ 未成交订单获取成功，共 {len(pending_orders)} 个订单")
            for order in pending_orders[:3]:
                if isinstance(order, dict):
                    logger.info(f"  订单ID: {order.get('ordId')}, 状态: {order.get('state')}")
        else:
            logger.info("ℹ️  无未成交订单")
        
        # 清理会话
        if hasattr(rest_client, 'session') and rest_client.session:
            await rest_client.session.close()
        
        # 测试结果总结
        logger.info("\n" + "=" * 60)
        logger.info("测试完成！")
        logger.info("=" * 60)
        logger.info("✅ 模拟盘账户余额测试通过")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    success = loop.run_until_complete(test_mock_balance())
    loop.close()
