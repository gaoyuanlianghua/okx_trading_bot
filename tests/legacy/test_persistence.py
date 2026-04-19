"""
测试数据持久化功能
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.utils.persistence import persistence_manager
from core.agents.order_agent import OrderAgent
from core.agents.base_agent import AgentConfig


def test_persistence():
    """测试数据持久化功能"""
    print("=== 测试数据持久化功能 ===")
    
    # 测试1: 直接测试PersistenceManager
    print("\n1. 测试PersistenceManager:")
    test_data = {
        "test_key": "test_value",
        "test_number": 123,
        "test_list": [1, 2, 3],
        "test_dict": {"a": 1, "b": 2}
    }
    
    # 保存测试数据
    save_result = persistence_manager.save_data("test_data.json", test_data)
    print(f"保存测试数据: {'成功' if save_result else '失败'}")
    
    # 加载测试数据
    loaded_data = persistence_manager.load_data("test_data.json")
    print(f"加载测试数据: {'成功' if loaded_data else '失败'}")
    if loaded_data:
        print(f"加载的数据: {loaded_data}")
    
    # 测试2: 测试OrderAgent状态保存和加载
    print("\n2. 测试OrderAgent状态保存和加载:")
    
    # 创建OrderAgent实例
    config = AgentConfig(name="TestOrderAgent")
    order_agent = OrderAgent(config, exchange_name="okx")
    
    # 设置一些测试数据
    order_agent._initial_balance = 1000.0
    order_agent._total_pnl = 100.0
    order_agent._total_fees = 10.0
    order_agent._order_count = 5
    order_agent._trade_history = [{"trade_id": "1", "side": "buy", "price": 10000.0}]
    
    # 保存状态
    order_agent.save_state_now()
    print("保存OrderAgent状态")
    
    # 创建新的OrderAgent实例
    new_order_agent = OrderAgent(config, exchange_name="okx")
    print(f"加载后的初始权益: {new_order_agent._initial_balance}")
    print(f"加载后的总收益: {new_order_agent._total_pnl}")
    print(f"加载后的总手续费: {new_order_agent._total_fees}")
    print(f"加载后的订单数: {new_order_agent._order_count}")
    print(f"加载后的交易记录数: {len(new_order_agent._trade_history)}")
    
    # 测试3: 检查文件是否存在
    print("\n3. 检查状态文件是否存在:")
    import os
    data_dir = "./data"
    files = os.listdir(data_dir)
    print(f"数据目录中的文件: {files}")
    
    # 检查是否存在状态文件
    order_state_file = os.path.join(data_dir, "order_agent_state.json")
    coordinator_state_file = os.path.join(data_dir, "coordinator_agent_state.json")
    
    print(f"订单智能体状态文件存在: {os.path.exists(order_state_file)}")
    print(f"协调智能体状态文件存在: {os.path.exists(coordinator_state_file)}")
    
    if os.path.exists(order_state_file):
        file_size = os.path.getsize(order_state_file)
        print(f"订单智能体状态文件大小: {file_size} 字节")
    
    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    test_persistence()
