#!/usr/bin/env python3
"""
DPI拦截类型检测脚本
用于自动判断DPI拦截类型：SSL握手阶段拦截还是应用层流量拦截

使用方法：
python detect_dpi_interception.py
或
python detect_dpi_interception.py --target www.okx.com --port 443
"""

import socket
import ssl
import sys
import argparse
import time
from urllib.parse import urlparse

# 配置日志输出
class Logger:
    def info(self, msg):
        print(f"[INFO] {msg}")
    
    def success(self, msg):
        print(f"[SUCCESS] {msg}")
    
    def warning(self, msg):
        print(f"[WARNING] {msg}")
    
    def error(self, msg):
        print(f"[ERROR] {msg}")
    
    def critical(self, msg):
        print(f"[CRITICAL] {msg}")

logger = Logger()

class DPIInterceptorDetector:
    def __init__(self, target, port=443, timeout=10):
        self.target = target
        self.port = port
        self.timeout = timeout
        self.results = {
            "tcp_connection": None,
            "ssl_handshake": None,
            "application_layer": None,
            "interception_type": None,
            "details": []
        }
    
    def test_tcp_connection(self):
        """测试TCP三次握手是否成功"""
        logger.info(f"测试TCP连接到 {self.target}:{self.port}...")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            
            start_time = time.time()
            sock.connect((self.target, self.port))
            end_time = time.time()
            
            connection_time = (end_time - start_time) * 1000
            logger.success(f"TCP连接成功！耗时 {connection_time:.2f} ms")
            
            self.results["tcp_connection"] = True
            self.results["details"].append(f"TCP连接成功，耗时 {connection_time:.2f} ms")
            
            return sock
        
        except socket.timeout:
            logger.error("TCP连接超时")
            self.results["tcp_connection"] = False
            self.results["details"].append("TCP连接超时")
            return None
        
        except ConnectionRefusedError:
            logger.error(f"连接被拒绝，请检查 {self.target}:{self.port} 是否可访问")
            self.results["tcp_connection"] = False
            self.results["details"].append(f"连接被拒绝，{self.target}:{self.port} 不可访问")
            return None
        
        except Exception as e:
            logger.error(f"TCP连接失败: {e}")
            self.results["tcp_connection"] = False
            self.results["details"].append(f"TCP连接失败: {str(e)}")
            return None
    
    def test_ssl_handshake(self, sock):
        """测试SSL握手是否成功"""
        if not sock:
            return False
        
        logger.info("测试SSL握手...")
        
        try:
            # 创建SSL上下文
            context = ssl.create_default_context()
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
            
            start_time = time.time()
            ssl_sock = context.wrap_socket(sock, server_hostname=self.target)
            end_time = time.time()
            
            handshake_time = (end_time - start_time) * 1000
            logger.success(f"SSL握手成功！耗时 {handshake_time:.2f} ms")
            
            # 获取SSL连接信息
            ssl_version = ssl_sock.version()
            cipher = ssl_sock.cipher()
            logger.info(f"SSL版本: {ssl_version}, 加密套件: {cipher[0]}")
            
            self.results["ssl_handshake"] = True
            self.results["details"].append(f"SSL握手成功，耗时 {handshake_time:.2f} ms，版本: {ssl_version}, 加密套件: {cipher[0]}")
            
            return ssl_sock
        
        except ssl.SSLError as e:
            logger.error(f"SSL握手失败: {e}")
            self.results["ssl_handshake"] = False
            self.results["details"].append(f"SSL握手失败: {str(e)}")
            
            # 关闭原始socket
            try:
                sock.close()
            except:
                pass
            
            return None
        
        except socket.timeout:
            logger.error("SSL握手超时")
            self.results["ssl_handshake"] = False
            self.results["details"].append("SSL握手超时")
            
            # 关闭原始socket
            try:
                sock.close()
            except:
                pass
            
            return None
        
        except Exception as e:
            logger.error(f"SSL握手过程中发生错误: {e}")
            self.results["ssl_handshake"] = False
            self.results["details"].append(f"SSL握手过程中发生错误: {str(e)}")
            
            # 关闭原始socket
            try:
                sock.close()
            except:
                pass
            
            return None
    
    def test_application_layer(self, ssl_sock):
        """测试应用层数据传输是否成功"""
        if not ssl_sock:
            return False
        
        logger.info("测试应用层数据传输...")
        
        try:
            # 发送简单的HTTP GET请求
            http_request = f"GET / HTTP/1.1\r\n"
            http_request += f"Host: {self.target}\r\n"
            http_request += "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n"
            http_request += "Accept: */*\r\n"
            http_request += "Connection: close\r\n"
            http_request += "\r\n"
            
            start_time = time.time()
            ssl_sock.sendall(http_request.encode())
            
            # 接收响应
            response = b""
            ssl_sock.settimeout(5)
            
            try:
                while True:
                    data = ssl_sock.recv(4096)
                    if not data:
                        break
                    response += data
            except socket.timeout:
                # 超时但已收到部分数据，视为成功
                pass
            
            end_time = time.time()
            
            if response:
                # 解析HTTP响应
                response_str = response.decode('utf-8', errors='ignore')
                first_line = response_str.split('\n')[0]
                logger.success(f"应用层数据传输成功！收到响应: {first_line}")
                
                transfer_time = (end_time - start_time) * 1000
                logger.info(f"数据传输耗时: {transfer_time:.2f} ms，响应大小: {len(response)} 字节")
                
                self.results["application_layer"] = True
                self.results["details"].append(f"应用层数据传输成功，响应: {first_line}")
                return True
            else:
                logger.error("未收到应用层响应")
                self.results["application_layer"] = False
                self.results["details"].append("未收到应用层响应")
                return False
        
        except ConnectionResetError:
            logger.error("连接被重置，应用层流量可能被DPI拦截")
            self.results["application_layer"] = False
            self.results["details"].append("连接被重置，应用层流量可能被DPI拦截")
            return False
        
        except socket.timeout:
            logger.error("应用层数据传输超时")
            self.results["application_layer"] = False
            self.results["details"].append("应用层数据传输超时")
            return False
        
        except Exception as e:
            logger.error(f"应用层数据传输失败: {e}")
            self.results["application_layer"] = False
            self.results["details"].append(f"应用层数据传输失败: {str(e)}")
            return False
        
        finally:
            # 关闭SSL socket
            try:
                ssl_sock.close()
            except:
                pass
    
    def detect_interception_type(self):
        """执行完整的DPI拦截类型检测"""
        logger.info(f"开始DPI拦截类型检测，目标: {self.target}:{self.port}")
        logger.info("=" * 60)
        
        # 1. 测试TCP连接
        sock = self.test_tcp_connection()
        
        if not self.results["tcp_connection"]:
            logger.critical("TCP连接失败，无法进行后续测试")
            self.results["interception_type"] = "TCP连接失败"
            return self.results
        
        # 2. 测试SSL握手
        ssl_sock = self.test_ssl_handshake(sock)
        
        if not self.results["ssl_handshake"]:
            logger.critical("SSL握手失败，DPI在SSL握手阶段拦截")
            self.results["interception_type"] = "SSL握手阶段拦截"
            return self.results
        
        # 3. 测试应用层数据传输
        app_layer_success = self.test_application_layer(ssl_sock)
        
        if not app_layer_success:
            logger.critical("应用层数据传输失败，DPI在应用层拦截")
            self.results["interception_type"] = "应用层流量拦截"
        else:
            logger.success("所有测试通过，未检测到DPI拦截")
            self.results["interception_type"] = "无DPI拦截"
        
        return self.results
    
    def print_report(self):
        """打印检测报告"""
        logger.info("\n" + "=" * 60)
        logger.info("DPI拦截类型检测报告")
        logger.info("=" * 60)
        
        logger.info(f"目标: {self.target}:{self.port}")
        logger.info(f"检测时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"DPI拦截类型: {self.results['interception_type']}")
        
        logger.info("\n测试详情:")
        for detail in self.results["details"]:
            logger.info(f"  - {detail}")
        
        logger.info("\n" + "=" * 60)
        logger.info("解决方案建议")
        logger.info("=" * 60)
        
        if self.results["interception_type"] == "TCP连接失败":
            logger.info("1. 检查目标服务器是否可访问")
            logger.info("2. 检查本地网络连接是否正常")
            logger.info("3. 检查防火墙设置是否阻止了连接")
        
        elif self.results["interception_type"] == "SSL握手阶段拦截":
            logger.info("1. 推荐使用Socks5代理中转流量")
            logger.info("2. 修改TLS指纹，伪装流量特征")
            logger.info("3. 尝试使用不同的SSL版本和加密套件")
            logger.info("4. 使用VPN服务绕开DPI拦截")
        
        elif self.results["interception_type"] == "应用层流量拦截":
            logger.info("1. 推荐使用Socks5代理中转流量")
            logger.info("2. 伪装成浏览器流量，添加完整的浏览器请求头")
            logger.info("3. 使用加密协议（如HTTPS）传输数据")
            logger.info("4. 考虑使用WebSocket加密扩展")
        
        elif self.results["interception_type"] == "无DPI拦截":
            logger.info("1. 当前网络环境未检测到DPI拦截")
            logger.info("2. 建议定期检测，以应对可能的DPI策略变化")
        
        logger.info("\n" + "=" * 60)
        logger.info("检测完成")
        logger.info("=" * 60)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="DPI拦截类型检测脚本")
    parser.add_argument("--target", type=str, default="www.okx.com", help="目标域名或IP地址")
    parser.add_argument("--port", type=int, default=443, help="目标端口")
    parser.add_argument("--timeout", type=int, default=10, help="连接超时时间（秒）")
    
    args = parser.parse_args()
    
    # 解析目标URL
    if args.target.startswith(('http://', 'https://')):
        parsed_url = urlparse(args.target)
        target = parsed_url.netloc.split(':')[0]
        port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
    else:
        target = args.target
        port = args.port
    
    # 创建检测器实例
    detector = DPIInterceptorDetector(target, port, args.timeout)
    
    # 执行检测
    detector.detect_interception_type()
    
    # 打印报告
    detector.print_report()

if __name__ == "__main__":
    main()