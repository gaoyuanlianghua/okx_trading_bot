import requests
import json

# 直接使用IP地址测试API连接
def test_direct_ip():
    print("=== 测试直接IP连接 ===")
    
    # 使用OKX的IP地址
    ip = "172.64.144.82"
    
    # 测试公共API端点
    print(f"测试公共API: https://{ip}/api/v5/public/time")
    try:
        headers = {
            "Host": "www.okx.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        response = requests.get(f"https://{ip}/api/v5/public/time", headers=headers, verify=False)
        print(f"响应状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"响应数据: {data}")
        else:
            print(f"请求失败: {response.text}")
    except Exception as e:
        print(f"请求异常: {e}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_direct_ip()
