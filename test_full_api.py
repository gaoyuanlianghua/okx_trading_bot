#!/usr/bin/env python3
"""
OKX交易机器人完整API测试脚本
使用真实的API密钥测试所有功能
"""

import asyncio
import time
import logging
import yaml
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def load_config():
    """加载配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


async def test_full_api():
    """测试完整API功能"""
    logger.info("开始完整API测试...")
    
    # 加载配置
    config = await load_config()
    api_config = config.get('api', {})
    
    # 导入OKX REST客户端
    try:
        from core.api.okx_rest_client import OKXRESTClient
    except ImportError as e:
        logger.error(f"导入客户端失败: {e}")
        return
    
    # 初始化REST客户端
    client = OKXRESTClient(
        api_key=api_config.get('api_key', ''),
        api_secret=api_config.get('api_secret', ''),
        passphrase=api_config.get('passphrase', ''),
        is_test=api_config.get('is_test', True),
        timeout=api_config.get('timeout', 30)
    )
    
    try:
        # 测试1: 获取服务器时间（公共API）
        logger.info("测试1: 获取服务器时间")
        start_time = time.time()
        server_time = await client.get_server_time()
        end_time = time.time()
        
        if server_time:
            logger.info(f"✓ 服务器时间: {server_time}")
            logger.info(f"  响应时间: {((end_time - start_time) * 1000):.2f}ms")
        else:
            logger.error("✗ 获取服务器时间失败")
        
        # 测试2: 获取产品信息（公共API）
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
        
        # 测试3: 获取行情数据（公共API）
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
        
        # 测试4: 获取账户余额（私有API，需要认证）
        logger.info("\n测试4: 获取账户余额")
        start_time = time.time()
        balance = await client.get_account_balance()
        end_time = time.time()
        
        if balance:
            logger.info(f"✓ 账户余额获取成功")
            logger.info(f"  响应时间: {((end_time - start_time) * 1000):.2f}ms")
            # 显示余额信息
            for ccy in balance.get('details', []):
                logger.info(f"  {ccy.get('ccy')}: 可用={ccy.get('availBal')}, 总余额={ccy.get('cashBal')}")
        else:
            logger.error("✗ 获取账户余额失败")
        
        # 测试5: 获取持仓信息（私有API，需要认证）
        logger.info("\n测试5: 获取持仓信息")
        start_time = time.time()
        positions = await client.get_positions(inst_type="SWAP")
        end_time = time.time()
        
        if positions:
            logger.info(f"✓ 成功获取 {len(positions)} 个持仓")
            logger.info(f"  响应时间: {((end_time - start_time) * 1000):.2f}ms")
            # 显示持仓信息
            for pos in positions:
                logger.info(f"  {pos.get('instId')}: 方向={pos.get('posSide')}, 数量={pos.get('pos')}")
        else:
            logger.info("⚠ 无持仓信息")
        
        # 测试6: 下单测试（私有API，需要认证）
        logger.info("\n测试6: 下单测试")
        start_time = time.time()
        ord_id = await client.place_order(
            inst_id="BTC-USDT-SWAP",
            side="buy",
            ord_type="market",
            sz="0.001",
            td_mode="cross"
        )
        end_time = time.time()
        
        if ord_id:
            logger.info(f"✓ 下单成功，订单ID: {ord_id}")
            logger.info(f"  响应时间: {((end_time - start_time) * 1000):.2f}ms")
            
            # 测试7: 获取订单信息
            logger.info("\n测试7: 获取订单信息")
            start_time = time.time()
            order_info = await client.get_order_info("BTC-USDT-SWAP", ord_id=ord_id)
            end_time = time.time()
            
            if order_info:
                logger.info(f"✓ 订单信息获取成功")
                logger.info(f"  响应时间: {((end_time - start_time) * 1000):.2f}ms")
                logger.info(f"  订单状态: {order_info.get('state')}")
            else:
                logger.error("✗ 获取订单信息失败")
            
            # 测试8: 撤单测试
            logger.info("\n测试8: 撤单测试")
            start_time = time.time()
            cancel_result = await client.cancel_order("BTC-USDT-SWAP", ord_id=ord_id)
            end_time = time.time()
            
            if cancel_result:
                logger.info(f"✓ 撤单成功")
                logger.info(f"  响应时间: {((end_time - start_time) * 1000):.2f}ms")
            else:
                logger.error("✗ 撤单失败")
        else:
            logger.error("✗ 下单失败")
        
        # 测试9: 获取未成交订单（私有API，需要认证）
        logger.info("\n测试9: 获取未成交订单")
        start_time = time.time()
        pending_orders = await client.get_pending_orders(inst_type="SWAP")
        end_time = time.time()
        
        if pending_orders:
            logger.info(f"✓ 成功获取 {len(pending_orders)} 个未成交订单")
            logger.info(f"  响应时间: {((end_time - start_time) * 1000):.2f}ms")
        else:
            logger.info("⚠ 无未成交订单")
        
        # 测试10: 获取历史订单（私有API，需要认证）
        logger.info("\n测试10: 获取历史订单")
        start_time = time.time()
        history_orders = await client.get_order_history(inst_type="SWAP", limit=5)
        end_time = time.time()
        
        if history_orders:
            logger.info(f"✓ 成功获取 {len(history_orders)} 个历史订单")
            logger.info(f"  响应时间: {((end_time - start_time) * 1000):.2f}ms")
            # 显示最新的订单
            for i, order in enumerate(history_orders[:3]):
                logger.info(f"  {i+1}. {order.get('instId')}: {order.get('side')} {order.get('sz')} 状态: {order.get('state')}")
        else:
            logger.info("⚠ 无历史订单")
        
    finally:
        # 关闭客户端
        await client.close()
    
    logger.info("\n完整API测试完成")


async def main():
    """主测试函数"""
    logger.info("=" * 60)
    logger.info("OKX交易机器人完整API测试")
    logger.info("=" * 60)
    
    # 运行测试
    await test_full_api()
    
    logger.info("\n" + "=" * 60)
    logger.info("测试完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
