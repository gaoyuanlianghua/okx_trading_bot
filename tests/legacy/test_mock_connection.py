#!/usr/bin/env python3
"""
简单的模拟盘连接测试脚本
测试API连接和模拟盘配置
"""

import asyncio
import logging
import json
from core.config.env_manager import env_manager
from core.api.okx_rest_client import OKXRESTClient

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_simple_connection():
    """简单的连接测试"""
    logger.info("\n" + "=" * 60)
    logger.info("简单模拟盘连接测试")
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
            return False
        
        # 测试直接的HTTP请求
        import aiohttp
        async with aiohttp.ClientSession() as session:
            # 测试公共API（不需要认证）
            logger.info("\n测试公共API (GET /api/v5/public/time)")
            url = "https://www.okx.com/api/v5/public/time"
            try:
                async with session.get(url, timeout=10) as response:
                    logger.info(f"公共API状态码: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"公共API响应: {json.dumps(data, indent=2)}")
                        if data.get('code') == '0':
                            logger.info("✅ 公共API测试成功")
                        else:
                            logger.error(f"❌ 公共API返回错误: {data.get('msg')}")
                    else:
                        logger.error(f"❌ 公共API请求失败: {response.status}")
            except Exception as e:
                logger.error(f"❌ 公共API请求异常: {e}")
            
            # 测试模拟盘API头
            logger.info("\n测试模拟盘API头")
            headers = {
                "Content-Type": "application/json",
                "x-simulated-trading": "1"  # 模拟盘请求头
            }
            logger.info(f"模拟盘请求头: {headers}")
        
        # 创建REST客户端
        rest_client = OKXRESTClient(
            api_key=api_config['api_key'],
            api_secret=api_config['api_secret'],
            passphrase=api_config['passphrase'],
            is_test=api_config['is_test']
        )
        
        # 测试服务器时间
        logger.info("\n测试服务器时间")
        server_time = await rest_client.get_server_time()
        if server_time:
            logger.info(f"✅ 服务器时间获取成功: {server_time}")
        else:
            logger.error("❌ 服务器时间获取失败")
        
        # 测试行情数据
        logger.info("\n测试行情数据 (BTC-USDT)")
        ticker = await rest_client.get_ticker('BTC-USDT')
        if ticker:
            logger.info(f"✅ 行情数据获取成功: {json.dumps(ticker, indent=2)}")
        else:
            logger.error("❌ 行情数据获取失败")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    success = loop.run_until_complete(test_simple_connection())
    loop.close()
    
    if success:
        logger.info("\n✅ 模拟盘连接测试成功！")
    else:
        logger.error("\n❌ 模拟盘连接测试失败！")
