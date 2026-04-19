from core.api.exchange_manager import exchange_manager
import asyncio

async def get_order_info():
    client = exchange_manager.get_exchange('okx')
    order1 = await client.get_order_info(inst_id='BTC-USDT', ord_id='3457923350112165888')
    order2 = await client.get_order_info(inst_id='BTC-USDT', ord_id='3457923431146119168')
    print('Order 1:', order1)
    print('Order 2:', order2)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(get_order_info())