#!/usr/bin/env python3
"""
测试各种交易类型的脚本
"""

import asyncio
import logging
import yaml
import json
from decimal import Decimal

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_trade_types():
    """测试各种交易类型"""
    try:
        logger.info("开始测试各种交易类型...")
        
        # 读取当前环境配置
        with open('config/current_env.json', 'r') as f:
            current_env = json.load(f)
        env = current_env.get('env', 'test')
        
        # 读取对应环境的配置文件
        config_file = f'config/config_{env}.yaml' if env != 'live' else 'config/config_live.yaml'
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        api_config = config.get('api', {})
        api_key = api_config.get('api_key')
        api_secret = api_config.get('api_secret')
        passphrase = api_config.get('passphrase')
        is_test = api_config.get('is_test', env == 'test')
        
        if not api_key or not api_secret or not passphrase:
            logger.error(f"请在{config_file}中配置API参数")
            return
        
        # 初始化OKX REST客户端
        from core.api.okx_rest_client import OKXRESTClient
        rest_client = OKXRESTClient(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            is_test=is_test
        )
        
        # 测试现货买入 - 市价单
        logger.info("测试现货买入 - 市价单")
        try:
            # 构建订单参数
            order_params = {
                'inst_id': 'BTC-USDT',
                'side': 'buy',
                'ord_type': 'market',
                'sz': '1',  # 1 USDT
                'td_mode': 'cash',
                'tgtCcy': 'quote_ccy'  # 按USDT金额下单
            }
            
            # 发送订单
            order_id = await rest_client.place_order(**order_params)
            logger.info(f"  结果: 订单ID={order_id}")
        except Exception as e:
            logger.error(f"  失败: {e}")
        
        # 测试现货买入 - 限价单
        logger.info("测试现货买入 - 限价单")
        try:
            # 获取当前价格
            ticker = await rest_client.get_ticker("BTC-USDT")
            if ticker and isinstance(ticker, dict):
                current_price = Decimal(str(ticker.get('last', '0')))
                if current_price > 0:
                    # 设置限价为当前价格的95%，确保订单不会立即成交
                    limit_price = current_price * Decimal('0.95')
                    
                    # 构建订单参数
                    order_params = {
                        'inst_id': 'BTC-USDT',
                        'side': 'buy',
                        'ord_type': 'limit',
                        'px': str(limit_price),
                        'sz': '1',  # 1 USDT
                        'td_mode': 'cash',
                        'tgtCcy': 'quote_ccy'  # 按USDT金额下单
                    }
                    
                    # 发送订单
                    order_id = await rest_client.place_order(**order_params)
                    logger.info(f"  结果: 订单ID={order_id}")
                else:
                    logger.error("  无法获取当前价格")
            else:
                logger.error("  无法获取当前价格")
        except Exception as e:
            logger.error(f"  失败: {e}")
        
        # 测试现货卖出 - 市价单
        logger.info("测试现货卖出 - 市价单")
        try:
            # 先获取BTC余额
            balance = await rest_client.get_account_balance()
            btc_balance = Decimal('0')
            if balance and isinstance(balance, dict):
                data = balance.get('data', [])
                if data:
                    details = data[0].get('details', [])
                    for detail in details:
                        if detail.get('ccy') == 'BTC':
                            btc_balance = Decimal(str(detail.get('availBal', '0')))
                            logger.info(f"  BTC可用余额: {btc_balance}")
                            break
            
            # 即使BTC余额显示为0，也尝试卖出一个很小的数量
            if btc_balance > Decimal('0') or True:
                # 构建订单参数
                order_params = {
                    'inst_id': 'BTC-USDT',
                    'side': 'sell',
                    'ord_type': 'market',
                    'sz': '0.00001',  # 卖出一个很小的数量
                    'td_mode': 'cash',
                    'tgtCcy': 'base_ccy'  # 按BTC数量下单
                }
                
                # 发送订单
                order_id = await rest_client.place_order(**order_params)
                logger.info(f"  结果: 订单ID={order_id}")
            else:
                logger.error("  BTC余额不足")
        except Exception as e:
            logger.error(f"  失败: {e}")
        
        # 测试其他交易对 - ETH-USDT
        logger.info("测试其他交易对 - ETH-USDT")
        try:
            # 构建订单参数
            order_params = {
                'inst_id': 'ETH-USDT',
                'side': 'buy',
                'ord_type': 'market',
                'sz': '1',  # 1 USDT
                'td_mode': 'cash',
                'tgtCcy': 'quote_ccy'  # 按USDT金额下单
            }
            
            # 发送订单
            order_id = await rest_client.place_order(**order_params)
            logger.info(f"  结果: 订单ID={order_id}")
        except Exception as e:
            logger.error(f"  失败: {e}")
        
        # 测试现货杠杆交易
        logger.info("测试现货杠杆交易 - BTC-USDT")
        try:
            # 构建订单参数
            order_params = {
                'inst_id': 'BTC-USDT',
                'side': 'buy',
                'ord_type': 'market',
                'sz': '1',  # 1 USDT
                'td_mode': 'cross',  # 现货杠杆交易（全仓）
                'tgtCcy': 'quote_ccy'  # 按USDT金额下单
            }
            
            # 发送订单
            order_id = await rest_client.place_order(**order_params)
            logger.info(f"  结果: 订单ID={order_id}")
        except Exception as e:
            logger.error(f"  失败: {e}")
        
        # 测试期货交易
        logger.info("测试期货交易 - BTC-USDT-260627")
        try:
            # 构建订单参数
            order_params = {
                'inst_id': 'BTC-USDT-260627',  # 期货合约（使用USDT计价）
                'side': 'buy',
                'ord_type': 'market',
                'sz': '1',  # 1 张
                'td_mode': 'cross',  # 全仓
                'lever': '10',  # 10倍杠杆
                'posSide': 'long'  # 多头
            }
            
            # 发送订单
            order_id = await rest_client.place_order(**order_params)
            logger.info(f"  结果: 订单ID={order_id}")
        except Exception as e:
            logger.error(f"  失败: {e}")
        
        # 测试永续合约交易
        logger.info("测试永续合约交易 - BTC-USDT-SWAP")
        try:
            # 构建订单参数
            order_params = {
                'inst_id': 'BTC-USDT-SWAP',  # 永续合约（使用USDT计价）
                'side': 'buy',
                'ord_type': 'market',
                'sz': '1',  # 1 张
                'td_mode': 'cross',  # 全仓
                'lever': '10',  # 10倍杠杆
                'posSide': 'long'  # 多头
            }
            
            # 发送订单
            order_id = await rest_client.place_order(**order_params)
            logger.info(f"  结果: 订单ID={order_id}")
        except Exception as e:
            logger.error(f"  失败: {e}")
        
        logger.info("交易类型测试完成")
        
    except Exception as e:
        logger.error(f"测试交易类型失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
    finally:
        # 关闭REST客户端
        if 'rest_client' in locals():
            await rest_client.close()
            logger.info("已关闭REST客户端")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_trade_types())
