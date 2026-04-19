import sys
sys.path.append("/root/okx_trading_bot")
from core.api.okx_rest_client import OKXRESTClient
import asyncio

async def check_account():
    # 初始化OKX REST客户端
    client = OKXRESTClient(
        api_key="c6637a95-ca47-4e23-8c0f-c1803d71b392",
        api_secret="528F306447BAFA6CBB15579522473A95",
        passphrase="Gy528329818.123",
        is_test=False
    )
    
    # 获取账户余额
    balance = await client.get_account_balance()
    print("账户余额:")
    print(balance)
    
    # 获取未成交订单
    pending_orders = await client.get_pending_orders(inst_type="SPOT")
    print("\n未成交订单:")
    print(pending_orders)
    
    # 获取历史订单
    history_orders = await client.get_order_history(inst_type="SPOT")
    print("\n历史订单:")
    print(history_orders)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(check_account())
    loop.close()
