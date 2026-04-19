#!/usr/bin/env python3
"""
原始API测试脚本
使用aiohttp直接测试OKX API
"""

import asyncio
import logging
import json
import aiohttp

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_raw_api():
    """测试原始API"""
    logger.info("\n" + "=" * 60)
    logger.info("原始API测试")
    logger.info("=" * 60)
    
    try:
        # 测试公共API
        logger.info("\n测试公共API (服务器时间)")
        url = "https://www.okx.com/api/v5/public/time"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                logger.info(f"状态码: {response.status}")
                text = await response.text()
                logger.info(f"响应: {text}")
                
                data = json.loads(text)
                if data.get('code') == '0':
                    logger.info("✅ 公共API测试成功")
                    logger.info(f"服务器时间: {data.get('data', [{}])[0].get('ts')}")
                else:
                    logger.error(f"❌ 公共API测试失败: {data.get('msg')}")
        
        # 测试行情数据
        logger.info("\n测试行情数据 (BTC-USDT)")
        url = "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                logger.info(f"状态码: {response.status}")
                text = await response.text()
                # 只显示前200个字符
                logger.info(f"响应: {text[:200]}...")
                
                data = json.loads(text)
                if data.get('code') == '0':
                    logger.info("✅ 行情数据测试成功")
                    ticker = data.get('data', [{}])[0]
                    logger.info(f"BTC-USDT 最新价: {ticker.get('last')}")
                else:
                    logger.error(f"❌ 行情数据测试失败: {data.get('msg')}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    success = loop.run_until_complete(test_raw_api())
    loop.close()
    
    if success:
        logger.info("\n✅ 原始API测试成功！")
    else:
        logger.error("\n❌ 原始API测试失败！")
