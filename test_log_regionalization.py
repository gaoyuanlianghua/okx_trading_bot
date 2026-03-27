#!/usr/bin/env python3
"""
测试日志区域化功能
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 初始化日志配置
from commons.logger_config import global_logger_config

# 导入服务
try:
    from services.market_data.market_data_service import get_market_data_service
    from services.order_management.order_manager import get_order_manager
    from services.risk_management.risk_manager import get_risk_manager
    from okx_api_client import OKXAPIClient
    from okx_websocket_client import OKXWebsocketClient
except ImportError as e:
    print(f"导入错误: {e}")
    sys.exit(1)


def test_log_regionalization():
    """测试日志区域化功能"""
    print("开始测试日志区域化功能...")
    
    # 测试API客户端日志
    print("\n1. 测试API客户端日志...")
    api_client = OKXAPIClient()
    
    # 测试市场数据服务日志
    print("\n2. 测试市场数据服务日志...")
    market_data_service = get_market_data_service()
    
    # 测试订单管理服务日志
    print("\n3. 测试订单管理服务日志...")
    order_manager = get_order_manager()
    
    # 测试风险管理服务日志
    print("\n4. 测试风险管理服务日志...")
    risk_manager = get_risk_manager()
    
    # 测试WebSocket客户端日志
    print("\n5. 测试WebSocket客户端日志...")
    ws_client = OKXWebsocketClient()
    
    print("\n日志区域化测试完成！请查看日志输出，确认每个日志消息都包含正确的区域标识。")


if __name__ == "__main__":
    test_log_regionalization()
