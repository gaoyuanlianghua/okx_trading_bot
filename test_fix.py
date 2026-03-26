from services.risk_management.risk_manager import RiskManager
from okx_api_client import OKXAPIClient

# 创建一个模拟的API客户端
mock_client = OKXAPIClient()

# 初始化风险管理服务
rm = RiskManager(api_client=mock_client)
print('RiskManager initialized successfully')

# 测试get_pending_orders方法
print('Testing get_pending_orders method...')
try:
    result = rm.get_pending_orders('BTC-USDT-SWAP')
    print('Method called successfully')
    print(f'Result: {result}')
except AttributeError as e:
    print(f'AttributeError: {e}')
except Exception as e:
    print(f'Other error: {e}')
