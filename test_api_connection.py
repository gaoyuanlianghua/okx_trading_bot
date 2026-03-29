import time
from okx_api_client import OKXAPIClient
from services.market_data.market_data_service import MarketDataService
from services.order_management.order_manager import OrderManager

# 测试API连接
def test_api_connection():
    print("=== 测试API连接 ===")
    try:
        # 创建API客户端
        api_client = OKXAPIClient()
        print("✓ API客户端创建成功")
        
        # 测试服务器时间
        server_time = api_client.get_server_time()
        if server_time:
            print(f"✓ 服务器时间获取成功: {server_time}")
        else:
            print("✗ 服务器时间获取失败")
        
        # 测试市场数据
        market_service = MarketDataService(api_client=api_client)
        print("✓ 市场数据服务创建成功")
        
        # 测试获取行情
        ticker = market_service.get_real_time_ticker('BTC-USDT-SWAP')
        if ticker:
            print(f"✓ 行情数据获取成功: 最新价格: {ticker.get('last')}")
        else:
            print("✗ 行情数据获取失败")
        
        # 测试获取订单簿
        order_book = market_service.get_order_book('BTC-USDT-SWAP', 5)
        if order_book:
            print(f"✓ 订单簿数据获取成功: 买一: {order_book.get('bids', [[0, 0]])[0][0]}, 卖一: {order_book.get('asks', [[0, 0]])[0][0]}")
        else:
            print("✗ 订单簿数据获取失败")
        
        # 测试获取K线数据
        candles = market_service.get_candlesticks('BTC-USDT-SWAP', '1m', 10)
        if candles:
            print(f"✓ K线数据获取成功: 最近收盘价: {candles[-1].get('close')}")
        else:
            print("✗ K线数据获取失败")
        
        # 测试订单管理
        order_manager = OrderManager(api_client=api_client)
        print("✓ 订单管理服务创建成功")
        
        # 测试获取未成交订单
        pending_orders = order_manager.get_pending_orders('BTC-USDT-SWAP')
        print(f"✓ 未成交订单获取成功: {len(pending_orders)} 个订单")
        
        print("\n=== 测试完成 ===")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")

if __name__ == "__main__":
    test_api_connection()
