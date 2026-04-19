#!/usr/bin/env python3
"""
模拟盘全面功能测试脚本
测试所有核心功能
"""

import asyncio
import logging
import time
from core.config.env_manager import env_manager

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_public_api(rest_client):
    """测试公共API"""
    logger.info("\n" + "=" * 60)
    logger.info("测试1: 公共API")
    logger.info("=" * 60)
    
    results = {}
    
    # 1.1 服务器时间
    logger.info("\n1.1 测试服务器时间")
    try:
        server_time = await rest_client.get_server_time()
        if server_time:
            logger.info(f"✅ 服务器时间: {server_time}")
            results['server_time'] = True
        else:
            logger.error("❌ 服务器时间获取失败")
            results['server_time'] = False
    except Exception as e:
        logger.error(f"❌ 服务器时间测试失败: {e}")
        results['server_time'] = False
    
    # 1.2 行情数据
    logger.info("\n1.2 测试行情数据")
    try:
        ticker = await rest_client.get_ticker('BTC-USDT')
        if ticker:
            logger.info("✅ 行情数据获取成功")
            logger.info(f"  BTC-USDT 最新价: {ticker.get('last')}")
            logger.info(f"  24h 成交量: {ticker.get('vol24h')}")
            logger.info(f"  24h 涨跌幅: {ticker.get('px24hPct')}%")
            results['ticker'] = True
        else:
            logger.error("❌ 行情数据获取失败")
            results['ticker'] = False
    except Exception as e:
        logger.error(f"❌ 行情数据测试失败: {e}")
        results['ticker'] = False
    
    # 1.3 K线数据
    logger.info("\n1.3 测试K线数据")
    try:
        candles = await rest_client.get_candles('BTC-USDT', bar='1m', limit=5)
        if candles:
            logger.info("✅ K线数据获取成功")
            for candle in candles[:3]:
                logger.info(f"  {candle[0]}: 开 {candle[1]}, 高 {candle[2]}, 低 {candle[3]}, 收 {candle[4]}")
            results['candles'] = True
        else:
            logger.error("❌ K线数据获取失败")
            results['candles'] = False
    except Exception as e:
        logger.error(f"❌ K线数据测试失败: {e}")
        results['candles'] = False
    
    # 1.4 交易产品信息
    logger.info("\n1.4 测试交易产品信息")
    try:
        instruments = await rest_client.get_instruments(inst_type='SPOT')
        if instruments:
            logger.info(f"✅ 交易产品信息获取成功，共 {len(instruments)} 个产品")
            # 查找BTC-USDT
            btc_instrument = None
            for inst in instruments:
                if inst.get('instId') == 'BTC-USDT':
                    btc_instrument = inst
                    break
            if btc_instrument:
                logger.info(f"  BTC-USDT 最小交易单位: {btc_instrument.get('minSz')}")
                logger.info(f"  BTC-USDT 价格精度: {btc_instrument.get('tickSz')}")
            results['instruments'] = True
        else:
            logger.error("❌ 交易产品信息获取失败")
            results['instruments'] = False
    except Exception as e:
        logger.error(f"❌ 交易产品信息测试失败: {e}")
        results['instruments'] = False
    
    return results


async def test_api_caching(rest_client):
    """测试API缓存"""
    logger.info("\n" + "=" * 60)
    logger.info("测试2: API缓存")
    logger.info("=" * 60)
    
    results = {}
    
    try:
        # 第一次请求
        logger.info("\n2.1 第一次请求（不使用缓存）")
        start_time = time.time()
        ticker1 = await rest_client.get_ticker('BTC-USDT')
        elapsed1 = time.time() - start_time
        logger.info(f"  耗时: {elapsed1:.3f}s")
        
        # 第二次请求（应该使用缓存）
        logger.info("\n2.2 第二次请求（应该使用缓存）")
        start_time = time.time()
        ticker2 = await rest_client.get_ticker('BTC-USDT')
        elapsed2 = time.time() - start_time
        logger.info(f"  耗时: {elapsed2:.3f}s")
        
        if elapsed2 < elapsed1:
            logger.info("✅ API缓存测试成功")
            results['caching'] = True
        else:
            logger.warning("⚠️  API缓存可能未生效")
            results['caching'] = False
        
        # API统计
        logger.info("\n2.3 API调用统计")
        logger.info(f"  总调用次数: {rest_client.api_stats['total_calls']}")
        logger.info(f"  成功调用次数: {rest_client.api_stats['success_calls']}")
        logger.info(f"  失败调用次数: {rest_client.api_stats['failed_calls']}")
        logger.info(f"  缓存调用次数: {rest_client.api_stats['cached_calls']}")
        logger.info(f"  平均响应时间: {rest_client.api_stats['avg_response_time']:.3f}s")
        
    except Exception as e:
        logger.error(f"❌ API缓存测试失败: {e}")
        results['caching'] = False
    
    return results


