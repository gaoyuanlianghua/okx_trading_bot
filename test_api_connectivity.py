import requests
import json
import time
import socket
import ssl

# 从配置管理器读取API配置
def load_config():
    try:
        from commons.config_manager import global_config_manager
        config = global_config_manager.get_config()
        return config['api']
    except Exception as e:
        # 如果配置管理器不可用，使用默认配置
        return {
            'api_key': '-1',
            'api_secret': '-1',
            'passphrase': '-1',
            'is_test': False,
            'api_url': 'https://www.okx.com',
            'timeout': 30,
            'api_ips': [],
            'ws_ips': []
        }

def test_port_connectivity(ip, port, timeout=5):
    """测试端口连通性"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip, port))
        s.close()
        return True
    except Exception as e:
        return False

def test_ssl_certificate(ip, port, server_name):
    """测试SSL证书"""
    try:
        context = ssl.create_default_context()
        with socket.create_connection((ip, port), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=server_name) as ssock:
                cert = ssock.getpeercert()
                return True, cert
    except Exception as e:
        return False, str(e)

def test_api_connection():
    """测试API连通性"""
    config = load_config()
    
    print(f"测试配置:")
    print(f"  环境: {'主网' if not config['is_test'] else '测试网'}")
    print(f"  API地址: {config['api_url']}")
    print(f"  超时时间: {config['timeout']}秒")
    print(f"  API IP列表: {', '.join(config.get('api_ips', []))}")
    print(f"  WebSocket IP列表: {', '.join(config.get('ws_ips', []))}")
    
    # 测试1: 端口连通性检测
    print("\n=== 测试1: 端口连通性检测 ===")
    test_ips = config.get('api_ips', [])[:3]  # 测试前3个IP
    if not test_ips:
        # 从API URL提取IP
        from urllib.parse import urlparse
        parsed = urlparse(config['api_url'])
        test_ips = [socket.gethostbyname(parsed.hostname)]
    
    for ip in test_ips:
        # 测试HTTP端口
        http_ok = test_port_connectivity(ip, 443)
        print(f"  {ip}:443 (HTTPS): {'✅ 可达' if http_ok else '❌ 不可达'}")
        
        # 测试WebSocket端口
        ws_ok = test_port_connectivity(ip, 8443)
        print(f"  {ip}:8443 (WebSocket): {'✅ 可达' if ws_ok else '❌ 不可达'}")
    
    # 测试2: SSL证书检测
    print("\n=== 测试2: SSL证书检测 ===")
    server_name = "www.okx.com" if not config['is_test'] else "testnet.okx.com"
    for ip in test_ips[:2]:  # 测试前2个IP
        ssl_ok, cert = test_ssl_certificate(ip, 443, server_name)
        if ssl_ok:
            print(f"  {ip}:443 SSL证书: ✅ 有效")
        else:
            print(f"  {ip}:443 SSL证书: ❌ 无效 - {cert}")
    
    headers = {
        "OK-ACCESS-KEY": config['api_key'],
        "OK-ACCESS-PASSPHRASE": config['passphrase'],
        "Content-Type": "application/json"
    }
    
    # 测试3: 公共API - 获取服务器时间
    print("\n=== 测试3: 公共API - 获取服务器时间 ===")
    try:
        resp = requests.get(f"{config['api_url']}/api/v5/public/time", headers=headers, timeout=config['timeout'])
        if resp.status_code == 200:
            time_data = resp.json()
            if time_data['code'] == '0':
                print(f"  ✅ 成功: 服务器时间 - {time_data['data'][0]['ts']} (UTC)")
                server_time = int(time_data['data'][0]['ts'])
                local_time = int(time.time() * 1000)  # 毫秒
                time_diff = abs(server_time - local_time)
                print(f"  ⏰ 本地时间与服务器时间差: {time_diff}ms")
            else:
                print(f"  ❌ 失败: {time_data['msg']}")
        else:
            print(f"  ❌ 失败: HTTP {resp.status_code}, 响应: {resp.text}")
    except requests.exceptions.ConnectionError as e:
        print(f"  ❌ 连接错误: {e}")
        print(f"  💡 可能原因: 网络拦截、防火墙限制或OKX服务端问题")
    except Exception as e:
        print(f"  ❌ 未知错误: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试4: 公共API - 获取行情数据
    print("\n=== 测试4: 公共API - 获取行情数据 ===")
    try:
        resp = requests.get(f"{config['api_url']}/api/v5/market/ticker?instId=BTC-USDT", headers=headers, timeout=config['timeout'])
        if resp.status_code == 200:
            ticker_data = resp.json()
            if ticker_data['code'] == '0':
                print(f"  ✅ 成功: 获取BTC-USDT行情数据")
                print(f"  💰 最新价格: {ticker_data['data'][0]['last']} USDT")
            else:
                print(f"  ❌ 失败: {ticker_data['msg']}")
        else:
            print(f"  ❌ 失败: HTTP {resp.status_code}, 响应: {resp.text}")
    except requests.exceptions.ConnectionError as e:
        print(f"  ❌ 连接错误: {e}")
    except Exception as e:
        print(f"  ❌ 未知错误: {e}")
    
    # 测试5: 私有API - 获取账户信息
    print("\n=== 测试5: 私有API - 获取账户信息 ===")
    try:
        # 生成签名
        import hmac
        import base64
        
        timestamp = str(int(time.time()))
        method = 'GET'
        request_path = '/api/v5/account/info'
        message = timestamp + method + request_path
        
        mac = hmac.new(bytes(config['api_secret'], encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
        sign = base64.b64encode(mac.digest()).decode()
        
        # 添加签名和时间戳到请求头
        headers['OK-ACCESS-TIMESTAMP'] = timestamp
        headers['OK-ACCESS-SIGN'] = sign
        
        resp = requests.get(f"{config['api_url']}{request_path}", headers=headers, timeout=config['timeout'])
        if resp.status_code == 200:
            account_data = resp.json()
            if account_data['code'] == '0':
                print(f"  ✅ 成功: 账户信息获取成功")
                print(f"  📊 账户状态: {account_data['data'][0]['acctLv']}")
                print(f"  💰 账户余额: {account_data['data'][0]['totalEq']} {account_data['data'][0]['ccy']}")
            else:
                print(f"  ❌ 失败: {account_data['msg']} (错误码: {account_data['code']})")
                if account_data['code'] == '401':
                    print(f"  💡 可能原因: API密钥错误或过期")
                elif account_data['code'] == '403':
                    print(f"  💡 可能原因: API权限不足")
        else:
            print(f"  ❌ 失败: HTTP {resp.status_code}, 响应: {resp.text}")
    except requests.exceptions.ConnectionError as e:
        print(f"  ❌ 连接错误: {e}")
        print(f"  💡 可能原因: 网络拦截或OKX服务端限制")
    except Exception as e:
        print(f"  ❌ 未知错误: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试6: WebSocket连接测试
    print("\n=== 测试6: WebSocket连接测试 ===")
    ws_server = "ws.okx.com" if not config['is_test'] else "wspap.okx.com"
    print(f"  WebSocket服务器: {ws_server}")
    print(f"  WebSocket端口: 8443")
    print("  💡 提示: 完整WebSocket测试请运行okx_websocket_client.py")
    
    print("\n=== 测试完成 ===")
    print("\n问题排查建议:")
    print("1. 如果端口不可达: 检查防火墙设置或网络环境")
    print("2. 如果SSL证书无效: 可能是测试网证书问题，可临时放宽SSL验证")
    print("3. 如果API连接失败: 检查API密钥有效性或OKX服务状态")
    print("4. 如果WebSocket连接重置: 可能是网络层拦截或SSL握手失败")
    print("5. 测试网不稳定时: 切换到主网环境")

if __name__ == "__main__":
    test_api_connection()