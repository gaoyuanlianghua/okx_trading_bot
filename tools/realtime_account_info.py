import sys
sys.path.append("/root/okx_trading_bot")
from core.api.okx_rest_client import OKXRESTClient
import asyncio
import time

async def realtime_account_info():
    # 初始化OKX REST客户端
    client = OKXRESTClient(
        api_key="3dd4fb24-e61d-4045-ba75-afb8b1870ccb",
        api_secret="033873E52B7A698C47F3757480F21240",
        passphrase="Gy528329818.123",
        is_test=False
    )
    
    try:
        while True:
            print("\n" + "="*50)
            print(f"实时账户信息更新 - {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*50)
            
            # 获取账户余额
            balance = await client.get_account_balance()
            if balance:
                print("\n1. 账户余额:")
                print(f"   总权益: {balance.get('totalEq', 'N/A')} USDT")
                print(f"   可用余额: {balance.get('availEq', 'N/A')} USDT")
                print(f"   冻结余额: {balance.get('frozenBal', 'N/A')} USDT")
                
                # 打印各币种余额
                if 'details' in balance:
                    print("\n   各币种余额:")
                    for detail in balance['details']:
                        if float(detail.get('availBal', '0')) > 0:
                            print(f"   - {detail.get('ccy', 'N/A')}: {detail.get('availBal', '0')} (可用) / {detail.get('frozenBal', '0')} (冻结)")
            else:
                print("\n1. 账户余额: 获取失败")
            
            # 获取持仓信息
            positions = await client.get_positions()
            if positions:
                print("\n2. 持仓信息:")
                for pos in positions:
                    if float(pos.get('pos', '0')) > 0:
                        print(f"   - {pos.get('instId', 'N/A')}: {pos.get('pos', '0')} {pos.get('posSide', 'N/A')}")
                        print(f"      平均成本: {pos.get('avgPx', 'N/A')} USDT")
                        print(f"      最新价格: {pos.get('last', 'N/A')} USDT")
                        print(f"      浮动盈亏: {pos.get('unrealizedPnl', 'N/A')} USDT")
            else:
                print("\n2. 持仓信息: 无持仓")
            
            # 获取未成交订单
            pending_orders = await client.get_pending_orders()
            if pending_orders:
                print("\n3. 未成交订单:")
                for order in pending_orders:
                    print(f"   - 订单ID: {order.get('ordId', 'N/A')}")
                    print(f"     产品: {order.get('instId', 'N/A')}")
                    print(f"     方向: {order.get('side', 'N/A')}")
                    print(f"     类型: {order.get('ordType', 'N/A')}")
                    print(f"     数量: {order.get('sz', 'N/A')}")
                    print(f"     价格: {order.get('px', 'N/A')} USDT")
                    print(f"     状态: {order.get('state', 'N/A')}")
            else:
                print("\n3. 未成交订单: 无")
            
            # 获取最近的历史订单
            history_orders = await client.get_order_history(inst_type="SPOT", limit=5)
            if history_orders:
                print("\n4. 最近历史订单:")
                for order in history_orders[:5]:  # 只显示最近5个
                    print(f"   - 订单ID: {order.get('ordId', 'N/A')}")
                    print(f"     产品: {order.get('instId', 'N/A')}")
                    print(f"     方向: {order.get('side', 'N/A')}")
                    print(f"     类型: {order.get('ordType', 'N/A')}")
                    print(f"     数量: {order.get('sz', 'N/A')}")
                    print(f"     价格: {order.get('px', 'N/A')} USDT")
                    print(f"     状态: {order.get('state', 'N/A')}")
                    print(f"     时间: {order.get('cTime', 'N/A')}")
            else:
                print("\n4. 最近历史订单: 无")
            
            print("\n" + "="*50)
            print("等待下一次更新...")
            print("="*50)
            
            # 每5秒更新一次
            await asyncio.sleep(5)
    except KeyboardInterrupt:
        print("\n程序已停止")
    finally:
        await client.close()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(realtime_account_info())
    loop.close()