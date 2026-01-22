import time
from okx_api_client import OKXAPIClient

def test_network_adapter():
    """测试网络自动适配功能"""
    print("=== 测试网络自动适配功能 ===")
    
    # 创建API客户端
    client = OKXAPIClient(is_test=True)
    
    # 运行网络自动适配脚本，不自动更新配置
    print("\n1. 运行网络自动适配脚本（不更新配置）...")
    result = client.run_network_adapter(auto_update=False)
    print(f"执行结果: {'成功' if result else '失败'}")
    
    # 运行网络自动适配脚本，自动更新配置
    print("\n2. 运行网络自动适配脚本（自动更新配置）...")
    result = client.run_network_adapter(auto_update=True)
    print(f"执行结果: {'成功' if result else '失败'}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_network_adapter()