async def test_private_api(rest_client):
    """测试私有API"""
    logger.info("\n" + "=" * 60)
    logger.info("测试3: 私有API")
    logger.info("=" * 60)
    
    results = {}
    
    # 3.1 账户余额
    logger.info("\n3.1 测试账户余额")
    try:
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
            results['balance'] = True
        else:
            logger.error("❌ 账户余额获取失败")
            results['balance'] = False
    except Exception as e:
        logger.error(f"❌ 账户余额测试失败: {e}")
        results['balance'] = False
    
    # 3.2 持仓信息
    logger.info("\n3.2 测试持仓信息")
    try:
        positions = await rest_client.get_positions(inst_type='MARGIN')
        if positions:
            logger.info(f"✅ 持仓信息获取成功，共 {len(positions)} 个持仓")
            for pos in positions[:3]:
                if isinstance(pos, dict):
                    logger.info(f"  {pos.get('instId')}: 持仓 {pos.get('pos')}, 均价 {pos.get('avgPx')}")
            results['positions'] = True
        else:
            logger.info("ℹ️  无持仓信息")
            results['positions'] = True
    except Exception as e:
        logger.error(f"❌ 持仓信息测试失败: {e}")
        results['positions'] = False
    
    # 3.3 未成交订单
    logger.info("\n3.3 测试未成交订单")
    try:
        pending_orders = await rest_client.get_orders_pending()
        if pending_orders:
            logger.info(f"✅ 未成交订单获取成功，共 {len(pending_orders)} 个订单")
            for order in pending_orders[:3]:
                if isinstance(order, dict):
                    logger.info(f"  订单ID: {order.get('ordId')}, 状态: {order.get('state')}")
            results['pending_orders'] = True
        else:
            logger.info("ℹ️  无未成交订单")
            results['pending_orders'] = True
    except Exception as e:
        logger.error(f"❌ 未成交订单测试失败: {e}")
        results['pending_orders'] = False
    
    return results


async def test_order_operations(rest_client, ticker):
    """测试订单操作"""
    logger.info("\n" + "=" * 60)
    logger.info("测试4: 订单操作")
    logger.info("=" * 60)
    
    results = {}
    
    try:
        # 获取当前价格
        current_price = float(ticker.get('last', '0'))
        logger.info(f"\n4.1 当前BTC-USDT价格: {current_price} USDT")
        
        # 测试下单
        logger.info("\n4.2 测试下单")
        order_id = await rest_client.place_order(
            inst_id='BTC-USDT',
            side='buy',
            ord_type='limit',
            sz='0.00001',
            px=str(current_price * 0.99),
            td_mode='cross',
            lever='2'
        )
        
        if order_id:
            logger.info(f"✅ 下单成功，订单ID: {order_id}")
            results['place_order'] = True
            
            # 测试查询订单
            logger.info("\n4.3 测试查询订单")
            order_info = await rest_client.get_order('BTC-USDT', order_id)
            if order_info:
                logger.info("✅ 订单查询成功")
                if isinstance(order_info, dict):
                    logger.info(f"  订单状态: {order_info.get('state')}")
                    logger.info(f"  订单价格: {order_info.get('px')}")
                    logger.info(f"  订单数量: {order_info.get('sz')}")
                results['get_order'] = True
            else:
                logger.error("❌ 订单查询失败")
                results['get_order'] = False
            
            # 测试撤单
            logger.info("\n4.4 测试撤单")
            cancel_result = await rest_client.cancel_order('BTC-USDT', order_id)
            if cancel_result:
                logger.info("✅ 撤单成功")
                results['cancel_order'] = True
            else:
                logger.error("❌ 撤单失败")
                results['cancel_order'] = False
        else:
            logger.error("❌ 下单失败")
            results['place_order'] = False
            results['get_order'] = False
            results['cancel_order'] = False
            
    except Exception as e:
        logger.error(f"❌ 订单操作测试失败: {e}")
        results['place_order'] = False
        results['get_order'] = False
        results['cancel_order'] = False
    
    return results


