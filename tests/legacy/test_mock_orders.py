#!/usr/bin/env python3
"""
模拟盘订单操作测试脚本
测试模拟盘中的下单、撤单等操作
"""

import asyncio
import logging
import json
from core.api.okx_rest_client import OKXRESTClient

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_mock_orders():
    """测试模拟盘订单操作"""
    logger.info("\n" + "=" * 60)
    logger.info("模拟盘订单操作测试")
    logger.info("=" * 60)
    
    try:
        # 直接硬编码API配置（仅测试用）
        api_key = "19500a62-d018-44d8-9a24-01b87a2d6488"
        api_secret = "5939DA43F600616659F41F905321D502"
        passphrase = "Gy528329818.123"
        is_test = True
        
        logger.info(f"API Key: {api_key[:8]}...")
        logger.info(f"模拟盘模式: {is_test}")
        
        # 创建REST客户端
        rest_client = OKXRESTClient(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            is_test=is_test
        )
        
        # 1. 获取账户余额
        logger.info("\n1. 获取账户余额")
        balance = await rest_client.get_account_balance()
        if balance and len(balance) > 0:
            logger.info("✅ 账户余额获取成功")
            for item in balance:
                logger.info(f"  总权益: {item.get('totalEq', 'N/A')}")
                for detail in item.get('details', []):
                    if float(detail.get('cashBal', '0')) > 0:
                        logger.info(f"  {detail.get('ccy')}: {detail.get('cashBal')} (可用: {detail.get('availBal')})")
        else:
            logger.error("❌ 账户余额获取失败")
        
        # 2. 获取当前价格
        logger.info("\n2. 获取当前价格")
        ticker = await rest_client.get_ticker('BTC-USDT')
        if ticker:
            current_price = float(ticker.get('last', '0'))
            logger.info(f"✅ 价格获取成功: {current_price} USDT")
        else:
            logger.error("❌ 价格获取失败")
            return False
        
        # 3. 测试下单
        logger.info("\n3. 测试下单")
        order_id = await rest_client.place_order(
            inst_id='BTC-USDT',
            side='buy',
            ord_type='limit',
            sz='0.00001',  # 最小交易单位
            px=str(current_price * 0.99),  # 低于当前价格1%
            td_mode='cross',
            lever='2'
        )
        
        if order_id:
            logger.info(f"✅ 下单成功，订单ID: {order_id}")
            
            # 4. 测试查询订单
            logger.info("\n4. 测试查询订单")
            order_info = await rest_client.get_order('BTC-USDT', order_id)
            if order_info:
                logger.info("✅ 订单查询成功")
                logger.info(f"  订单状态: {order_info.get('state')}")
                logger.info(f"  订单价格: {order_info.get('px')}")
                logger.info(f"  订单数量: {order_info.get('sz')}")
            else:
                logger.error("❌ 订单查询失败")
            
            # 5. 测试撤单
            logger.info("\n5. 测试撤单")
            cancel_result = await rest_client.cancel_order('BTC-USDT', order_id)
            if cancel_result:
                logger.info("✅ 撤单成功")
            else:
                logger.error("❌ 撤单失败")
        else:
            logger.error("❌ 下单失败")
        
        # 6. 获取未成交订单
        logger.info("\n6. 获取未成交订单")
        pending_orders = await rest_client.get_orders_pending()
        if pending_orders and len(pending_orders) > 0:
            logger.info(f"✅ 未成交订单获取成功，共 {len(pending_orders)} 个订单")
            for order in pending_orders[:3]:  # 只显示前3个
                logger.info(f"  订单ID: {order.get('ordId')}, 状态: {order.get('state')}, 价格: {order.get('px')}")
        else:
            logger.info("ℹ️  无未成交订单")
        
        # 清理会话
        if hasattr(rest_client, 'session') and rest_client.session:
            await rest_client.session.close()
            logger.info("✅ 会话已关闭")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    success = loop.run_until_complete(test_mock_orders())
    loop.close()
    
    if success:
        logger.info("\n✅ 模拟盘订单操作测试成功！")
    else:
        logger.error("\n❌ 模拟盘订单操作测试失败！")
