#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网络调试工具，用于诊断OKX API网络连接问题
"""

import time
import socket
import ssl
import json
import asyncio
import websockets
from okx_api_client import OKXAPIClient
from okx_websocket_client import OKXWebsocketClient
from commons.health_checker import global_health_checker
from commons.logger_config import global_logger as logger

class NetworkDebugger:
    """网络调试器，用于诊断网络连接问题"""
    
    def __init__(self):
        """初始化网络调试器"""
        self.api_client = None
        self.ws_client = None
        self.debug_results = {}
        logger.info("网络调试器初始化完成")
    
    def test_dns_resolution(self, hostnames):
        """
        测试DNS解析
        
        Args:
            hostnames (list): 要测试的主机名列表
        """
        logger.info("开始测试DNS解析...")
        results = {}
        
        for hostname in hostnames:
            try:
                start_time = time.time()
                ips = socket.gethostbyname_ex(hostname)
                end_time = time.time()
                results[hostname] = {
                    'status': 'PASS',
                    'ips': ips[2],
                    'time': round((end_time - start_time) * 1000, 2),
                    'error': ''
                }
                logger.info(f"DNS解析成功: {hostname} -> {ips[2]} (耗时: {results[hostname]['time']}ms)")
            except Exception as e:
                results[hostname] = {
                    'status': 'FAIL',
                    'ips': [],
                    'time': 0,
                    'error': str(e)
                }
                logger.error(f"DNS解析失败: {hostname} - {e}")
        
        self.debug_results['dns_resolution'] = results
        return results
    
    def test_socket_connection(self, ip_addresses, port=443):
        """
        测试Socket连接
        
        Args:
            ip_addresses (list): 要测试的IP地址列表
            port (int): 端口号，默认为443
        """
        logger.info("开始测试Socket连接...")
        results = {}
        
        for ip in ip_addresses:
            try:
                start_time = time.time()
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((ip, port))
                s.close()
                end_time = time.time()
                results[ip] = {
                    'status': 'PASS',
                    'time': round((end_time - start_time) * 1000, 2),
                    'error': ''
                }
                logger.info(f"Socket连接成功: {ip}:{port} (耗时: {results[ip]['time']}ms)")
            except Exception as e:
                results[ip] = {
                    'status': 'FAIL',
                    'time': 0,
                    'error': str(e)
                }
                logger.error(f"Socket连接失败: {ip}:{port} - {e}")
        
        self.debug_results['socket_connection'] = results
        return results
    
    def test_ssl_handshake(self, ip_addresses, hostname, port=443):
        """
        测试SSL握手
        
        Args:
            ip_addresses (list): 要测试的IP地址列表
            hostname (str): 主机名（用于SNI）
            port (int): 端口号，默认为443
        """
        logger.info("开始测试SSL握手...")
        results = {}
        
        for ip in ip_addresses:
            # 跳过本地链路地址
            if ip.startswith('169.254.'):
                results[ip] = {
                    'status': 'SKIPPED',
                    'time': 0,
                    'error': '本地链路地址，跳过测试'
                }
                logger.info(f"跳过SSL握手测试: {ip}:{port} (本地链路地址)")
                continue
            
            try:
                start_time = time.time()
                context = ssl.create_default_context()
                context.check_hostname = True
                context.verify_mode = ssl.CERT_REQUIRED
                
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((ip, port))
                
                # 尝试SSL握手
                try:
                    ssl_sock = context.wrap_socket(s, server_hostname=hostname)
                    ssl_sock.close()
                    s.close()
                    
                    end_time = time.time()
                    results[ip] = {
                        'status': 'PASS',
                        'time': round((end_time - start_time) * 1000, 2),
                        'error': ''
                    }
                    logger.info(f"SSL握手成功: {ip}:{port} (耗时: {results[ip]['time']}ms)")
                except ssl.SSLError as e:
                    # SSL握手失败，可能是网络环境问题
                    s.close()
                    results[ip] = {
                        'status': 'FAIL',
                        'time': 0,
                        'error': f'SSL错误: {str(e)}'
                    }
                    logger.warning(f"SSL握手失败: {ip}:{port} - {e} (可能是网络环境限制)")
                except Exception as e:
                    # 其他错误
                    s.close()
                    results[ip] = {
                        'status': 'FAIL',
                        'time': 0,
                        'error': str(e)
                    }
                    logger.error(f"SSL握手失败: {ip}:{port} - {e}")
            except socket.timeout:
                results[ip] = {
                    'status': 'FAIL',
                    'time': 0,
                    'error': '连接超时'
                }
                logger.warning(f"SSL握手失败: {ip}:{port} - 连接超时")
            except Exception as e:
                results[ip] = {
                    'status': 'FAIL',
                    'time': 0,
                    'error': str(e)
                }
                logger.error(f"SSL握手失败: {ip}:{port} - {e}")
        
        self.debug_results['ssl_handshake'] = results
        return results
    
    def test_api_connection(self):
        """
        测试API连接
        """
        logger.info("开始测试API连接...")
        results = {}
        
        try:
            if not self.api_client:
                self.api_client = OKXAPIClient()
            
            start_time = time.time()
            server_time = self.api_client.get_server_time()
            end_time = time.time()
            
            if server_time:
                results['api_connection'] = {
                    'status': 'PASS',
                    'time': round((end_time - start_time) * 1000, 2),
                    'data': server_time,
                    'error': ''
                }
                logger.info(f"API连接成功 (耗时: {results['api_connection']['time']}ms)")
            else:
                results['api_connection'] = {
                    'status': 'FAIL',
                    'time': 0,
                    'data': None,
                    'error': 'API响应为空'
                }
                logger.error("API连接失败: 响应为空")
        except Exception as e:
            results['api_connection'] = {
                'status': 'FAIL',
                'time': 0,
                'data': None,
                'error': str(e)
            }
            logger.error(f"API连接失败: {e}")
        
        self.debug_results['api_connection'] = results
        return results
    
    async def test_websocket_connection(self, url, hostname):
        """
        测试WebSocket连接
        
        Args:
            url (str): WebSocket URL
            hostname (str): 主机名（用于SNI）
        """
        logger.info(f"开始测试WebSocket连接: {url}")
        results = {}
        
        try:
            # 创建SSL上下文
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED
            
            start_time = time.time()
            
            # 连接WebSocket
            async with websockets.connect(
                url,
                ssl=ssl_context,
                server_hostname=hostname,
                open_timeout=10.0,
                ping_timeout=5.0
            ) as ws:
                # 发送ping
                await ws.send(json.dumps({"event": "ping"}))
                logger.info("发送WebSocket ping")
                
                # 等待pong
                pong_response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                pong_data = json.loads(pong_response)
                
                end_time = time.time()
                
                if pong_data.get("event") == "pong":
                    results['websocket_connection'] = {
                        'status': 'PASS',
                        'time': round((end_time - start_time) * 1000, 2),
                        'error': ''
                    }
                    logger.info(f"WebSocket连接成功 (耗时: {results['websocket_connection']['time']}ms)")
                else:
                    results['websocket_connection'] = {
                        'status': 'FAIL',
                        'time': 0,
                        'error': '未收到pong响应'
                    }
                    logger.error("WebSocket连接失败: 未收到pong响应")
        except Exception as e:
            results['websocket_connection'] = {
                'status': 'FAIL',
                'time': 0,
                'error': str(e)
            }
            logger.error(f"WebSocket连接失败: {e}")
        
        self.debug_results['websocket_connection'] = results
        return results
    
    def test_health_check(self):
        """
        测试健康检查
        """
        logger.info("开始测试健康检查...")
        
        # 启动健康检查
        global_health_checker.start()
        
        # 等待健康检查完成
        time.sleep(5)
        
        # 获取健康状态
        health_status = global_health_checker.get_health_status()
        
        # 停止健康检查
        global_health_checker.stop()
        
        self.debug_results['health_check'] = health_status
        logger.info(f"健康检查结果: {health_status['overall']}")
        for check_name, check_result in health_status['checks'].items():
            logger.info(f"  {check_name}: {check_result['status']} - {check_result['message']}")
        
        return health_status
    
    def run_full_debug(self):
        """
        运行完整的网络调试
        """
        logger.info("开始完整网络调试...")
        
        # 1. 测试DNS解析
        hostnames = ['www.okx.com', 'ws.okx.com', 'okx.com']
        self.test_dns_resolution(hostnames)
        
        # 2. 提取IP地址进行测试
        ip_addresses = []
        if 'dns_resolution' in self.debug_results:
            for hostname, result in self.debug_results['dns_resolution'].items():
                if result['status'] == 'PASS':
                    ip_addresses.extend(result['ips'])
        
        # 去重
        ip_addresses = list(set(ip_addresses))
        
        if ip_addresses:
            # 3. 测试Socket连接
            self.test_socket_connection(ip_addresses)
            
            # 4. 测试SSL握手
            self.test_ssl_handshake(ip_addresses, 'www.okx.com')
        
        # 5. 测试API连接
        self.test_api_connection()
        
        # 6. 测试WebSocket连接
        ws_url = "wss://ws.okx.com:8443/ws/v5/public"
        asyncio.run(self.test_websocket_connection(ws_url, 'ws.okx.com'))
        
        # 7. 测试健康检查
        self.test_health_check()
        
        # 生成调试报告
        self.generate_report()
    
    def generate_report(self):
        """
        生成调试报告
        """
        logger.info("\n=== 网络调试报告 ===")
        
        # DNS解析报告
        if 'dns_resolution' in self.debug_results:
            logger.info("\n1. DNS解析测试:")
            for hostname, result in self.debug_results['dns_resolution'].items():
                status = "✓" if result['status'] == 'PASS' else "✗"
                logger.info(f"  {status} {hostname}: {result['ips'] if result['status'] == 'PASS' else result['error']}")
        
        # Socket连接报告
        if 'socket_connection' in self.debug_results:
            logger.info("\n2. Socket连接测试:")
            for ip, result in self.debug_results['socket_connection'].items():
                status = "✓" if result['status'] == 'PASS' else "✗"
                logger.info(f"  {status} {ip}:443 - {'成功' if result['status'] == 'PASS' else result['error']}")
        
        # SSL握手报告
        if 'ssl_handshake' in self.debug_results:
            logger.info("\n3. SSL握手测试:")
            for ip, result in self.debug_results['ssl_handshake'].items():
                status = "✓" if result['status'] == 'PASS' else "✗"
                logger.info(f"  {status} {ip}:443 - {'成功' if result['status'] == 'PASS' else result['error']}")
        
        # API连接报告
        if 'api_connection' in self.debug_results:
            result = self.debug_results['api_connection']['api_connection']
            status = "✓" if result['status'] == 'PASS' else "✗"
            logger.info("\n4. API连接测试:")
            logger.info(f"  {status} API连接 - {'成功' if result['status'] == 'PASS' else result['error']}")
        
        # WebSocket连接报告
        if 'websocket_connection' in self.debug_results:
            result = self.debug_results['websocket_connection']['websocket_connection']
            status = "✓" if result['status'] == 'PASS' else "✗"
            logger.info("\n5. WebSocket连接测试:")
            logger.info(f"  {status} WebSocket连接 - {'成功' if result['status'] == 'PASS' else result['error']}")
        
        # 健康检查报告
        if 'health_check' in self.debug_results:
            health_status = self.debug_results['health_check']
            logger.info("\n6. 健康检查测试:")
            logger.info(f"  整体状态: {health_status['overall']}")
            for check_name, check_result in health_status['checks'].items():
                status = "✓" if check_result['status'] == 'PASS' else "✗"
                logger.info(f"  {status} {check_name}: {check_result['message']}")
        
        # 总结
        logger.info("\n=== 调试总结 ===")
        issues = []
        
        if 'dns_resolution' in self.debug_results:
            for hostname, result in self.debug_results['dns_resolution'].items():
                if result['status'] == 'FAIL':
                    issues.append(f"DNS解析失败: {hostname}")
        
        if 'socket_connection' in self.debug_results:
            for ip, result in self.debug_results['socket_connection'].items():
                if result['status'] == 'FAIL':
                    issues.append(f"Socket连接失败: {ip}:443")
        
        if 'ssl_handshake' in self.debug_results:
            for ip, result in self.debug_results['ssl_handshake'].items():
                if result['status'] == 'FAIL':
                    issues.append(f"SSL握手失败: {ip}:443")
        
        if 'api_connection' in self.debug_results:
            result = self.debug_results['api_connection']['api_connection']
            if result['status'] == 'FAIL':
                issues.append(f"API连接失败: {result['error']}")
        
        if 'websocket_connection' in self.debug_results:
            result = self.debug_results['websocket_connection']['websocket_connection']
            if result['status'] == 'FAIL':
                issues.append(f"WebSocket连接失败: {result['error']}")
        
        if issues:
            logger.error("发现以下网络问题:")
            for issue in issues:
                logger.error(f"  - {issue}")
        else:
            logger.info("未发现网络问题，所有测试通过！")
        
        logger.info("=== 调试结束 ===")

if __name__ == "__main__":
    debugger = NetworkDebugger()
    debugger.run_full_debug()
