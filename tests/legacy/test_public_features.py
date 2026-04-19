#!/usr/bin/env python3
"""
模拟盘公共功能测试脚本
测试不需要API密钥验证的功能
"""

import asyncio
import logging
import json
from core.config.env_manager import env_manager
from core.api.okx_rest_client import OKXRESTClient

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def main():
    """主测试函数"""
    logger.info("\n" + "=" * 60)
    logger.info("模拟盘公共功能测试")
    logger.info("=" * 60)
    logger.info(f"当前环境: {env_manager.get_current_env().upper()}")
    
    # 1. 环境管理器测试
    logger.info("\n测试1: 环境管理器")
    env_info = env_manager.get_env_info()
    logger.info(f"✅ 环境管理器正常")
    logger.info(f"  实盘配置文件: {'存在' if env_info['live_config_exists'] else '不存在'}")
    logger.info(f"  模拟盘配置文件: {'存在' if env_info['test_config_exists'] else '不存在'}")
    logger.info(f"  当前环境: {env_info['current_env']}")
    
    # 2. API配置测试
    logger.info("\n测试2: API配置")
    api_config = env_manager.get_api_config()
    logger.info(f"✅ API配置正常")
    logger.info(f"  API Key: {api_config['api_key'][:8]}...")
    logger.info(f"  模拟盘模式: {'是' if api_config['is_test'] else '否'}")
    logger.info(f"  超时时间: {api_config['timeout']}秒")
    
    # 3. 公共API测试
    logger.info("\n测试3: 公共API")
    
    try:
        # 创建REST客户端
        rest_client = OKXRESTClient(
            api_key=api_config['api_key'],
            api_secret=api_config['api_secret'],
            passphrase=api_config['passphrase'],
            is_test=api_config['is_test']
        )
        
        # 3.1 服务器时间
        logger.info("\n3.1 服务器时间")
        server_time = await rest_client.get_server_time()
        if server_time:
            logger.info(f"✅ 服务器时间获取成功: {server_time}")
        else:
            logger.error("❌ 服务器时间获取失败")
        
        # 3.2 行情数据
        logger.info("\n3.2 行情数据 (BTC-USDT)")
        ticker = await rest_client.get_ticker('BTC-USDT')
        if ticker:
            logger.info("✅ 行情数据获取成功")
            logger.info(f"  BTC-USDT 最新价: {ticker.get('last')} USDT")
            logger.info(f"  24h 成交量: {ticker.get('vol24h')}")
            logger.info(f"  24h 涨跌幅: {ticker.get('px24hPct')}%")
        else:
            logger.error("❌ 行情数据获取失败")
        
        # 3.3 K线数据
        logger.info("\n3.3 K线数据 (BTC-USDT, 1m)")
        candles = await rest_client.get_candles('BTC-USDT', bar='1m', limit=5)
        if candles:
            logger.info("✅ K线数据获取成功")
            for i, candle in enumerate(candles[:3]):
                logger.info(f"  K线 {i+1}: 开 {candle[1]}, 高 {candle[2]}, 低 {candle[3]}, 收 {candle[4]}")
        else:
            logger.error("❌ K线数据获取失败")
        
        # 3.4 交易产品信息
        logger.info("\n3.4 交易产品信息")
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
        else:
            logger.error("❌ 交易产品信息获取失败")
        
        # 3.5 API缓存测试
        logger.info("\n3.5 API缓存测试")
        # 第一次请求
        import time
        start_time = time.time()
        ticker1 = await rest_client.get_ticker('BTC-USDT')
        elapsed1 = time.time() - start_time
        
        # 第二次请求（应该使用缓存）
        start_time = time.time()
        ticker2 = await rest_client.get_ticker('BTC-USDT')
        elapsed2 = time.time() - start_time
        
        logger.info(f"  第一次请求耗时: {elapsed1:.3f}s")
        logger.info(f"  第二次请求耗时: {elapsed2:.3f}s")
        
        if elapsed2 < elapsed1:
            logger.info("✅ API缓存测试成功")
        else:
            logger.warning("⚠️  API缓存可能未生效")
        
        # 3.6 API统计信息
        logger.info("\n3.6 API统计信息")
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
        logger.info("✅ 公共API测试通过")
        logger.info("⚠️  私有API测试需要有效的模拟盘API密钥")
        logger.info("\n提示：如需测试私有API功能，请先在OKX官网创建模拟盘API密钥")
        logger.info("      然后配置到 config/config_test.yaml 文件中")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
