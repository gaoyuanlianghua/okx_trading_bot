#!/usr/bin/env python3
"""
模拟盘功能测试脚本
测试所有核心功能在模拟盘中的运行情况
"""

import asyncio
import logging
from core.config.env_manager import env_manager
from core.api.okx_rest_client import OKXRESTClient
from core.api.okx_websocket_client import OKXWebSocketClient

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_api_connection():
    """测试API连接"""
    logger.info("\n" + "=" * 60)
    logger.info("测试1: API连接")
    logger.info("=" * 60)
    
    try:
        # 获取API配置
        api_config = env_manager.get_api_config()
        logger.info(f"使用环境: {env_manager.get_current_env().upper()}")
        logger.info(f"API Key: {api_config['api_key'][:8]}...")
        logger.info(f"模拟盘模式: {api_config['is_test']}")
        
        # 检查API配置
        if not api_config['api_key'] or not api_config['api_secret'] or not api_config['passphrase']:
            logger.error("❌ API配置不完整，请检查config_test.yaml文件")
            return None
        
        # 创建REST客户端
        rest_client = OKXRESTClient(
            api_key=api_config['api_key'],
            api_secret=api_config['api_secret'],
            passphrase=api_config['passphrase'],
            is_test=api_config['is_test']
        )
        
        # 测试服务器时间（不需要认证的公共API）
        server_time = await rest_client.get_server_time()
        if server_time:
            logger.info(f"✅ 服务器时间获取成功: {server_time}")
        else:
            logger.error("❌ 服务器时间获取失败")
        
        return rest_client
        
    except Exception as e:
        logger.error(f"❌ API连接测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_account_info(rest_client):
    """测试账户信息"""
    logger.info("\n" + "=" * 60)
    logger.info("测试2: 账户信息")
    logger.info("=" * 60)
    
    try:
        # 获取账户余额
        balance = await rest_client.get_account_balance()
        if balance and 'data' in balance:
            logger.info("✅ 账户余额获取成功")
            for item in balance['data']:
                logger.info(f"  总权益: {item.get('totalEq', 'N/A')}")
                for detail in item.get('details', []):
                    if float(detail.get('cashBal', '0')) > 0:
                        logger.info(f"  {detail.get('ccy')}: {detail.get('cashBal')} (可用: {detail.get('availBal')})")
        else:
            logger.error("❌ 账户余额获取失败")
        
        # 获取持仓信息
        positions = await rest_client.get_positions(inst_type='MARGIN')
        if positions and 'data' in positions:
            logger.info("✅ 持仓信息获取成功")
            for pos in positions['data']:
                logger.info(f"  {pos.get('instId')}: 持仓 {pos.get('pos')}, 均价 {pos.get('avgPx')}")
        else:
            logger.info("ℹ️  无持仓信息")
            
    except Exception as e:
        logger.error(f"❌ 账户信息测试失败: {e}")


async def test_market_data(rest_client):
    """测试市场数据"""
    logger.info("\n" + "=" * 60)
    logger.info("测试3: 市场数据")
    logger.info("=" * 60)
    
    try:
        # 获取行情
        ticker = await rest_client.get_ticker('BTC-USDT')
        if ticker and 'data' in ticker:
            data = ticker['data'][0]
            logger.info("✅ 行情数据获取成功")
            logger.info(f"  BTC-USDT 最新价: {data.get('last')} USDT")
            logger.info(f"  24h 成交量: {data.get('vol24h')} USDT")
            logger.info(f"  24h 涨跌幅: {data.get('px24hPct')}%")
        else:
            logger.error("❌ 行情数据获取失败")
        
        # 获取K线数据
        candles = await rest_client.get_candles('BTC-USDT', bar='1m', limit=5)
        if candles and 'data' in candles:
            logger.info("✅ K线数据获取成功")
            for candle in candles['data'][:3]:
                logger.info(f"  {candle[0]}: 开 {candle[1]}, 高 {candle[2]}, 低 {candle[3]}, 收 {candle[4]}")
        else:
            logger.error("❌ K线数据获取失败")
            
    except Exception as e:
        logger.error(f"❌ 市场数据测试失败: {e}")


async def test_order_operations(rest_client):
    """测试订单操作"""
    logger.info("\n" + "=" * 60)
    logger.info("测试4: 订单操作")
    logger.info("=" * 60)
    
    try:
        # 获取当前价格
        ticker = await rest_client.get_ticker('BTC-USDT')
        if not ticker or 'data' not in ticker:
            logger.error("❌ 无法获取当前价格")
            return
        
        current_price = float(ticker['data'][0].get('last', '0'))
        logger.info(f"当前 BTC-USDT 价格: {current_price} USDT")
        
        # 测试下单
        logger.info("\n测试下单...")
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
            
            # 测试撤单
            logger.info("测试撤单...")
            cancel_result = await rest_client.cancel_order('BTC-USDT', order_id)
            if cancel_result:
                logger.info("✅ 撤单成功")
            else:
                logger.error("❌ 撤单失败")
        else:
            logger.error("❌ 下单失败")
            
    except Exception as e:
        logger.error(f"❌ 订单操作测试失败: {e}")


async def test_websocket():
    """测试WebSocket连接"""
    logger.info("\n" + "=" * 60)
    logger.info("测试5: WebSocket连接")
    logger.info("=" * 60)
    
    try:
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
        connected = await ws_client.connect()
        if connected:
            logger.info("✅ WebSocket连接成功")
            
            # 订阅行情
            subscribed = await ws_client.subscribe('tickers', 'BTC-USDT')
            if subscribed:
                logger.info("✅ 订阅行情成功")
            else:
                logger.error("❌ 订阅行情失败")
            
            # 等待3秒接收数据
            await asyncio.sleep(3)
            
            # 断开连接
            await ws_client.close()
            logger.info("✅ WebSocket断开成功")
        else:
            logger.error("❌ WebSocket连接失败")
            
    except Exception as e:
        logger.error(f"❌ WebSocket测试失败: {e}")


async def main():
    """主测试函数"""
    logger.info("开始模拟盘功能测试...")
    
    # 检查当前环境
    if not env_manager.is_test_env():
        logger.error("❌ 当前不在模拟盘环境，请先切换到模拟盘")
        return
    
    # 测试API连接
    rest_client = await test_api_connection()
    if not rest_client:
        return
    
    # 测试账户信息
    await test_account_info(rest_client)
    
    # 测试市场数据
    await test_market_data(rest_client)
    
    # 测试订单操作
    await test_order_operations(rest_client)
    
    # 测试WebSocket
    await test_websocket()
    
    logger.info("\n" + "=" * 60)
    logger.info("模拟盘功能测试完成！")
    logger.info("=" * 60)


if __name__ == "__main__":
    # 兼容旧版本Python
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
