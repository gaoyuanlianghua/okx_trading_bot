#!/usr/bin/env python3
"""
模拟盘功能全面测试脚本
测试所有核心功能在模拟盘中的运行情况
"""

import asyncio
import logging
import json
from core.config.env_manager import env_manager
from core.api.okx_rest_client import OKXRESTClient
from core.api.okx_websocket_client import OKXWebSocketClient

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FeatureTester:
    """功能测试器"""
    
    def __init__(self):
        self.rest_client = None
        self.ws_client = None
        self.api_config = env_manager.get_api_config()
    
    async def setup(self):
        """设置测试环境"""
        logger.info("\n" + "=" * 60)
        logger.info("模拟盘功能全面测试")
        logger.info("=" * 60)
        logger.info(f"当前环境: {env_manager.get_current_env().upper()}")
        logger.info(f"API Key: {self.api_config['api_key'][:8]}...")
        logger.info(f"模拟盘模式: {self.api_config['is_test']}")
        
        # 创建REST客户端
        self.rest_client = OKXRESTClient(
            api_key=self.api_config['api_key'],
            api_secret=self.api_config['api_secret'],
            passphrase=self.api_config['passphrase'],
            is_test=self.api_config['is_test']
        )
    
    async def test_public_api(self):
        """测试公共API"""
        logger.info("\n" + "-" * 60)
        logger.info("测试1: 公共API")
        logger.info("-" * 60)
        
        try:
            # 1. 测试服务器时间
            logger.info("\n1.1 测试服务器时间")
            server_time = await self.rest_client.get_server_time()
            if server_time:
                logger.info(f"✅ 服务器时间获取成功: {server_time}")
            else:
                logger.error("❌ 服务器时间获取失败")
                return False
            
            # 2. 测试行情数据
            logger.info("\n1.2 测试行情数据")
            ticker = await self.rest_client.get_ticker('BTC-USDT')
            if ticker:
                logger.info("✅ 行情数据获取成功")
                logger.info(f"  BTC-USDT 最新价: {ticker.get('last')}")
                logger.info(f"  24h 成交量: {ticker.get('vol24h')}")
                logger.info(f"  24h 涨跌幅: {ticker.get('px24hPct')}%")
            else:
                logger.error("❌ 行情数据获取失败")
                return False
            
            # 3. 测试K线数据
            logger.info("\n1.3 测试K线数据")
            candles = await self.rest_client.get_candles('BTC-USDT', bar='1m', limit=5)
            if candles:
                logger.info("✅ K线数据获取成功")
                for candle in candles[:3]:
                    logger.info(f"  {candle[0]}: 开 {candle[1]}, 高 {candle[2]}, 低 {candle[3]}, 收 {candle[4]}")
            else:
                logger.error("❌ K线数据获取失败")
                return False
            
            # 4. 测试交易产品信息
            logger.info("\n1.4 测试交易产品信息")
            instruments = await self.rest_client.get_instruments(inst_type='SPOT')
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
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 公共API测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_api_caching(self):
        """测试API缓存"""
        logger.info("\n" + "-" * 60)
        logger.info("测试2: API缓存")
        logger.info("-" * 60)
        
        try:
            # 第一次请求
            logger.info("\n2.1 第一次请求（不使用缓存）")
            start_time = asyncio.get_event_loop().time()
            ticker1 = await self.rest_client.get_ticker('BTC-USDT')
            elapsed1 = asyncio.get_event_loop().time() - start_time
            logger.info(f"  耗时: {elapsed1:.3f}s")
            
            # 第二次请求（应该使用缓存）
            logger.info("\n2.2 第二次请求（应该使用缓存）")
            start_time = asyncio.get_event_loop().time()
            ticker2 = await self.rest_client.get_ticker('BTC-USDT')
            elapsed2 = asyncio.get_event_loop().time() - start_time
            logger.info(f"  耗时: {elapsed2:.3f}s")
            
            if elapsed2 < elapsed1:
                logger.info("✅ API缓存测试成功")
            else:
                logger.warning("⚠️  API缓存可能未生效")
            
            # 检查API统计
            logger.info("\n2.3 API调用统计")
            logger.info(f"  总调用次数: {self.rest_client.api_stats['total_calls']}")
            logger.info(f"  成功调用次数: {self.rest_client.api_stats['success_calls']}")
            logger.info(f"  失败调用次数: {self.rest_client.api_stats['failed_calls']}")
            logger.info(f"  缓存调用次数: {self.rest_client.api_stats['cached_calls']}")
            logger.info(f"  平均响应时间: {self.rest_client.api_stats['avg_response_time']:.3f}s")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ API缓存测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_websocket_public(self):
        """测试公共WebSocket"""
        logger.info("\n" + "-" * 60)
        logger.info("测试3: 公共WebSocket")
        logger.info("-" * 60)
        
        try:
            # 创建WebSocket客户端
            self.ws_client = OKXWebSocketClient(
                api_key=self.api_config['api_key'],
                api_secret=self.api_config['api_secret'],
                passphrase=self.api_config['passphrase'],
                is_test=self.api_config['is_test']
            )
            
            # 连接WebSocket
            logger.info("\n3.1 连接公共WebSocket")
            connected = await self.ws_client.connect()
            if connected:
                logger.info("✅ WebSocket连接成功")
            else:
                logger.error("❌ WebSocket连接失败")
                return False
            
            # 订阅行情
            logger.info("\n3.2 订阅行情")
            subscribed = await self.ws_client.subscribe('tickers', 'BTC-USDT')
            if subscribed:
                logger.info("✅ 订阅行情成功")
            else:
                logger.error("❌ 订阅行情失败")
                return False
            
            # 等待接收数据
            logger.info("\n3.3 等待接收数据 (3秒)")
            await asyncio.sleep(3)
            
            # 断开连接
            logger.info("\n3.4 断开连接")
            await self.ws_client.close()
            logger.info("✅ WebSocket断开成功")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 公共WebSocket测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_private_api(self):
        """测试私有API（需要有效的模拟盘API密钥）"""
        logger.info("\n" + "-" * 60)
        logger.info("测试4: 私有API")
        logger.info("-" * 60)
        logger.info("注意：私有API需要有效的模拟盘API密钥")
        
        try:
            # 1. 测试账户余额
            logger.info("\n4.1 测试账户余额")
            balance = await self.rest_client.get_account_balance()
            if balance:
                logger.info("✅ 账户余额获取成功")
                if isinstance(balance, list) and len(balance) > 0:
                    for item in balance:
                        if isinstance(item, dict):
                            logger.info(f"  总权益: {item.get('totalEq', 'N/A')}")
                            for detail in item.get('details', []):
                                if isinstance(detail, dict) and float(detail.get('cashBal', '0')) > 0:
                                    logger.info(f"  {detail.get('ccy')}: {detail.get('cashBal')} (可用: {detail.get('availBal')})")
            else:
                logger.error("❌ 账户余额获取失败")
                logger.info("提示：请确保使用有效的模拟盘API密钥")
                return False
            
            # 2. 测试持仓信息
            logger.info("\n4.2 测试持仓信息")
            positions = await self.rest_client.get_positions(inst_type='MARGIN')
            if positions:
                logger.info(f"✅ 持仓信息获取成功，共 {len(positions)} 个持仓")
                for pos in positions[:3]:
                    logger.info(f"  {pos.get('instId')}: 持仓 {pos.get('pos')}, 均价 {pos.get('avgPx')}")
            else:
                logger.info("ℹ️  无持仓信息")
            
            # 3. 测试未成交订单
            logger.info("\n4.3 测试未成交订单")
            pending_orders = await self.rest_client.get_orders_pending()
            if pending_orders:
                logger.info(f"✅ 未成交订单获取成功，共 {len(pending_orders)} 个订单")
                for order in pending_orders[:3]:
                    logger.info(f"  订单ID: {order.get('ordId')}, 状态: {order.get('state')}")
            else:
                logger.info("ℹ️  无未成交订单")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 私有API测试失败: {e}")
            logger.info("提示：请确保使用有效的模拟盘API密钥")
            import traceback
            traceback.print_exc()
            return False
    
    async def run_all_tests(self):
        """运行所有测试"""
        results = {}
        
        # 测试1: 公共API
        results['公共API'] = await self.test_public_api()
        
        # 测试2: API缓存
        results['API缓存'] = await self.test_api_caching()
        
        # 测试3: 公共WebSocket
        results['公共WebSocket'] = await self.test_websocket_public()
        
        # 测试4: 私有API（可选）
        results['私有API'] = await self.test_private_api()
        
        # 打印测试结果
        logger.info("\n" + "=" * 60)
        logger.info("测试结果总结")
        logger.info("=" * 60)
        for test_name, result in results.items():
            status = "✅ 通过" if result else "❌ 失败"
            logger.info(f"{test_name}: {status}")
        
        # 清理
        if hasattr(self.rest_client, 'session') and self.rest_client.session:
            await self.rest_client.session.close()
        
        return all(results.values())


async def main():
    """主测试函数"""
    tester = FeatureTester()
    await tester.setup()
    success = await tester.run_all_tests()
    
    if success:
        logger.info("\n✅ 所有测试通过！")
    else:
        logger.warning("\n⚠️  部分测试未通过")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
