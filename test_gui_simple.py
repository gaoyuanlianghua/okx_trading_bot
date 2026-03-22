import sys
from PyQt5.QtWidgets import QApplication
from trading_gui_simple import TradingGUI

# 创建QApplication实例
app = QApplication(sys.argv)

# 创建一个简单的配置字典
config = {
    "api": {
        "api_key": "",
        "api_secret": "",
        "passphrase": "",
        "is_test": True,
        "api_url": "https://www.okx.com",
        "timeout": 30,
        "is_logged_in": False
    },
    "market_data": {
        "update_interval": 10
    }
}

# 创建一个简单的trading_bot对象
class MockTradingBot:
    def get_agent(self, agent_id):
        return None
    
    def register_strategy(self, strategy_class):
        return True

trading_bot = MockTradingBot()

# 尝试创建TradingGUI实例
print("Creating TradingGUI instance...")
try:
    gui = TradingGUI(config, trading_bot)
    print("TradingGUI instance created successfully!")
    print("Methods in TradingGUI class:")
    for method in dir(gui):
        if method.startswith('init_'):
            print(f"  - {method}")
except Exception as e:
    print(f"Error creating TradingGUI instance: {e}")
    import traceback
    traceback.print_exc()

# 运行应用程序事件循环
# app.exec_()