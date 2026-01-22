import sys
import socket
import ssl
import urllib3
from loguru import logger
import requests
from okx_api_client import custom_dns_resolve

# 配置日志
logger.remove()
logger.add(sys.stdout, level="DEBUG")

def debug_with_urllib3():
    """使用urllib3直接调试HTTP请求"""
    logger.info("使用urllib3直接调试HTTP请求...")
    
    try:
        # 获取OKX IP地址
        ip = custom_dns_resolve("www.okx.com")
        if not ip:
            logger.error("无法解析OKX IP地址")
            return
        
        logger.info(f"使用IP: {ip}")
        
        # 创建SSL上下文
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        
        # 创建连接池
        http = urllib3.PoolManager(
            ssl_context=context,
            headers={
                'Host': 'www.okx.com',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
                'Origin': 'https://www.okx.com'
            }
        )
        
        # 构建URL
        url = f"https://{ip}/api/v5/public/ticker?instId=BTC-USDT-SWAP"
        
        # 发送请求
        logger.info(f"发送请求到: {url}")
        response = http.request('GET', url, headers={'Host': 'www.okx.com'})
        
        logger.info(f"响应状态码: {response.status}")
        logger.info(f"响应内容: {response.data.decode('utf-8')}")
        
        return True
        
    except Exception as e:
        logger.error(f"urllib3请求失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def debug_with_requests():
    """使用requests库调试HTTP请求"""
    logger.info("使用requests库调试HTTP请求...")
    
    try:
        # 获取OKX IP地址
        ip = custom_dns_resolve("www.okx.com")
        if not ip:
            logger.error("无法解析OKX IP地址")
            return
        
        logger.info(f"使用IP: {ip}")
        
        # 构建URL
        url = f"https://{ip}/api/v5/public/ticker?instId=BTC-USDT-SWAP"
        
        # 发送请求，使用Host头
        logger.info(f"发送请求到: {url}")
        response = requests.get(
            url,
            headers={
                'Host': 'www.okx.com',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
                'Origin': 'https://www.okx.com'
            },
            verify=True
        )
        
        logger.info(f"响应状态码: {response.status_code}")
        logger.info(f"响应内容: {response.text}")
        
        return True
        
    except Exception as e:
        logger.error(f"requests请求失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def debug_with_socket():
    """使用socket直接调试SSL连接"""
    logger.info("使用socket直接调试SSL连接...")
    
    try:
        # 获取OKX IP地址
        ip = custom_dns_resolve("www.okx.com")
        if not ip:
            logger.error("无法解析OKX IP地址")
            return
        
        logger.info(f"使用IP: {ip}")
        
        # 创建socket连接
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        
        # 连接到服务器
        sock.connect((ip, 443))
        logger.info("socket连接成功")
        
        # 创建SSL上下文
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        
        # 包装socket
        ssl_sock = context.wrap_socket(sock, server_hostname='www.okx.com')
        logger.info("SSL握手成功")
        
        # 发送HTTP请求
        request = ("GET /api/v5/public/ticker?instId=BTC-USDT-SWAP HTTP/1.1\r\n" +
                   "Host: www.okx.com\r\n" +
                   "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36\r\n" +
                   "Accept: application/json, text/plain, */*\r\n" +
                   "Connection: close\r\n" +
                   "\r\n")
        
        logger.info(f"发送HTTP请求: {request}")
        ssl_sock.sendall(request.encode('utf-8'))
        
        # 接收响应
        response = b""
        while True:
            data = ssl_sock.recv(1024)
            if not data:
                break
            response += data
        
        logger.info(f"响应内容: {response.decode('utf-8')}")
        
        # 关闭连接
        ssl_sock.close()
        sock.close()
        
        return True
        
    except Exception as e:
        logger.error(f"socket请求失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    logger.info("开始HTTP调试...")
    
    # 测试1: 使用socket直接调试
    logger.info("\n=== 测试1: 使用socket直接调试 ===")
    debug_with_socket()
    
    # 测试2: 使用urllib3
    logger.info("\n=== 测试2: 使用urllib3 ===")
    debug_with_urllib3()
    
    # 测试3: 使用requests
    logger.info("\n=== 测试3: 使用requests ===")
    debug_with_requests()
    
    logger.info("HTTP调试完成")

if __name__ == "__main__":
    main()
