#!/usr/bin/env python3
"""
OKX交易机器人网络测试脚本（简化版）
测试网络连接、API响应时间和WebSocket连接
不依赖PyQt5，只测试核心网络功能
"""

import asyncio
import time
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_http_connection():
    """测试HTTP连接"""
    logger.info("开始测试HTTP连接...")
    
    try:
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            # 测试连接到OKX API
            start_time = time.time()
            async with session.get('https://www.okx.com/api/v5/public/time') as response:
                end_time = time.time()
                
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✓ HTTP连接成功")
                    logger.info(f"  响应状态: {response.status}")
                    logger.info(f"  响应时间: {((end_time - start_time) * 1000):.2f}ms")
                    logger.info(f"  服务器时间: {data.get('data', [{}])[0].get('ts')}")
                else:
                    logger.error(f"✗ HTTP连接失败: 状态码 {response.status}")
    except Exception as e:
        logger.error(f"✗ HTTP连接测试失败: {e}")
    
    logger.info("HTTP连接测试完成")


async def test_websocket_connection():
    """测试WebSocket连接"""
    logger.info("\n开始测试WebSocket连接...")
    
    try:
        import websockets
        
        # 连接到OKX WebSocket
        ws_url = "wss://ws.okx.com:8443/ws/v5/public"
        logger.info(f"连接到: {ws_url}")
        
        start_time = time.time()
        async with websockets.connect(ws_url) as websocket:
            end_time = time.time()
            logger.info(f"✓ WebSocket连接成功")
            logger.info(f"  连接时间: {((end_time - start_time) * 1000):.2f}ms")
            
            # 发送订阅请求
            subscribe_msg = {
                "op": "subscribe",
                "args": [
                    {
                        "channel": "ticker",
                        "instId": "BTC-USDT-SWAP"
                    }
                ]
            }
            
            import json
            await websocket.send(json.dumps(subscribe_msg))
            logger.info("  已订阅BTC-USDT-SWAP行情")
            
            # 等待接收数据
            logger.info("  等待接收WebSocket数据...")
            
            # 接收3条消息
            message_count = 0
            max_messages = 3
            
            while message_count < max_messages:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)
                    logger.info(f"  接收到消息: {data.get('arg', {}).get('channel')}")
                    message_count += 1
                except asyncio.TimeoutError:
                    logger.warning("  未接收到WebSocket消息（超时）")
                    break
                    
    except Exception as e:
        logger.error(f"✗ WebSocket连接测试失败: {e}")
    
    logger.info("WebSocket连接测试完成")


async def test_network_performance():
    """测试网络性能"""
    logger.info("\n开始测试网络性能...")
    
    try:
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            # 测试多次请求的响应时间
            test_count = 10
            response_times = []
            
            logger.info(f"执行 {test_count} 次API请求测试...")
            
            for i in range(test_count):
                start_time = time.time()
                async with session.get('https://www.okx.com/api/v5/public/time') as response:
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
    except Exception as e:
        logger.error(f"✗ 网络性能测试失败: {e}")
    
    logger.info("网络性能测试完成")


async def main():
    """主测试函数"""
    logger.info("=" * 60)
    logger.info("OKX交易机器人网络测试")
    logger.info("=" * 60)
    
    # 运行所有测试
    await test_http_connection()
    await test_websocket_connection()
    await test_network_performance()
    
    logger.info("\n" + "=" * 60)
    logger.info("网络测试完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
