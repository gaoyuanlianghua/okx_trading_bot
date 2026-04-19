#!/usr/bin/env python3
"""
测试OKXRESTClient的request方法
直接测试request方法的行为
"""

import asyncio
import logging
import json
from core.config.env_manager import env_manager
from core.api.okx_rest_client import OKXRESTClient

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_request_method():
    """测试request方法"""
    logger.info("\n" + "=" * 60)
    logger.info("测试OKXRESTClient.request方法")
    logger.info("=" * 60)
    
    try:
        # 获取API配置
        api_config = env_manager.get_api_config()
        logger.info(f"使用环境: {env_manager.get_current_env().upper()}")
        logger.info(f"API Key: {api_config['api_key'][:8]}...")
        logger.info(f"模拟盘模式: {api_config['is_test']}")
        
        # 创建REST客户端
        rest_client = OKXRESTClient(
            api_key=api_config['api_key'],
            api_secret=api_config['api_secret'],
            passphrase=api_config['passphrase'],
            is_test=api_config['is_test']
        )
        
        # 直接测试request方法
        logger.info("\n测试request方法 (GET /public/time)")
        result = await rest_client.request("GET", "/public/time", auth_required=False)
        logger.info(f"request方法返回: {result}")
        logger.info(f"result类型: {type(result)}")
        
        if result:
            logger.info(f"result长度: {len(result)}")
            if len(result) > 0:
                logger.info(f"result[0]: {result[0]}")
                if isinstance(result[0], dict) and 'ts' in result[0]:
                    logger.info(f"服务器时间: {result[0]['ts']}")
                    logger.info("✅ request方法测试成功")
                else:
                    logger.error("❌ request方法返回的数据格式不正确")
            else:
                logger.error("❌ request方法返回空列表")
        else:
            logger.error("❌ request方法返回None")
        
        # 测试行情数据
        logger.info("\n测试request方法 (GET /market/ticker)")
        params = {"instId": "BTC-USDT"}
        result = await rest_client.request("GET", "/market/ticker", params=params, auth_required=False)
        logger.info(f"request方法返回: {result}")
        logger.info(f"result类型: {type(result)}")
        
        if result:
            logger.info(f"result长度: {len(result)}")
            if len(result) > 0:
                logger.info(f"result[0] 包含的键: {list(result[0].keys())[:10]}...")
                if 'last' in result[0]:
                    logger.info(f"BTC-USDT 最新价: {result[0]['last']}")
                    logger.info("✅ 行情数据测试成功")
                else:
                    logger.error("❌ 行情数据格式不正确")
            else:
                logger.error("❌ 行情数据返回空列表")
        else:
            logger.error("❌ 行情数据返回None")
        
        # 测试API统计
        logger.info("\nAPI调用统计:")
        logger.info(f"总调用次数: {rest_client.api_stats['total_calls']}")
        logger.info(f"成功调用次数: {rest_client.api_stats['success_calls']}")
        logger.info(f"失败调用次数: {rest_client.api_stats['failed_calls']}")
        logger.info(f"缓存调用次数: {rest_client.api_stats['cached_calls']}")
        logger.info(f"平均响应时间: {rest_client.api_stats['avg_response_time']:.3f}s")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    success = loop.run_until_complete(test_request_method())
    loop.close()
    
    if success:
        logger.info("\n✅ request方法测试成功！")
    else:
        logger.error("\n❌ request方法测试失败！")
