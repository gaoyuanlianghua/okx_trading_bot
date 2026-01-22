import socket
import ssl
import time

def test_port(ip, port, timeout=5):
    """测试指定IP和端口的连通性"""
    results = {
        'ip': ip,
        'port': port,
        'tcp_reachable': False,
        'tcp_error': '',
        'ssl_connected': False,
        'ssl_error': '',
        'ssl_cert_valid': False,
        'cert_details': ''
    }
    
    try:
        # 测试TCP连接
        print(f"\n测试 {ip}:{port} TCP连接...")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip, port))
        results['tcp_reachable'] = True
        print(f"✅ {ip}:{port} TCP连接成功")
        
        # 测试SSL握手
        print(f"测试 {ip}:{port} SSL握手...")
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        ssock = context.wrap_socket(s, server_hostname='www.okx.com')
        results['ssl_connected'] = True
        print(f"✅ {ip}:{port} SSL握手成功")
        
        # 测试SSL证书
        print(f"测试 {ip}:{port} SSL证书...")
        cert = ssock.getpeercert()
        if cert:
            results['ssl_cert_valid'] = True
            results['cert_details'] = f"主题: {cert.get('subject')}, 颁发者: {cert.get('issuer')}"
            print(f"✅ {ip}:{port} SSL证书有效")
        else:
            print(f"⚠️  {ip}:{port} 无法获取证书信息")
        
        ssock.close()
    except ssl.SSLError as e:
        results['ssl_error'] = f"SSL错误: {e}"
        print(f"❌ {ip}:{port} SSL错误: {e}")
    except socket.timeout:
        results['tcp_error'] = "连接超时"
        print(f"❌ {ip}:{port} 连接超时")
    except ConnectionRefusedError:
        results['tcp_error'] = "连接被拒绝"
        print(f"❌ {ip}:{port} 连接被拒绝")
    except ConnectionResetError:
        results['tcp_error'] = "连接被重置"
        print(f"❌ {ip}:{port} 连接被重置")
    except Exception as e:
        results['tcp_error'] = f"其他错误: {e}"
        print(f"❌ {ip}:{port} 其他错误: {e}")
    finally:
        try:
            s.close()
        except:
            pass
    
    return results

def main():
    print("=== 端口限制检测报告 ===")
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 测试OKX主网IP和端口
    okx_ips = [
        "172.64.144.82",
        "16.163.28.222", 
        "104.18.43.174"
    ]
    
    test_ports = [443, 8443]
    
    all_results = []
    
    for ip in okx_ips:
        for port in test_ports:
            result = test_port(ip, port)
            all_results.append(result)
    
    # 生成总结报告
    print("\n" + "="*50)
    print("=== 端口限制总结 ===")
    print("="*50)
    
    for result in all_results:
        status = "✅ 正常" if result['tcp_reachable'] and result['ssl_connected'] else "❌ 受限"
        print(f"{result['ip']}:{result['port']} - {status}")
        if not result['tcp_reachable']:
            print(f"   原因: {result['tcp_error']}")
        elif not result['ssl_connected']:
            print(f"   原因: {result['ssl_error']}")
    
    # 统计受限端口
    restricted_ports = []
    for result in all_results:
        if not result['tcp_reachable'] or not result['ssl_connected']:
            restricted_ports.append(f"{result['ip']}:{result['port']}")
    
    print("\n" + "="*50)
    print(f"=== 最终结论 ===")
    print("="*50)
    
    if restricted_ports:
        print(f"检测到 {len(restricted_ports)} 个受限端口:")
        for port in restricted_ports:
            print(f"   - {port}")
        print("\n可能的原因:")
        print("1. 网络防火墙限制")
        print("2. 网络运营商限制")
        print("3. SSL检查/拦截")
        print("4. OKX服务器端限制")
        print("5. 网络环境不稳定")
    else:
        print("✅ 所有测试端口均正常")

if __name__ == "__main__":
    main()