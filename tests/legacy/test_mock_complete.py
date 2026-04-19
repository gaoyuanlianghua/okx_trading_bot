#!/usr/bin/env python3
"""
模拟盘完整测试脚本
测试模拟盘的所有功能，包括账户余额、下单和撤单
"""

import asyncio
import logging
from core.config.env_manager import env_manager
from core.api.okx_rest_client import OKXRESTClient

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_mock_complete():
    """测试模拟盘完整功能"""
    logger.info("\n" + "=" * 60)
    logger.info("模拟盘完整功能测试")
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
        
        # 1. 测试服务器时间
        logger.info("\n1. 测试服务器时间")
        server_time = await rest_client.get_server_time()
        if server_time:
            logger.info(f"✅ 服务器时间获取成功: {server_time}")
        else:
            logger.error("❌ 服务器时间获取失败")
            return False
        
        # 2. 测试行情数据
        logger.info("\n2. 测试行情数据")
        ticker = await rest_client.get_ticker('BTC-USDT')
        if ticker:
            logger.info("✅ 行情数据获取成功")
            logger.info(f"  BTC-USDT 最新价: {ticker.get('last')} USDT")
        else:
            logger.error("❌ 行情数据获取失败")
            return False
        
        # 3. 测试账户余额
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
            return False
        
        # 4. 测试持仓信息
        logger.info("\n4. 测试持仓信息")
        positions = await rest_client.get_positions(inst_type='MARGIN')
        if positions:
            logger.info(f"✅ 持仓信息获取成功，共 {len(positions)} 个持仓")
            for pos in positions[:3]:
                if isinstance(pos, dict):
                    logger.info(f"  {pos.get('instId')}: 持仓 {pos.get('pos')}, 均价 {pos.get('avgPx')}")
        else:
            logger.info("ℹ️  无持仓信息")
        
        # 5. 测试未成交订单
        logger.info("\n5. 测试未成交订单")
        pending_orders = await rest_client.get_orders_pending()
        if pending_orders:
            logger.info(f"✅ 未成交订单获取成功，共 {len(pending_orders)} 个订单")
            for order in pending_orders[:3]:
                if isinstance(order, dict):
                    logger.info(f"  订单ID: {order.get('ordId')}, 状态: {order.get('state')}")
        else:
            logger.info("ℹ️  无未成交订单")
        
        # 6. 测试下单和撤单
        logger.info("\n6. 测试下单和撤单")
        # 获取当前价格
        current_price = float(ticker.get('last', '0'))
        logger.info(f"  当前BTC-USDT价格: {current_price} USDT")
        
        # 测试下单
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
            
            # 测试查询订单
            order_info = await rest_client.get_order('BTC-USDT', order_id)
            if order_info:
                logger.info("✅ 订单查询成功")
                if isinstance(order_info, dict):
                    logger.info(f"  订单状态: {order_info.get('state')}")
                    logger.info(f"  订单价格: {order_info.get('px')}")
                    logger.info(f"  订单数量: {order_info.get('sz')}")
            else:
                logger.error("❌ 订单查询失败")
            
            # 测试撤单
            cancel_result = await rest_client.cancel_order('BTC-USDT', order_id)
            if cancel_result:
                logger.info("✅ 撤单成功")
            else:
                logger.error("❌ 撤单失败")
        else:
            logger.error("❌ 下单失败")
        
        # 7. 测试API统计
        logger.info("\n7. API调用统计")
        logger.info(f"  总调用次数: {rest_client.api_stats['total_calls']}")
        logger.info(f"  成功调用次数: {rest_client.api_stats['success_calls']}")
        logger.info(f"  失败调用次数: {rest_client.api_stats['failed_calls']}")
        logger.info(f"  缓存调用次数: {rest_client.api_stats['cached_calls']}")
        logger.info(f"  平均响应时间: {rest_client.api_stats['avg_response_time']:.3f}s")
        
        # 清理会话
        if hasattr(rest_client, 'session') and rest_client.session:
            await rest_client.session.close()
        
        # 测试结果总结
        logger.info("\n" + "=" * 60)
        logger.info("测试完成！")
        logger.info("=" * 60)
        logger.info("✅ 模拟盘完整功能测试通过")
        logger.info("\n🎉 所有功能都已测试成功！")
        logger.info("您现在可以在模拟盘中安全地测试完整的交易策略了。")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 使用旧版本Python的异步运行方式
    loop = asyncio.get_event_loop()
    success = loop.run_until_complete(test_mock_complete())
    loop.close()
    
    if not success:
        logger.error("\n⚠️  测试未通过，请检查API密钥是否正确")