async def test_websocket():
    """测试WebSocket"""
    logger.info("\n" + "=" * 60)
    logger.info("测试5: WebSocket")
    logger.info("=" * 60)
    
    results = {}
    
    try:
        from core.api.okx_websocket_client import OKXWebSocketClient
        
        # 获取API配置
        api_config = env_manager.get_api_config()
        
        # 创建WebSocket客户端
        ws_client = OKXWebSocketClient(
            api_key=api_config['api_key'],
            api_secret=api_config['api_secret'],
            passphrase=api_config['passphrase'],
            is_test=api_config['is_test']
        )
        
        # 连接WebSocket
        logger.info("\n5.1 连接公共WebSocket")
        connected = await ws_client.connect()
        if connected:
            logger.info("✅ WebSocket连接成功")
            results['connect'] = True
        else:
            logger.error("❌ WebSocket连接失败")
            results['connect'] = False
            return results
        
        # 订阅行情
        logger.info("\n5.2 订阅行情")
        subscribed = await ws_client.subscribe('tickers', 'BTC-USDT')
        if subscribed:
            logger.info("✅ 订阅行情成功")
            results['subscribe'] = True
        else:
            logger.error("❌ 订阅行情失败")
            results['subscribe'] = False
        
        # 等待接收数据
        logger.info("\n5.3 等待接收数据 (3秒)")
        await asyncio.sleep(3)
        
        # 断开连接
        logger.info("\n5.4 断开连接")
        await ws_client.close()
        logger.info("✅ WebSocket断开成功")
        results['close'] = True
        
    except Exception as e:
        logger.error(f"❌ WebSocket测试失败: {e}")
        import traceback
        traceback.print_exc()
        results['connect'] = False
        results['subscribe'] = False
        results['close'] = False
    
    return results


def print_test_summary(all_results):
    """打印测试总结"""
    logger.info("\n" + "=" * 60)
    logger.info("测试总结")
    logger.info("=" * 60)
    
    all_passed = True
    for test_name, results in all_results.items():
        logger.info(f"\n{test_name}:")
        for item_name, result in results.items():
            status = "✅ 通过" if result else "❌ 失败"
            logger.info(f"  {item_name}: {status}")
            if not result:
                all_passed = False
    
    logger.info("\n" + "=" * 60)
    if all_passed:
        logger.info("🎉 所有测试通过！")
    else:
        logger.warning("⚠️  部分测试未通过")
    logger.info("=" * 60)


async def main():
    """主测试函数"""
    logger.info("\n" + "=" * 60)
    logger.info("模拟盘全面功能测试")
    logger.info("=" * 60)
    
    all_results = {}
    
    try:
        # 获取API配置
        api_config = env_manager.get_api_config()
        logger.info(f"\n当前环境: {env_manager.get_current_env().upper()}")
        logger.info(f"API Key: {api_config['api_key'][:8]}...")
        logger.info(f"模拟盘模式: {api_config['is_test']}")
        
        # 导入REST客户端
        from core.api.okx_rest_client import OKXRESTClient
        
        # 创建REST客户端
        rest_client = OKXRESTClient(
            api_key=api_config['api_key'],
            api_secret=api_config['api_secret'],
            passphrase=api_config['passphrase'],
            is_test=api_config['is_test']
        )
        
        # 测试1: 公共API
        all_results['公共API'] = await test_public_api(rest_client)
        
        # 测试2: API缓存
        all_results['API缓存'] = await test_api_caching(rest_client)
        
        # 测试3: 私有API
        all_results['私有API'] = await test_private_api(rest_client)
        
        # 获取行情数据用于订单测试
        ticker = await rest_client.get_ticker('BTC-USDT')
        
        # 测试4: 订单操作
        if ticker:
            all_results['订单操作'] = await test_order_operations(rest_client, ticker)
        
        # 清理REST会话
        if hasattr(rest_client, 'session') and rest_client.session:
            await rest_client.session.close()
        
        # 测试5: WebSocket
        all_results['WebSocket'] = await test_websocket()
        
        # 打印测试总结
        print_test_summary(all_results)
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
