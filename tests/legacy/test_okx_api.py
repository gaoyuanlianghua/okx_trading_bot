#!/usr/bin/env python3
"""
测试获取当前账户交易手续费费率
使用OKX REST客户端获取当前账户交易手续费费率
"""

import asyncio
import sys
sys.path.append("/root/okx_trading_bot")
from core.api.okx_rest_client import OKXRESTClient

async def get_fee_rates():
    # 初始化OKX REST客户端
    client = OKXRESTClient(
        api_key="3dd4fb24-e61d-4045-ba75-afb8b1870ccb",
        api_secret="033873E52B7A698C47F3757480F21240",
        passphrase="Gy528329818.123",
        is_test=False
    )
    
    # 获取当前账户交易手续费费率
    print("获取当前账户交易手续费费率...")
    result = await client.get_fee_rates("SPOT", "BTC-USDT")
    print("获取结果:")
    print(result)
    
    # 关闭客户端
    await client.close()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(get_fee_rates())
    loop.close()