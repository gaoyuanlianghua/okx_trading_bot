#!/usr/bin/env python3
"""
OKX交易机器人网络测试脚本
测试网络连接、API响应时间和WebSocket连接
"""

import asyncio
import time
import logging
from core.api.okx_rest_client import OKXRESTClient
from core.api.okx_websocket_client import OKXWebSocketClient

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_rest_api():
    """测试REST API连接"""
    logger.info("开始测试REST API连接...")
    
    # 初始化REST客户端（使用模拟盘）
    client = OKXRESTClient(
        api_key="",
        api_secret="",
        passphrase="",
        is_test=True,
        timeout=30
    )
    
    try:
        # 测试1: 获取服务器时间
        logger.info("测试1: 获取服务器时间")
        start_time = time.time()
        server_time = await client.get_server_time()
        end_time = time.time()
        
        if server_time:
            logger.info(f"✓ 服务器时间: {server_time}")
            logger.info(f"  响应时间: {((end_time - start_time) * 1000):.2f}ms")
        else:
            logger.error("✗ 获取服务器时间失败")
        
        # 测试2: 获取产品信息
        logger.info("\n测试2: 获取产品信息")
        start_time = time.time()
        instruments = await client.get_instruments(inst_type="SWAP")
        end_time = time.time()
        
        if instruments:
            logger.info(f"✓ 成功获取 {len(instruments)} 个产品")
            logger.info(f"  响应时间: {((end_time - start_time) * 1000):.2f}ms")
            # 显示前5个产品
            for i, inst in enumerate(instruments[:5]):
                logger.info(f"  {i+1}. {inst.get('instId')}")
        else:
            logger.error("✗ 获取产品信息失败")
        
        # 测试3: 获取行情数据
        logger.info("\n测试3: 获取行情数据")
        start_time = time.time()
        ticker = await client.get_ticker("BTC-USDT-SWAP")
        end_time = time.time()
        
        if ticker:
            logger.info(f"✓ BTC-USDT-SWAP 行情:")
            logger.info(f"  最新价格: {ticker.get('last')}")
            logger.info(f"  响应时间: {((end_time - start_time) * 1000):.2f}ms")
        else:
            logger.error("✗ 获取行情数据失败")
        
        # 测试4: 获取K线数据
        logger.info("\n测试4: 获取K线数据")
        start_time = time.time()
        candles = await client.get_candles("BTC-USDT-SWAP", bar="1m", limit=10)
        end_time = time.time()
        
        if candles:
            logger.info(f"✓ 成功获取 {len(candles)} 条K线数据")
            logger.info(f"  响应时间: {((end_time - start_time) * 1000):.2f}ms")
            # 显示最新一条K线
            if candles:
                latest_candle = candles[0]
                logger.info(f"  最新K线: 时间={latest_candle[0]}, 开盘={latest_candle[1]}, 收盘={latest_candle[4]}")
        else:
            logger.error("✗ 获取K线数据失败")
        
    finally:
        # 关闭客户端
        await client.close()
    
    logger.info("\nREST API测试完成")


async def test_websocket():
    """测试WebSocket连接"""
    logger.info("\n开始测试WebSocket连接...")
    
    # 初始化WebSocket客户端
    ws_client = OKXWebSocketClient(
        api_key="",
        api_secret="",
        passphrase="",
        is_test=True
    )
    
    try:
        # 连接WebSocket
        logger.info("连接WebSocket...")
        await ws_client.connect()
        
        # 订阅BTC-USDT-SWAP的行情
        logger.info("订阅BTC-USDT-SWAP行情...")
        await ws_client.subscribe_public("BTC-USDT-SWAP", "ticker")
        
        # 等待接收数据
        logger.info("等待接收WebSocket数据...")
        start_time = time.time()
        
        # 等待5秒接收数据
        await asyncio.sleep(5)
        
        # 检查是否接收到数据
        if ws_client.received_messages:
            logger.info(f"✓ 成功接收 {len(ws_client.received_messages)} 条WebSocket消息")
            # 显示最新一条消息
            latest_msg = ws_client.received_messages[-1]
            logger.info(f"  最新消息类型: {latest_msg.get('arg', {}).get('channel')}")
        else:
            logger.warning("⚠ 未接收到WebSocket消息")
        
        end_time = time.time()
        logger.info(f"WebSocket连接时间: {((end_time - start_time) * 1000):.2f}ms")
        
    except Exception as e:
        logger.error(f"WebSocket测试失败: {e}")
    finally:
        # 关闭WebSocket连接
        await ws_client.disconnect()
    
    logger.info("WebSocket测试完成")


async def test_network_performance():
    """测试网络性能"""
    logger.info("\n开始测试网络性能...")
    
    # 初始化REST客户端
    client = OKXRESTClient(
        api_key="",
        api_secret="",
        passphrase="",
        is_test=True,
        timeout=30
    )
    
    try:
        # 测试多次请求的响应时间
        test_count = 10
        response_times = []
        
        logger.info(f"执行 {test_count} 次API请求测试...")
        
        for i in range(test_count):
            start_time = time.time()
            await client.get_server_time()
            end_time = time.time()
            response_time = (end_time - start_time) * 1000
            response_times.append(response_time)
            logger.info(f"  请求 {i+1}: {response_time:.2f}ms")
        
        # 计算统计数据
        if response_times:
            avg_time = sum(response_times) / len(response_times)
            max_time = max(response_times)
            min_time = min(response_times)
            
            logger.info("\n性能统计:")
            logger.info(f"  平均响应时间: {avg_time:.2f}ms")
            logger.info(f"  最大响应时间: {max_time:.2f}ms")
            logger.info(f"  最小响应时间: {min_time:.2f}ms")
        
    finally:
        await client.close()
    
    logger.info("网络性能测试完成")


async def main():
    """主测试函数"""
    logger.info("=" * 60)
    logger.info("OKX交易机器人网络测试")
    logger.info("=" * 60)
    
    # 运行所有测试
    await test_rest_api()
    await test_websocket()
    await test_network_performance()
    
    logger.info("\n" + "=" * 60)
    logger.info("网络测试完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
