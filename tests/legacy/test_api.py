import sys
sys.path.append("/root/okx_trading_bot")
from core.api.okx_rest_client import OKXRESTClient
import asyncio

async def test_api():
    # 初始化OKX REST客户端
    client = OKXRESTClient(
        api_key="c6637a95-ca47-4e23-8c0f-c1803d71b392",
        api_secret="528F306447BAFA6CBB15579522473A95",
        passphrase="Gy528329818.123",
        is_test=False
    )
    
    print("=" * 60)
    print("测试1: 获取账户余额")
    print("=" * 60)
    balance = await client.get_account_balance()
    print(f"账户余额: {balance}")
    print()
    
    print("=" * 60)
    print("测试2: 尝试下单（使用USDT金额）")
    print("=" * 60)
    # 尝试市价买入2.0 USDT的BTC
    order_id = await client.place_order(
        inst_id="BTC-USDT",
        side="buy",
        ord_type="market",
        sz="2.00",
        td_mode="cash"
    )
    print(f"订单ID: {order_id}")
    print()
    
    print("=" * 60)
    print("测试3: 查看API调用历史")
    print("=" * 60)
    if hasattr(client, 'api_call_history'):
        print(f"API调用历史数量: {len(client.api_call_history)}")
        for i, call in enumerate(client.api_call_history[-5:]):
            print(f"\nAPI调用 {i+1}:")
            print(f"  URL: {call.get('url')}")
            print(f"  方法: {call.get('method')}")
            print(f"  状态码: {call.get('status_code')}")
            print(f"  错误: {call.get('error')}")
            print(f"  响应: {call.get('response')}")
    
    await client.close()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_api())
    loop.close()
