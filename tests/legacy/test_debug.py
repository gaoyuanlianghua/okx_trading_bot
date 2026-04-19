#!/usr/bin/env python3
"""
调试测试脚本
详细测试OKXRESTClient的request方法
"""

import asyncio
import logging
import json
import aiohttp

# 配置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_debug():
    """调试测试"""
    logger.info("\n" + "=" * 60)
    logger.info("调试测试")
    logger.info("=" * 60)
    
    try:
        # 测试直接的HTTP请求（带模拟盘头）
        logger.info("\n测试1: 直接HTTP请求（带模拟盘头）")
        async with aiohttp.ClientSession() as session:
            url = "https://www.okx.com/api/v5/public/time"
            headers = {"x-simulated-trading": "1"}
            
            logger.info(f"请求URL: {url}")
            logger.info(f"请求头: {headers}")
            
            async with session.get(url, headers=headers, timeout=10) as response:
                logger.info(f"状态码: {response.status}")
                logger.info(f"响应头: {dict(response.headers)}")
                
                text = await response.text()
                logger.info(f"响应内容: {text}")
                
                data = json.loads(text)
                if data.get('code') == '0':
                    logger.info("✅ 直接HTTP请求测试成功")
                else:
                    logger.error(f"❌ 直接HTTP请求测试失败: {data.get('msg')}")
        
        # 现在测试OKXRESTClient
        logger.info("\n测试2: OKXRESTClient")
        
        # 直接导入OKXRESTClient
        from core.api.okx_rest_client import OKXRESTClient
        
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
        
        # 测试request方法
        logger.info("\n测试3: request方法")
        endpoint = "/public/time"
        logger.info(f"测试端点: {endpoint}")
        
        # 直接调用request方法，不使用缓存
        result = await rest_client.request("GET", endpoint, auth_required=False, use_cache=False)
        logger.info(f"request方法返回: {result}")
        logger.info(f"result类型: {type(result)}")
        
        # 测试get_server_time方法
        logger.info("\n测试4: get_server_time方法")
        server_time = await rest_client.get_server_time()
        logger.info(f"get_server_time方法返回: {server_time}")
        
        # 测试get_ticker方法
        logger.info("\n测试5: get_ticker方法")
        ticker = await rest_client.get_ticker('BTC-USDT')
        logger.info(f"get_ticker方法返回: {ticker}")
        
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
    success = loop.run_until_complete(test_debug())
    loop.close()
    
    if success:
        logger.info("\n✅ 调试测试成功！")
    else:
        logger.error("\n❌ 调试测试失败！")
