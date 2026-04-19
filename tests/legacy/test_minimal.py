#!/usr/bin/env python3
"""
最小化测试脚本
只测试OKXRESTClient的基本功能
"""

import asyncio
import logging
import json

# 直接导入需要的模块，避免导入整个包
from core.api.okx_rest_client import OKXRESTClient

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_minimal():
    """最小化测试"""
    logger.info("\n" + "=" * 60)
    logger.info("最小化测试")
    logger.info("=" * 60)
    
    try:
        # 直接硬编码API配置（仅测试用）
        api_key = "19500a62-d018-44d8-9a24-01b87a2d6488"
        api_secret = "5939DA43F600616659F41F905321D502"
        passphrase = "Gy528329818.123"
        is_test = True
        
        logger.info(f"API Key: {api_key[:8]}...")
        logger.info(f"模拟盘模式: {is_test}")
        
        # 测试直接的HTTP请求
        import aiohttp
        async with aiohttp.ClientSession() as session:
            # 测试公共API
            url = "https://www.okx.com/api/v5/public/time"
            logger.info("\n测试直接HTTP请求 (服务器时间)")
            async with session.get(url, timeout=10) as response:
                logger.info(f"状态码: {response.status}")
                text = await response.text()
                logger.info(f"响应: {text}")
                
                data = json.loads(text)
                if data.get('code') == '0':
                    logger.info("✅ 直接HTTP请求测试成功")
                else:
                    logger.error(f"❌ 直接HTTP请求测试失败: {data.get('msg')}")
        
        # 测试行情数据
        async with aiohttp.ClientSession() as session:
            url = "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT"
            logger.info("\n测试直接HTTP请求 (行情数据)")
            async with session.get(url, timeout=10) as response:
                logger.info(f"状态码: {response.status}")
                text = await response.text()
                logger.info(f"响应: {text[:200]}...")
                
                data = json.loads(text)
                if data.get('code') == '0':
                    logger.info("✅ 直接HTTP请求测试成功")
                    ticker = data.get('data', [{}])[0]
                    logger.info(f"BTC-USDT 最新价: {ticker.get('last')}")
                else:
                    logger.error(f"❌ 直接HTTP请求测试失败: {data.get('msg')}")
        
        # 现在测试REST客户端
        logger.info("\n测试REST客户端")
        rest_client = OKXRESTClient(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            is_test=is_test
        )
        
        # 测试服务器时间
        logger.info("\n测试服务器时间")
        server_time = await rest_client.get_server_time()
        if server_time:
            logger.info(f"✅ 服务器时间获取成功: {server_time}")
        else:
            logger.error("❌ 服务器时间获取失败")
        
        # 测试行情数据
        logger.info("\n测试行情数据")
        ticker = await rest_client.get_ticker('BTC-USDT')
        if ticker:
            logger.info(f"✅ 行情数据获取成功")
            logger.info(f"BTC-USDT 最新价: {ticker.get('last', 'N/A')}")
        else:
            logger.error("❌ 行情数据获取失败")
        
        # 清理会话
        if hasattr(rest_client, 'session') and rest_client.session:
            await rest_client.session.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    success = loop.run_until_complete(test_minimal())
    loop.close()
    
    if success:
        logger.info("\n✅ 最小化测试成功！")
    else:
        logger.error("\n❌ 最小化测试失败！")
