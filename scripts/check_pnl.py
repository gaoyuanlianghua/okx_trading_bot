#!/usr/bin/env python3
"""
查看BTC持仓盈亏详情
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 设置日志级别
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from core.api.exchange_manager import exchange_manager
from core.utils.config_manager import ConfigManager
from core.utils.logger import get_logger

logger = get_logger(__name__)

async def check_pnl():
    """检查BTC持仓盈亏详情"""
    rest_client = None
    try:
        # 加载配置
        logger.info("正在加载配置...")
        config_manager = ConfigManager()
        
        # 获取API配置
        api_key = config_manager.get("api.api_key")
        api_secret = config_manager.get("api.api_secret")
        passphrase = config_manager.get("api.passphrase")
        is_test = config_manager.get("api.is_test", True)
        
        # 创建REST客户端
        rest_client = exchange_manager.get_exchange(
            "okx",
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            is_test=is_test
        )
        
        if not rest_client:
            logger.error("无法创建REST客户端")
            return
        
        logger.info("=" * 60)
        logger.info("查询BTC持仓盈亏详情")
        logger.info("=" * 60)
        
        # 获取账户余额
        balance = await rest_client.get_account_balance()
        if balance and isinstance(balance, dict):
            details = balance.get('details', [])
            
            # 查找BTC持仓
            btc_info = None
            for item in details:
                if isinstance(item, dict) and item.get('ccy') == 'BTC':
                    btc_info = item
                    break
            
            if btc_info:
                logger.info("\n📊 BTC持仓详情:")
                logger.info("-" * 60)
                
                # 基础信息
                avail_bal = float(btc_info.get('availBal', 0))
                eq = float(btc_info.get('eq', 0))
                eq_usd = float(btc_info.get('eqUsd', 0))
                
                # 成本信息
                acc_avg_px = btc_info.get('accAvgPx', '')
                open_avg_px = btc_info.get('openAvgPx', '')
                
                # 盈亏信息
                spot_upl = float(btc_info.get('spotUpl', 0))
                spot_upl_ratio = float(btc_info.get('spotUplRatio', 0))
                total_pnl = float(btc_info.get('totalPnl', 0))
                total_pnl_ratio = float(btc_info.get('totalPnlRatio', 0))
                
                logger.info(f"  可用余额: {avail_bal} BTC")
                logger.info(f"  总权益: {eq} BTC")
                logger.info(f"  权益价值: {eq_usd} USDT")
                logger.info(f"")
                logger.info(f"  开仓均价(accAvgPx): {acc_avg_px}")
                logger.info(f"  开仓均价(openAvgPx): {open_avg_px}")
                logger.info(f"")
                logger.info(f"  未实现盈亏(spotUpl): {spot_upl} BTC")
                logger.info(f"  未实现盈亏率(spotUplRatio): {spot_upl_ratio * 100:.4f}%")
                logger.info(f"")
                logger.info(f"  总盈亏(totalPnl): {total_pnl} BTC")
                logger.info(f"  总盈亏率(totalPnlRatio): {total_pnl_ratio * 100:.4f}%")
                
                # 手动计算盈亏率
                if acc_avg_px and float(acc_avg_px) > 0:
                    # 获取当前价格
                    ticker = await rest_client.get_ticker("BTC-USDT")
                    if ticker and isinstance(ticker, list) and len(ticker) > 0:
                        current_price = float(ticker[0].get('last', 0))
                        avg_price = float(acc_avg_px)
                        
                        logger.info(f"")
                        logger.info(f"  当前市场价格: {current_price} USDT")
                        logger.info(f"  开仓均价: {avg_price} USDT")
                        
                        # 计算盈亏率
                        pnl_ratio = (current_price - avg_price) / avg_price
                        logger.info(f"")
                        logger.info(f"  📈 手动计算盈亏率: {pnl_ratio * 100:.4f}%")
                        logger.info(f"  📊 平台显示盈亏率: {spot_upl_ratio * 100:.4f}%")
                        
                        if abs(pnl_ratio - spot_upl_ratio) > 0.001:
                            logger.warning(f"  ⚠️ 盈亏率差异较大，可能存在计算错误")
                        else:
                            logger.info(f"  ✅ 盈亏率计算一致")
                
            else:
                logger.info("\n未找到BTC持仓信息")
        else:
            logger.info("\n无法获取账户余额信息")
        
        logger.info("\n" + "=" * 60)
        logger.info("查询完成")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"查询失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        if rest_client and hasattr(rest_client, 'close'):
            await rest_client.close()

if __name__ == "__main__":
    try:
        asyncio.run(check_pnl())
    except AttributeError:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(check_pnl())
