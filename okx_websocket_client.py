import asyncio
import json
import time
import ssl
import websockets
from threading import Thread, Lock
from okx_api_client import OKXAPIClient

# 初始化日志配置
from commons.logger_config import global_logger_config

# 获取区域化日志记录器
def get_logger(region=None):
    return global_logger_config.get_logger(region=region)

# 创建默认日志记录器
logger = get_logger("WebSocket")

class OKXWebsocketClient:
    """OKX Websocket客户端，支持订阅市场数据和订单更新"""
    
    def __init__(self, api_key=None, api_secret=None, passphrase=None, is_test=False, api_ip=None, api_ips=None, ws_ip=None, ws_ips=None):
        """
        初始化OKX Websocket客户端
        
        Args:
            api_key (str): OKX API密钥
            api_secret (str): OKX API密钥密码
            passphrase (str): OKX API密钥短语
            is_test (bool): 是否使用测试网
            api_ip (str): OKX API服务器的IP地址，用于绕过DNS解析
            api_ips (list): OKX API服务器的IP地址列表，用于负载均衡和自动切换
            ws_ip (str): OKX WebSocket服务器的IP地址，用于绕过DNS解析
            ws_ips (list): OKX WebSocket服务器的IP地址列表，用于IP轮询
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.is_test = is_test
        
        # 从配置管理器获取配置
        api_config = {}
        try:
            from commons.config_manager import global_config_manager
            self.config_manager = global_config_manager
            api_config = self.config_manager.get("api", {})
            logger.info("从配置管理器加载API配置成功")
        except Exception as e:
            logger.warning(f"从配置管理器加载配置失败: {e}")
        
        # WebSocket IP轮询相关
        # 优先使用传入的参数，然后是配置管理器的配置，最后是默认值
        self.ws_ips = ws_ips or api_config.get('ws_ips', [])  # WebSocket服务器IP列表
        self.current_ws_ip_index = 0  # 当前使用的WebSocket IP索引
        
        # 如果提供了单个ws_ip，添加到ws_ips列表
        config_ws_ip = api_config.get('ws_ip')
        effective_ws_ip = ws_ip or config_ws_ip
        if effective_ws_ip and effective_ws_ip not in self.ws_ips:
            self.ws_ips.insert(0, effective_ws_ip)
        
        # 如果没有提供ws_ips，使用默认IP列表
        if not self.ws_ips:
            self.ws_ips = ["104.18.43.174", "172.64.144.82"]  # 默认IP列表
        
        # 设置当前ws_ip
        self.ws_ip = self.ws_ips[self.current_ws_ip_index]
        
        # WebSocket URL模板
        self.public_url_template = "wss://ws.okx.com:8443/ws/v5/public" if not is_test else "wss://wspap.okx.com:8443/ws/v5/public"
        self.private_url_template = "wss://ws.okx.com:8443/ws/v5/private" if not is_test else "wss://wspap.okx.com:8443/ws/v5/private"
        self.business_url_template = "wss://ws.okx.com:8443/ws/v5/business" if not is_test else "wss://wspap.okx.com:8443/ws/v5/business"
        
        # 保存原始主机名，用于SSL验证和Host头
        self.original_host = "ws.okx.com" if not is_test else "wspap.okx.com"
        
        # IP 负载均衡相关
        self.api_ips = api_ips or api_config.get('api_ips', [])
        self.current_ip_index = 0
        
        # 初始化当前URL
        self.public_url = self.public_url_template
        self.private_url = self.private_url_template
        self.business_url = self.business_url_template
        
        # 更新WebSocket URL，如果提供了ws_ip则使用直接IP连接
        self.update_websocket_urls()
        
        # 不直接导入，使用websockets的默认DNS解析
        # 因为导入会导致模块循环依赖问题
        logger.info("WebSocket客户端使用默认DNS解析")
        
        # 连接状态
        self.public_connected = False
        self.private_connected = False
        
        # WebSocket连接
        self.public_ws = None
        self.private_ws = None
        
        # 订阅的频道
        self.public_subscriptions = set()
        self.private_subscriptions = set()
        
        # 消息处理器
        self.message_handlers = {}
        
        # 锁
        self.lock = Lock()
        
        # 心跳定时器
        self.heartbeat_interval = api_config.get('ws_ping_interval', 25)  # 秒，必须小于30
        self.last_message_time = time.time()  # 最后接收消息的时间
        self.last_ping_time = 0  # 最后发送ping的时间
        self.pong_timeout = api_config.get('ws_ping_timeout', 15)  # 秒，发送ping后等待pong的超时时间
        
        # 停止标志
        self._should_stop = False
        
        # WebSocket连接配置
        self.open_timeout = api_config.get('ws_open_timeout', 20.0)  # 连接超时时间
        self.ping_timeout = api_config.get('ws_ping_timeout', 15.0)  # 心跳超时时间
        self.close_timeout = api_config.get('ws_close_timeout', 10.0)  # 关闭超时时间
        self.max_queue = api_config.get('ws_max_queue', 1000)     # 最大队列大小
        self.ping_interval = api_config.get('ws_ping_interval', 20.0) # 心跳间隔
        
        # 不使用代理配置，只保留基本的API调用功能
        self.proxy_config = {}
        self.proxy_enabled = False
        self.proxy_url = None
        self.proxy_connector = None
        logger.info("未使用代理配置，只保留基本API调用功能")
        
        # 自动重连配置
        self.base_reconnect_delay = 2  # 基础重连延迟，秒
        self.reconnect_delay = self.base_reconnect_delay  # 当前重连延迟
        self.max_reconnect_delay = 60  # 最大重连延迟，秒
        self.max_reconnect_attempts = 50  # 增加最大重连次数
        self.reconnect_attempts = 0
        self.exponential_backoff = True  # 启用指数退避
        self.backoff_factor = 1.5  # 退避因子
        
        # 连接池管理配置
        self.connection_pool = {}  # 连接池，key为连接类型（public/private/business），value为连接对象
        self.max_connections = 5  # 最大并发连接数
        self.connection_status = {  # 连接状态，key为连接类型
            'public': {'connected': False, 'ws': None, 'task': None},
            'private': {'connected': False, 'ws': None, 'task': None},
            'business': {'connected': False, 'ws': None, 'task': None}
        }
        
        # 连接质量监控
        self.connection_quality = {  # 连接质量统计
            'public': {'latency': 0, 'success_rate': 1.0, 'message_count': 0, 'error_count': 0},
            'private': {'latency': 0, 'success_rate': 1.0, 'message_count': 0, 'error_count': 0},
            'business': {'latency': 0, 'success_rate': 1.0, 'message_count': 0, 'error_count': 0}
        }
        
        # SSL配置
        self.ssl_check_hostname = True  # 是否检查主机名
        self.ssl_verify_mode = ssl.CERT_REQUIRED  # 证书验证模式
        self.ssl_min_version = ssl.TLSVersion.TLSv1_2  # 最低TLS版本
        # 允许使用TLS 1.3，提高连接兼容性
        if hasattr(ssl, 'TLSVersion') and hasattr(ssl.TLSVersion, 'TLSv1_3'):
            self.ssl_max_version = ssl.TLSVersion.TLSv1_3
            logger.info(f"WebSocket SSL配置: TLS 1.2-1.3，证书验证模式: {self.ssl_verify_mode}")
        else:
            self.ssl_max_version = ssl.TLSVersion.TLSv1_2
            logger.info(f"WebSocket SSL配置: TLS 1.2，证书验证模式: {self.ssl_verify_mode}")
        
        # IP 健康状态跟踪
        self.ip_health = {}
        for ip in self.ws_ips:
            self.ip_health[ip] = {
                'success_count': 0,
                'fail_count': 0,
                'last_attempt': 0,
                'last_success': 0,
                'available': True
            }
        
        logger.info(f"OKX Websocket客户端初始化完成，测试网: {is_test}")
        logger.info(f"公共频道URL: {self.public_url}")
        logger.info(f"私有频道URL: {self.private_url}")
        logger.info(f"API IP列表: {self.api_ips}")
        logger.info(f"WebSocket直接IP: {self.ws_ip}")
        logger.info(f"WebSocket连接超时: {self.open_timeout}秒")
        logger.info(f"WebSocket心跳间隔: {self.ping_interval}秒")
    
    def get_current_ip(self):
        """获取当前活跃的API IP地址"""
        if not self.api_ips:
            return None
        return self.api_ips[self.current_ip_index]
    
    def switch_to_next_ip(self):
        """切换到下一个IP地址"""
        if not self.api_ips:
            return None
        self.current_ip_index = (self.current_ip_index + 1) % len(self.api_ips)
        logger.info(f"切换到下一个API IP: {self.get_current_ip()}")
        self.update_websocket_urls()
        return self.get_current_ip()
    
    def is_port_reachable(self, ip, port=8443, timeout=5):
        """
        检测指定IP和端口是否可达
        
        Args:
            ip (str): 要检测的IP地址
            port (int): 要检测的端口号，默认为8443
            timeout (float): 超时时间，默认为5秒
            
        Returns:
            bool: 端口是否可达
        """
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect((ip, port))
            s.close()
            logger.info(f"端口 {ip}:{port} 可达")
            return True
        except socket.timeout:
            logger.warning(f"检测端口 {ip}:{port} 超时")
            return False
        except socket.error as e:
            logger.warning(f"检测端口 {ip}:{port} 不可达: {e}")
            return False
        except Exception as e:
            logger.error(f"检测端口 {ip}:{port} 时发生未知错误: {e}")
            return False
    
    def create_ssl_context(self):
        """
        创建自定义SSL上下文，包含TLS指纹伪装
        
        Returns:
            ssl.SSLContext: 配置好的SSL上下文
        """
        ssl_context = ssl.create_default_context()
        
        # 先检查并处理verify_mode和check_hostname的关系
        actual_check_hostname = self.ssl_check_hostname
        actual_verify_mode = self.ssl_verify_mode
        
        # 当verify_mode为CERT_NONE时，必须将check_hostname设置为False
        if actual_verify_mode == ssl.CERT_NONE:
            actual_check_hostname = False
            logger.debug("SSL验证模式为CERT_NONE，自动将check_hostname设置为False")
        
        # 先设置check_hostname，再设置verify_mode
        ssl_context.check_hostname = actual_check_hostname
        ssl_context.verify_mode = actual_verify_mode
        
        # TLS指纹伪装配置 - 使用实例变量中的TLS版本配置
        ssl_context.minimum_version = self.ssl_min_version
        ssl_context.maximum_version = self.ssl_max_version
        
        # 使用更广泛的加密套件，提高兼容性
        ssl_context.set_ciphers("ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-SHA384:ECDHE-RSA-AES128-SHA256")
        
        # 关闭会话复用（减少特征），兼容不同Python版本
        if hasattr(ssl, 'OP_NO_SESSION_RESUMPTION_ON_RECONNECT'):
            ssl_context.options |= ssl.OP_NO_SESSION_RESUMPTION_ON_RECONNECT
        
        # 禁用旧版本协议和不安全特性
        ssl_context.options |= ssl.OP_NO_SSLv2
        ssl_context.options |= ssl.OP_NO_SSLv3
        ssl_context.options |= ssl.OP_NO_TLSv1
        ssl_context.options |= ssl.OP_NO_TLSv1_1
        
        logger.debug(f"创建SSL上下文: 验证模式={ssl_context.verify_mode}, 检查主机名={ssl_context.check_hostname}, TLS版本范围=[{ssl_context.minimum_version}, {ssl_context.maximum_version}], 加密套件={ssl_context.get_ciphers()[0]['name']}等")
        logger.debug("SSL上下文已配置TLS指纹伪装，使用常见加密套件和TLS 1.2")
        
        return ssl_context
    
    async def _tcp_ping(self, ip, port=8443, timeout=3):
        """
        异步TCP连接预热，验证IP+端口可达性
        
        Args:
            ip (str): IP地址
            port (int): 端口号
            timeout (float): 超时时间
            
        Returns:
            bool: 是否可达
        """
        try:
            # 使用asyncio.wait_for来设置超时，兼容不同Python版本
            connect_coro = asyncio.open_connection(ip, port)
            reader, writer = await asyncio.wait_for(connect_coro, timeout=timeout)
            writer.close()
            await writer.wait_closed()
            logger.debug(f"TCP ping成功: {ip}:{port}")
            return True
        except asyncio.TimeoutError:
            logger.warning(f"TCP ping超时: {ip}:{port}")
            return False
        except ConnectionRefusedError:
            logger.warning(f"TCP连接被拒绝: {ip}:{port}")
            return False
        except Exception as e:
            logger.error(f"TCP ping失败: {ip}:{port}, 错误: {e}")
            return False
    
    def switch_to_next_ws_ip(self):
        """
        切换到下一个健康的WebSocket IP地址
        优先选择可用且健康状态好的IP
        
        Returns:
            str: 切换后的WebSocket IP地址
        """
        if not self.ws_ips:
            logger.warning("WebSocket IP列表为空，无法切换IP")
            return None
        
        # 尝试找到一个健康的IP，最多尝试所有IP
        attempts = 0
        original_index = self.current_ws_ip_index
        
        while attempts < len(self.ws_ips):
            # 切换到下一个IP
            self.current_ws_ip_index = (self.current_ws_ip_index + 1) % len(self.ws_ips)
            candidate_ip = self.ws_ips[self.current_ws_ip_index]
            
            # 检查IP健康状态
            if self.ip_health.get(candidate_ip, {}).get('available', False):
                self.ws_ip = candidate_ip
                logger.info(f"切换到健康的WebSocket IP: {self.ws_ip} (索引: {self.current_ws_ip_index}/{len(self.ws_ips)})")
                # 更新WebSocket URL
                self.update_websocket_urls()
                return self.ws_ip
            
            attempts += 1
        
        # 如果没有健康的IP，使用下一个IP（即使不健康）
        self.current_ws_ip_index = (original_index + 1) % len(self.ws_ips)
        self.ws_ip = self.ws_ips[self.current_ws_ip_index]
        logger.warning(f"所有IP均不健康，强制切换到: {self.ws_ip} (索引: {self.current_ws_ip_index}/{len(self.ws_ips)})")
        # 更新WebSocket URL
        self.update_websocket_urls()
        return self.ws_ip
    
    def update_websocket_urls(self):
        """
        更新WebSocket URL，使用当前活跃IP或直接指定的ws_ip
        """
        # 优先使用直接指定的WebSocket IP
        if self.ws_ip:
            # 获取原始域名
            original_domain = "wspap.okx.com" if self.is_test else "ws.okx.com"
            
            # 更新公共URL
            self.public_url = self.public_url_template.replace(original_domain, self.ws_ip)
            # 更新私有URL
            self.private_url = self.private_url_template.replace(original_domain, self.ws_ip)
            # 更新业务URL
            self.business_url = self.business_url_template.replace(original_domain, self.ws_ip)
            
            logger.info(f"已更新WebSocket URL为直接IP连接，当前IP: {self.ws_ip}")
            logger.info(f"公共URL: {self.public_url}")
            logger.info(f"私有URL: {self.private_url}")
            logger.info(f"业务URL: {self.business_url}")
        else:
            # 使用API IP列表中的IP
            current_ip = self.get_current_ip()
            if not current_ip:
                return
            
            # 获取原始域名
            original_domain = "wspap.okx.com" if self.is_test else "ws.okx.com"
            
            # 更新公共URL
            self.public_url = self.public_url_template.replace(original_domain, current_ip)
            # 更新私有URL
            self.private_url = self.private_url_template.replace(original_domain, current_ip)
            # 更新业务URL
            self.business_url = self.business_url_template.replace(original_domain, current_ip)
            
            logger.info(f"已更新WebSocket URL，当前IP: {current_ip}")
            logger.info(f"公共URL: {self.public_url}")
            logger.info(f"私有URL: {self.private_url}")
            logger.info(f"业务URL: {self.business_url}")
    
    def add_message_handler(self, channel, handler):
        """
        添加消息处理器
        
        Args:
            channel (str): 频道名称
            handler (callable): 消息处理函数
        """
        with self.lock:
            if channel not in self.message_handlers:
                self.message_handlers[channel] = []
            self.message_handlers[channel].append(handler)
            logger.info(f"添加消息处理器到频道: {channel}")
    
    def remove_message_handler(self, channel, handler):
        """
        移除消息处理器
        
        Args:
            channel (str): 频道名称
            handler (callable): 消息处理函数
        """
        with self.lock:
            if channel in self.message_handlers:
                self.message_handlers[channel].remove(handler)
    
    async def _handle_message(self, message):
        """
        处理接收到的消息
        
        Args:
            message (dict): 接收到的消息
        """
        try:
            # 解析消息
            msg_data = json.loads(message)
            
            # 处理登录响应
            if "event" in msg_data and msg_data["event"] == "login":
                auth_logger = get_logger("Auth")
                if msg_data["code"] == "0":
                    auth_logger.info("Websocket私有频道登录成功")
                    self.private_connected = True
                else:
                    auth_logger.error(f"Websocket私有频道登录失败: {msg_data['msg']}")
                    self.private_connected = False
                return
            
            # 处理订阅响应
            if "event" in msg_data and msg_data["event"] == "subscribe":
                sub_logger = get_logger("Subscription")
                if msg_data["code"] == "0":
                    sub_logger.info(f"成功订阅频道: {msg_data['arg']['channel']}")
                else:
                    sub_logger.error(f"订阅频道失败: {msg_data['msg']}")
                return
            
            # 处理心跳响应
            if "event" in msg_data and msg_data["event"] == "pong":
                heartbeat_logger = get_logger("Heartbeat")
                heartbeat_logger.debug("收到心跳响应pong")
                self.last_message_time = time.time()  # 重置消息时间
                self.last_ping_time = 0  # 重置ping时间
                return
            
            # 更新最后接收消息的时间
            self.last_message_time = time.time()
            
            # 处理频道连接数统计
            if "event" in msg_data and msg_data["event"] == "channel-conn-count":
                stats_logger = get_logger("Stats")
                channel = msg_data.get("channel", "")
                conn_count = msg_data.get("connCount", "")
                conn_id = msg_data.get("connId", "")
                stats_logger.info(f"频道连接数统计 - 频道: {channel}, 连接数: {conn_count}, 连接ID: {conn_id}")
                return
            
            # 处理频道连接数超过限制错误
            if "event" in msg_data and msg_data["event"] == "channel-conn-count-error":
                error_logger = get_logger("Error")
                channel = msg_data.get("channel", "")
                conn_count = msg_data.get("connCount", "")
                conn_id = msg_data.get("connId", "")
                error_logger.error(f"频道连接数超过限制 - 频道: {channel}, 连接数: {conn_count}, 连接ID: {conn_id}")
                # 可以在这里添加重连逻辑或其他处理
                return
            
            # 处理通知消息，如服务升级断线通知
            if "event" in msg_data and msg_data["event"] == "notice":
                notice_logger = get_logger("Notice")
                code = msg_data.get("code", "")
                msg = msg_data.get("msg", "")
                conn_id = msg_data.get("connId", "")
                notice_logger.warning(f"收到通知消息 - 代码: {code}, 消息: {msg}, 连接ID: {conn_id}")
                
                # 服务升级断线通知，代码64008
                if code == "64008":
                    notice_logger.warning("WebSocket服务即将升级，将在60秒后断开连接")
                    notice_logger.warning("建议重新建立新的连接")
                    # 可以在这里添加自动重连逻辑
                return
            
            # 处理数据消息
            if "data" in msg_data and "arg" in msg_data:
                channel = msg_data["arg"]["channel"]
                
                # 根据频道类型确定区域
                if channel.startswith('ticker') or channel.startswith('books') or channel.startswith('candles') or channel.startswith('trades'):
                    data_logger = get_logger("MarketData")
                elif channel.startswith('orders') or channel.startswith('trades'):
                    data_logger = get_logger("Trade")
                elif channel.startswith('account') or channel.startswith('balance'):
                    data_logger = get_logger("Account")
                else:
                    data_logger = get_logger("WebSocket")
                
                # 调用对应的消息处理器
                with self.lock:
                    if channel in self.message_handlers:
                        for handler in self.message_handlers[channel]:
                            try:
                                handler(msg_data)
                            except Exception as e:
                                data_logger.error(f"处理{channel}频道消息失败: {e}")
        except json.JSONDecodeError as e:
            error_logger = get_logger("Error")
            error_logger.error(f"解析Websocket消息失败: {e}")
        except Exception as e:
            error_logger = get_logger("Error")
            error_logger.error(f"处理Websocket消息失败: {e}")
    
    async def _heartbeat_handler(self, ws):
        """
        心跳处理器，符合API指南要求：
        1. 每次收到消息后重置定时器
        2. 定时检查，如果N秒（N<30）未收到消息则发送ping
        3. 发送ping后等待pong响应，超时则重新连接
        
        Args:
            ws: WebSocket连接
        """
        heartbeat_logger = get_logger("Heartbeat")
        while not self._should_stop:
            try:
                current_time = time.time()
                
                # 检查是否需要发送ping
                if current_time - self.last_message_time > self.heartbeat_interval:
                    # 发送ping
                    await ws.send(json.dumps({"event": "ping"}))
                    heartbeat_logger.debug("发送心跳ping")
                    self.last_ping_time = current_time
                    
                    # 等待pong响应，超时则断开连接
                    await asyncio.sleep(self.pong_timeout)
                    
                    # 检查是否收到pong响应
                    if current_time == self.last_ping_time:  # 未更新，说明未收到pong
                        heartbeat_logger.error("心跳超时，未收到pong响应")
                        break
                
                # 每1秒检查一次
                await asyncio.sleep(1)
            except Exception as e:
                heartbeat_logger.error(f"心跳处理失败: {e}")
                break
    
    async def _public_handler(self):
        """处理公共频道连接"""
        self.reconnect_attempts = 0
        ws_logger = get_logger("WebSocket")
        
        while self.reconnect_attempts < self.max_reconnect_attempts and not self._should_stop:
            try:
                # 定期清理内存
                import gc
                if self.reconnect_attempts % 5 == 0:
                    gc.collect()
                    ws_logger.debug("执行内存垃圾回收")
                
                # 从URL中提取IP地址
                import re
                ip_match = re.search(r'wss://([^:]+):', self.public_url)
                if not ip_match:
                    ws_logger.error(f"无效的WebSocket URL: {self.public_url}")
                    await asyncio.sleep(self.reconnect_delay)
                    self.reconnect_attempts += 1
                    continue
                
                current_ip = ip_match.group(1)
                ws_logger.info(f"连接到公共Websocket频道: {self.public_url} (IP: {current_ip}) (尝试 {self.reconnect_attempts + 1}/{self.max_reconnect_attempts})")
                
                # 更新IP健康状态 - 记录尝试
                self.ip_health[current_ip]['last_attempt'] = time.time()
                
                # 异步TCP连接预热
                if not await self._tcp_ping(current_ip, timeout=3):
                    ws_logger.warning(f"TCP ping失败: {current_ip}:8443，跳过连接尝试")
                    # 更新IP健康状态 - 失败
                    self.ip_health[current_ip]['fail_count'] += 1
                    self.ip_health[current_ip]['available'] = False
                    # 计算下一个重连延迟
                    self._calculate_next_reconnect_delay()
                    # 等待一段时间后重连
                    await asyncio.sleep(self.reconnect_delay)
                    self.reconnect_attempts += 1
                    # 切换到下一个WebSocket IP
                    self.switch_to_next_ws_ip()
                    continue
                
                # 创建自定义SSL上下文
                ssl_context = self.create_ssl_context()
                
                # 连接到公共Websocket，添加Host头和SNI设置，使用配置的连接参数
                connect_kwargs = {
                    "extra_headers": {"Host": self.original_host},
                    "ssl": ssl_context,
                    "server_hostname": self.original_host,
                    "open_timeout": self.open_timeout,  # 使用配置的连接超时时间
                    "ping_timeout": self.ping_timeout,   # 使用配置的心跳超时时间
                    "close_timeout": self.close_timeout,   # 使用配置的关闭超时时间
                    "max_queue": self.max_queue,      # 使用配置的最大队列大小
                    "ping_interval": self.ping_interval   # 使用配置的心跳间隔
                }
                
                # 统一的WebSocket连接处理
                ws = None
                
                try:
                    # 直接连接WebSocket
                    ws_logger.info(f"直接连接到公共Websocket: {self.public_url}")
                    ws_logger.info(f"WebSocket连接参数: Host={self.original_host}, SNI={self.original_host}")
                    ws_logger.info(f"当前使用的WebSocket IP: {current_ip}")
                    ws_logger.info(f"SSL验证模式: {ssl_context.verify_mode}, 检查主机名: {ssl_context.check_hostname}")
                    ws_logger.info(f"TLS版本范围: {ssl_context.minimum_version} - {ssl_context.maximum_version}")
                    ws_logger.info(f"加密套件: {ssl_context.get_ciphers()[0]['name']}等")
                    
                    # 测试TCP连接
                    import socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    sock.connect((current_ip, 8443))
                    sock.close()
                    ws_logger.info(f"TCP连接测试成功: {current_ip}:8443")
                    
                    ws = await websockets.connect(self.public_url, **connect_kwargs)
                    ws_logger.info(f"公共Websocket直接连接成功")
                    
                    # 设置连接状态
                    self.public_ws = ws
                    self.public_connected = True
                    
                    # 更新IP健康状态 - 成功
                    self.ip_health[current_ip]['success_count'] += 1
                    self.ip_health[current_ip]['fail_count'] = 0
                    self.ip_health[current_ip]['last_success'] = time.time()
                    self.ip_health[current_ip]['available'] = True
                    
                    # 重置重连尝试和延迟
                    self.reconnect_attempts = 0
                    self.reconnect_delay = self.base_reconnect_delay
                    
                    ws_logger.info(f"公共Websocket频道连接成功: {self.public_url}")
                    # 更新健康状态
                    self.update_health_status()
                    
                    # 重新订阅所有频道
                    if self.public_subscriptions:
                        sub_logger = get_logger("Subscription")
                        sub_logger.info(f"重新订阅 {len(self.public_subscriptions)} 个公共频道")
                        await self._resubscribe_public()
                    
                    # 启动心跳任务
                    heartbeat_task = asyncio.create_task(self._heartbeat_handler(ws))
                    
                    # 接收消息
                    ws_logger.info(f"开始接收公共Websocket消息: {self.public_url}")
                    async for message in ws:
                        if self._should_stop:
                            break
                        await self._handle_message(message)
                    
                except websockets.exceptions.ConnectionClosedError as e:
                    ws_logger.warning(f"公共Websocket连接被关闭: {e}")
                except Exception as e:
                    ws_logger.error(f"接收公共Websocket消息时发生错误: {e}")
                finally:
                    # 取消心跳任务
                    if 'heartbeat_task' in locals():
                        heartbeat_task.cancel()
                        try:
                            await heartbeat_task
                        except asyncio.CancelledError:
                            pass
                    
                    # 关闭WebSocket连接
                    if ws:
                        await ws.close()
                    
                    ws_logger.warning(f"公共Websocket连接已关闭: {self.public_url}")
                    self.public_connected = False
                    self.public_ws = None
                    # 更新健康状态
                    self.update_health_status()
                    
                    if self._should_stop:
                        break
                    
                    # 计算下一个重连延迟
                    self._calculate_next_reconnect_delay()
                    
                    # 等待一段时间后重连
                    ws_logger.info(f"{self.reconnect_delay}秒后尝试重新连接公共Websocket")
                    await asyncio.sleep(self.reconnect_delay)
                    self.reconnect_attempts += 1
                    ws_logger.info(f"尝试重新连接公共Websocket，第{self.reconnect_attempts}次")
                    
                    # 切换到下一个WebSocket IP
                    self.switch_to_next_ws_ip()
                    
            except Exception as e:
                # 根据异常类型进行不同处理
                exception_type = type(e).__name__
                
                if exception_type == 'WebSocketException':
                    ws_logger.error(f"公共Websocket连接异常: {e}，URL: {self.public_url}")
                    ws_logger.error(f"WebSocket异常类型: {exception_type}")
                elif exception_type == 'ConnectionResetError':
                    ws_logger.error(f"公共Websocket连接被重置: {e}，URL: {self.public_url}")
                    ws_logger.error(f"异常类型: {exception_type} - 这通常是网络层问题或SSL握手失败")
                else:
                    ws_logger.error(f"公共Websocket连接失败: {e}，URL: {self.public_url}")
                    ws_logger.error(f"异常类型: {exception_type}")
                    import traceback
                    ws_logger.error(f"异常堆栈: {traceback.format_exc()}")
                
                # 更新IP健康状态 - 失败
                self.ip_health[current_ip]['fail_count'] += 1
                
                # 如果连续失败3次，标记为不可用
                if self.ip_health[current_ip]['fail_count'] >= 3:
                    self.ip_health[current_ip]['available'] = False
                    ws_logger.warning(f"IP {current_ip} 连续 {self.ip_health[current_ip]['fail_count']} 次失败，标记为不可用")
                
                self.public_connected = False
                self.public_ws = None
                
                if self._should_stop:
                    break
                
                # 计算下一个重连延迟
                self._calculate_next_reconnect_delay()
                
                # 等待一段时间后重连
                ws_logger.info(f"{self.reconnect_delay}秒后尝试重新连接公共Websocket")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_attempts += 1
                ws_logger.info(f"尝试重新连接公共Websocket，第{self.reconnect_attempts}次")
                
                # 切换到下一个WebSocket IP
                self.switch_to_next_ws_ip()
        
        if not self._should_stop:
            ws_logger.error("公共Websocket重连次数已达上限")
        else:
            ws_logger.info("公共Websocket连接已停止")
    
    def _calculate_next_reconnect_delay(self):
        """
        计算下一次重连延迟，实现指数退避算法
        """
        if self.exponential_backoff:
            # 指数退避: base_delay * (backoff_factor ** reconnect_attempts)
            new_delay = self.base_reconnect_delay * (self.backoff_factor ** self.reconnect_attempts)
            # 限制最大延迟
            self.reconnect_delay = min(new_delay, self.max_reconnect_delay)
            logger.info(f"使用指数退避，重连延迟从 {self.base_reconnect_delay}s 增加到 {self.reconnect_delay:.2f}s")
        else:
            # 固定延迟
            self.reconnect_delay = self.base_reconnect_delay

    def get_connection_status(self, conn_type='public'):
        """
        获取指定类型连接的状态
        
        Args:
            conn_type (str): 连接类型，可选值：public, private, business
            
        Returns:
            dict: 连接状态信息
        """
        return self.connection_status.get(conn_type, {'connected': False, 'ws': None, 'task': None})
    
    def update_connection_status(self, conn_type='public', connected=False, ws=None, task=None):
        """
        更新指定类型连接的状态
        
        Args:
            conn_type (str): 连接类型，可选值：public, private, business
            connected (bool): 是否连接
            ws: WebSocket连接对象
            task: 连接任务对象
        """
        if conn_type in self.connection_status:
            self.connection_status[conn_type]['connected'] = connected
            if ws is not None:
                self.connection_status[conn_type]['ws'] = ws
            if task is not None:
                self.connection_status[conn_type]['task'] = task
    
    def update_connection_quality(self, conn_type='public', latency=0, success=True, message_count=0, error_count=0):
        """
        更新连接质量统计
        
        Args:
            conn_type (str): 连接类型，可选值：public, private, business
            latency (float): 延迟时间，单位秒
            success (bool): 操作是否成功
            message_count (int): 消息计数增量
            error_count (int): 错误计数增量
        """
        if conn_type in self.connection_quality:
            quality = self.connection_quality[conn_type]
            
            # 更新延迟（使用滑动平均）
            if latency > 0:
                quality['latency'] = (quality['latency'] * 0.9 + latency * 0.1)  # 滑动平均
            
            # 更新消息计数
            quality['message_count'] += message_count
            
            # 更新错误计数
            if not success:
                quality['error_count'] += error_count
            
            # 更新成功率
            total = quality['message_count'] + quality['error_count']
            if total > 0:
                quality['success_rate'] = quality['message_count'] / total
    
    def get_connection_quality(self, conn_type='public'):
        """
        获取连接质量报告
        
        Args:
            conn_type (str): 连接类型，可选值：public, private, business
            
        Returns:
            dict: 连接质量统计信息
        """
        return self.connection_quality.get(conn_type, {'latency': 0, 'success_rate': 1.0, 'message_count': 0, 'error_count': 0})
    
    def is_connected(self, conn_type='public'):
        """
        检查指定类型的连接是否已连接
        
        Args:
            conn_type (str): 连接类型，可选值：public, private, business
            
        Returns:
            bool: 是否已连接
        """
        return self.connection_status.get(conn_type, {}).get('connected', False)
    
    def close_all_connections(self):
        """
        关闭所有WebSocket连接
        """
        logger.info("关闭所有WebSocket连接...")
        
        # 停止所有连接
        self._should_stop = True
        
        # 关闭所有连接状态
        for conn_type in self.connection_status:
            status = self.connection_status[conn_type]
            if status['ws'] and hasattr(status['ws'], 'close'):
                try:
                    asyncio.run(status['ws'].close())
                except Exception as e:
                    logger.error(f"关闭{conn_type}连接时出错: {e}")
            
            if status['task'] and hasattr(status['task'], 'cancel'):
                try:
                    status['task'].cancel()
                except Exception as e:
                    logger.error(f"取消{conn_type}任务时出错: {e}")
        
        logger.info("所有WebSocket连接已关闭")
        
    def update_health_status(self):
        """
        更新健康检查状态
        """
        try:
            from commons.health_checker import global_health_checker
            
            # 检查WebSocket状态
            ws_status = 'PASS' if self.public_connected or self.private_connected else 'FAIL'
            connected_channels = list(self.public_subscriptions) + list(self.private_subscriptions)
            global_health_checker.update_check_status(
                'websocket',
                ws_status,
                f'WebSocket连接正常，已订阅{len(connected_channels)}个频道' if ws_status == 'PASS' else 'WebSocket连接失败',
                connected_channels=connected_channels,
                last_message_time=self.last_message_time
            )
        except Exception as e:
            logger.error(f"更新WebSocket健康状态失败: {e}")

    def update_ip_health(self, ip, success=True):
        """
        更新IP健康状态
        
        Args:
            ip (str): IP地址
            success (bool): 是否连接成功
        """
        if ip not in self.ip_health:
            self.ip_health[ip] = {
                'success_count': 0,
                'fail_count': 0,
                'last_attempt': 0,
                'last_success': 0,
                'available': True
            }
        
        current_time = time.time()
        self.ip_health[ip]['last_attempt'] = current_time
        
        if success:
            self.ip_health[ip]['success_count'] += 1
            self.ip_health[ip]['fail_count'] = 0  # 重置失败计数
            self.ip_health[ip]['last_success'] = current_time
            self.ip_health[ip]['available'] = True
            logger.debug(f"IP {ip} 健康状态更新: 成功 +1, 总计 {self.ip_health[ip]['success_count']} 次成功")
        else:
            self.ip_health[ip]['fail_count'] += 1
            # 如果连续失败次数超过阈值，标记为不可用
            if self.ip_health[ip]['fail_count'] >= 3:
                self.ip_health[ip]['available'] = False
                logger.warning(f"IP {ip} 连续 {self.ip_health[ip]['fail_count']} 次失败，标记为不可用")
            logger.debug(f"IP {ip} 健康状态更新: 失败 +1, 总计 {self.ip_health[ip]['fail_count']} 次失败")
    
    async def _private_handler(self):
        """处理私有频道连接"""
        self.reconnect_attempts = 0
        ws_logger = get_logger("WebSocket")
        
        while self.reconnect_attempts < self.max_reconnect_attempts and not self._should_stop:
            try:
                # 定期清理内存
                import gc
                if self.reconnect_attempts % 5 == 0:
                    gc.collect()
                    ws_logger.debug("执行内存垃圾回收")
                
                # 从URL中提取IP地址
                import re
                ip_match = re.search(r'wss://([^:]+):', self.private_url)
                if not ip_match:
                    ws_logger.error(f"无效的WebSocket URL: {self.private_url}")
                    await asyncio.sleep(self.reconnect_delay)
                    self.reconnect_attempts += 1
                    continue
                
                current_ip = ip_match.group(1)
                ws_logger.info(f"连接到私有Websocket频道: {self.private_url} (IP: {current_ip}) (尝试 {self.reconnect_attempts + 1}/{self.max_reconnect_attempts})")
                
                # 更新IP健康状态 - 记录尝试
                self.ip_health[current_ip]['last_attempt'] = time.time()
                
                # 异步TCP连接预热
                if not await self._tcp_ping(current_ip, timeout=3):
                    ws_logger.warning(f"TCP ping失败: {current_ip}:8443，跳过连接尝试")
                    # 更新IP健康状态 - 失败
                    self.ip_health[current_ip]['fail_count'] += 1
                    self.ip_health[current_ip]['available'] = False
                    # 计算下一个重连延迟
                    self._calculate_next_reconnect_delay()
                    # 等待一段时间后重连
                    await asyncio.sleep(self.reconnect_delay)
                    self.reconnect_attempts += 1
                    # 切换到下一个WebSocket IP
                    self.switch_to_next_ws_ip()
                    continue
                
                # 创建自定义SSL上下文
                ssl_context = self.create_ssl_context()
                
                # 连接到私有Websocket，添加Host头和SNI设置，使用配置的连接参数
                connect_kwargs = {
                    "extra_headers": {"Host": self.original_host},
                    "ssl": ssl_context,
                    "server_hostname": self.original_host,
                    "open_timeout": self.open_timeout,  # 使用配置的连接超时时间
                    "ping_timeout": self.ping_timeout,   # 使用配置的心跳超时时间
                    "close_timeout": self.close_timeout,   # 使用配置的关闭超时时间
                    "max_queue": self.max_queue,      # 使用配置的最大队列大小
                    "ping_interval": self.ping_interval   # 使用配置的心跳间隔
                }
                
                # 统一的WebSocket连接处理
                ws = None
                
                try:
                    # 直接连接WebSocket
                    ws_logger.info(f"直接连接到私有Websocket: {self.private_url}")
                    ws_logger.info(f"WebSocket连接参数: Host={self.original_host}, SNI={self.original_host}")
                    ws_logger.info(f"当前使用的WebSocket IP: {current_ip}")
                    ws_logger.info(f"SSL验证模式: {ssl_context.verify_mode}, 检查主机名: {ssl_context.check_hostname}")
                    ws_logger.info(f"TLS版本范围: {ssl_context.minimum_version} - {ssl_context.maximum_version}")
                    ws_logger.info(f"加密套件: {ssl_context.get_ciphers()[0]['name']}等")
                    
                    # 测试TCP连接
                    import socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    sock.connect((current_ip, 8443))
                    sock.close()
                    ws_logger.info(f"TCP连接测试成功: {current_ip}:8443")
                    
                    ws = await websockets.connect(self.private_url, **connect_kwargs)
                    ws_logger.info(f"私有Websocket直接连接成功")
                    
                    # 设置连接状态
                    self.private_ws = ws
                    
                    # 更新IP健康状态 - 成功
                    self.ip_health[current_ip]['success_count'] += 1
                    self.ip_health[current_ip]['fail_count'] = 0
                    self.ip_health[current_ip]['last_success'] = time.time()
                    self.ip_health[current_ip]['available'] = True
                    
                    # 重置重连尝试和延迟
                    self.reconnect_attempts = 0
                    self.reconnect_delay = self.base_reconnect_delay
                    
                    ws_logger.info(f"私有Websocket频道连接成功: {self.private_url}")
                    # 更新健康状态
                    self.update_health_status()
                    
                    # 登录
                    auth_logger = get_logger("Auth")
                    auth_logger.info(f"正在登录私有Websocket频道: {self.private_url}")
                    await self._login(ws)
                    
                    # 启动心跳任务
                    heartbeat_task = asyncio.create_task(self._heartbeat_handler(ws))
                    
                    # 接收消息
                    ws_logger.info(f"开始接收私有Websocket消息: {self.private_url}")
                    async for message in ws:
                        if self._should_stop:
                            break
                        await self._handle_message(message)
                    
                except websockets.exceptions.ConnectionClosedError as e:
                    ws_logger.warning(f"私有Websocket连接被关闭: {e}")
                except Exception as e:
                    ws_logger.error(f"接收私有Websocket消息时发生错误: {e}")
                finally:
                    # 取消心跳任务
                    if 'heartbeat_task' in locals():
                        heartbeat_task.cancel()
                        try:
                            await heartbeat_task
                        except asyncio.CancelledError:
                            pass
                    
                    # 关闭WebSocket连接
                    if ws:
                        await ws.close()
                    
                    ws_logger.warning(f"私有Websocket连接已关闭: {self.private_url}")
                    self.private_connected = False
                    self.private_ws = None
                    # 更新健康状态
                    self.update_health_status()
                    
                    if self._should_stop:
                        break
                    
                    # 计算下一个重连延迟
                    self._calculate_next_reconnect_delay()
                    
                    # 等待一段时间后重连
                    ws_logger.info(f"{self.reconnect_delay}秒后尝试重新连接私有Websocket")
                    await asyncio.sleep(self.reconnect_delay)
                    self.reconnect_attempts += 1
                    ws_logger.info(f"尝试重新连接私有Websocket，第{self.reconnect_attempts}次")
                    
                    # 切换到下一个WebSocket IP
                    self.switch_to_next_ws_ip()
                    
            except Exception as e:
                # 根据异常类型进行不同处理
                exception_type = type(e).__name__
                
                if exception_type == 'WebSocketException':
                    ws_logger.error(f"私有Websocket连接异常: {e}，URL: {self.private_url}")
                    ws_logger.error(f"WebSocket异常类型: {exception_type}")
                elif exception_type == 'ConnectionResetError':
                    ws_logger.error(f"私有Websocket连接被重置: {e}，URL: {self.private_url}")
                    ws_logger.error(f"异常类型: {exception_type} - 这通常是网络层问题或SSL握手失败")
                else:
                    ws_logger.error(f"私有Websocket连接失败: {e}，URL: {self.private_url}")
                    ws_logger.error(f"异常类型: {exception_type}")
                    import traceback
                    ws_logger.error(f"异常堆栈: {traceback.format_exc()}")
                
                # 更新IP健康状态 - 失败
                self.ip_health[current_ip]['fail_count'] += 1
                
                # 如果连续失败3次，标记为不可用
                if self.ip_health[current_ip]['fail_count'] >= 3:
                    self.ip_health[current_ip]['available'] = False
                    ws_logger.warning(f"IP {current_ip} 连续 {self.ip_health[current_ip]['fail_count']} 次失败，标记为不可用")
                
                self.private_connected = False
                self.private_ws = None
                
                if self._should_stop:
                    break
                
                # 计算下一个重连延迟
                self._calculate_next_reconnect_delay()
                
                # 等待一段时间后重连
                ws_logger.info(f"{self.reconnect_delay}秒后尝试重新连接私有Websocket")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_attempts += 1
                ws_logger.info(f"尝试重新连接私有Websocket，第{self.reconnect_attempts}次")
                
                # 切换到下一个WebSocket IP
                self.switch_to_next_ws_ip()
        
        if not self._should_stop:
            ws_logger.error("私有Websocket重连次数已达上限")
        else:
            ws_logger.info("私有Websocket连接已停止")
    
    async def _login(self, ws):
        """
        登录私有频道
        
        Args:
            ws: WebSocket连接
        """
        auth_logger = get_logger("Auth")
        try:
            # 获取Unix Epoch时间戳，单位是秒
            timestamp = str(int(time.time()))
            
            # 生成签名
            login_params = {
                "op": "login",
                "args": [
                    {
                        "apiKey": self.api_key,
                        "passphrase": self.passphrase,
                        "timestamp": timestamp,
                        "sign": self._generate_signature(timestamp)
                    }
                ]
            }
            
            await ws.send(json.dumps(login_params))
            auth_logger.info("发送Websocket登录请求")
        except Exception as e:
            auth_logger.error(f"发送Websocket登录请求失败: {e}")
    
    def _generate_signature(self, timestamp):
        """
        生成WebSocket登录签名，符合API指南要求
        
        Args:
            timestamp (str): 时间戳，Unix Epoch时间，单位是秒
        
        Returns:
            str: 签名
        """
        import hmac
        import base64
        
        # 根据API指南，WebSocket登录签名必须使用：timestamp + 'GET' + '/users/self/verify'
        # method必须全部大写
        method = 'GET'
        request_path = '/users/self/verify'
        message = timestamp + method + request_path
        
        # 生成HMAC SHA256签名
        mac = hmac.new(bytes(self.api_secret, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
        d = mac.digest()
        
        # Base64编码
        return base64.b64encode(d).decode()
    
    async def _subscribe(self, ws, channel, inst_id, is_public=True):
        """
        订阅频道
        
        Args:
            ws: WebSocket连接
            channel (str): 频道名称
            inst_id (str): 交易对
            is_public (bool): 是否为公共频道
        """
        try:
            subscribe_msg = {
                "op": "subscribe",
                "args": [
                    {
                        "channel": channel,
                        "instId": inst_id
                    }
                ]
            }
            
            await ws.send(json.dumps(subscribe_msg))
            logger.info(f"订阅{channel}频道，交易对: {inst_id}")
            
            # 更新订阅列表
            subscription_key = f"{channel}:{inst_id}"
            if is_public:
                self.public_subscriptions.add(subscription_key)
            else:
                self.private_subscriptions.add(subscription_key)
        except Exception as e:
            logger.error(f"订阅{channel}频道失败: {e}")
    
    async def _unsubscribe(self, ws, channel, inst_id, is_public=True):
        """
        取消订阅频道
        
        Args:
            ws: WebSocket连接
            channel (str): 频道名称
            inst_id (str): 交易对
            is_public (bool): 是否为公共频道
        """
        try:
            unsubscribe_msg = {
                "op": "unsubscribe",
                "args": [
                    {
                        "channel": channel,
                        "instId": inst_id
                    }
                ]
            }
            
            await ws.send(json.dumps(unsubscribe_msg))
            logger.info(f"取消订阅{channel}频道，交易对: {inst_id}")
            
            # 更新订阅列表
            subscription_key = f"{channel}:{inst_id}"
            if is_public:
                self.public_subscriptions.discard(subscription_key)
            else:
                self.private_subscriptions.discard(subscription_key)
        except Exception as e:
            logger.error(f"取消订阅{channel}频道失败: {e}")
    
    async def _resubscribe_public(self):
        """重新订阅所有公共频道"""
        if not self.public_ws or not self.public_connected:
            return
        
        for subscription in self.public_subscriptions:
            channel, inst_id = subscription.split(":")
            await self._subscribe(self.public_ws, channel, inst_id, is_public=True)
    
    async def _resubscribe_private(self):
        """重新订阅所有私有频道"""
        if not self.private_ws or not self.private_connected:
            return
        
        for subscription in self.private_subscriptions:
            channel, inst_id = subscription.split(":")
            await self._subscribe(self.private_ws, channel, inst_id, is_public=False)
    
    def subscribe_public(self, channel, inst_id):
        """
        订阅公共频道
        
        Args:
            channel (str): 频道名称（如tickers, books, candles）
            inst_id (str): 交易对
        """
        if not self.public_connected:
            logger.error("公共Websocket连接未建立，无法订阅频道")
            return
        
        asyncio.create_task(self._subscribe(self.public_ws, channel, inst_id, is_public=True))
    
    def subscribe_private(self, channel, inst_id):
        """
        订阅私有频道
        
        Args:
            channel (str): 频道名称（如orders, positions, account）
            inst_id (str): 交易对
        """
        if not self.private_connected:
            logger.error("私有Websocket连接未建立，无法订阅频道")
            return
        
        asyncio.create_task(self._subscribe(self.private_ws, channel, inst_id, is_public=False))
    
    def unsubscribe_public(self, channel, inst_id):
        """
        取消订阅公共频道
        
        Args:
            channel (str): 频道名称
            inst_id (str): 交易对
        """
        if not self.public_connected:
            logger.error("公共Websocket连接未建立，无法取消订阅频道")
            return
        
        asyncio.create_task(self._unsubscribe(self.public_ws, channel, inst_id, is_public=True))
    
    def unsubscribe_private(self, channel, inst_id):
        """
        取消订阅私有频道
        
        Args:
            channel (str): 频道名称
            inst_id (str): 交易对
        """
        if not self.private_connected:
            logger.error("私有Websocket连接未建立，无法取消订阅频道")
            return
        
        asyncio.create_task(self._unsubscribe(self.private_ws, channel, inst_id, is_public=False))
    
    def start(self):
        """启动Websocket客户端"""
        # 启动公共频道连接
        def public_loop():
            asyncio.run(self._public_handler())
        
        # 启动私有频道连接
        def private_loop():
            asyncio.run(self._private_handler())
        
        # 启动公共频道线程
        self.public_thread = Thread(target=public_loop, daemon=True)
        self.public_thread.start()
        
        # 启动私有频道线程
        self.private_thread = Thread(target=private_loop, daemon=True)
        self.private_thread.start()
        
        logger.info("OKX Websocket客户端启动完成")
    
    def stop(self):
        """停止Websocket客户端"""
        logger.info("正在停止OKX Websocket客户端...")
        
        # 设置停止标志
        self._should_stop = True
        
        # 等待线程结束
        if hasattr(self, 'public_thread') and self.public_thread.is_alive():
            logger.info("等待公共频道线程结束...")
            # 不使用join()，避免阻塞主线程，让线程自然结束
        
        if hasattr(self, 'private_thread') and self.private_thread.is_alive():
            logger.info("等待私有频道线程结束...")
            # 不使用join()，避免阻塞主线程，让线程自然结束
        
        logger.info("OKX Websocket客户端已停止")

# 创建默认客户端实例
default_ws_client = None

def get_ws_client():
    """获取默认Websocket客户端实例"""
    global default_ws_client
    if not default_ws_client:
        from okx_api_client import OKXAPIClient
        client = OKXAPIClient()
        # 尝试从环境变量获取ws_ip，优先级高于配置文件
        import os
        ws_ip = os.getenv("OKX_WS_IP") or client.ws_ip
        
        # 尝试从环境变量获取ws_ips，格式为逗号分隔的字符串
        ws_ips_env = os.getenv("OKX_WS_IPS")
        if ws_ips_env:
            ws_ips = ws_ips_env.split(",")
        else:
            ws_ips = getattr(client, 'ws_ips', []) or []
        
        # 如果ws_ip不在ws_ips列表中，添加到列表开头
        if ws_ip and ws_ip not in ws_ips:
            ws_ips.insert(0, ws_ip)
        
        default_ws_client = OKXWebsocketClient(
            api_key=client.api_key,
            api_secret=client.api_secret,
            passphrase=client.passphrase,
            is_test=client.is_test,
            api_ip=client.api_ip,
            api_ips=client.api_ips,
            ws_ip=ws_ip,
            ws_ips=ws_ips
        )
        # 设置WebSocket超时和心跳参数
        default_ws_client.open_timeout = client.ws_open_timeout
        default_ws_client.ping_timeout = client.ws_ping_timeout
        default_ws_client.close_timeout = client.ws_close_timeout
        default_ws_client.max_queue = client.ws_max_queue
        default_ws_client.ping_interval = client.ws_ping_interval
    return default_ws_client

if __name__ == "__main__":
    # 测试Websocket客户端
    try:
        # 创建客户端
        ws_client = OKXWebsocketClient(is_test=True)
        
        # 定义消息处理器
        def handle_ticker_message(msg):
            logger.info(f"收到行情消息: {msg['data'][0]['instId']}，最新价格: {msg['data'][0]['last']}")
        
        # 添加消息处理器
        ws_client.add_message_handler("tickers", handle_ticker_message)
        
        # 启动客户端
        ws_client.start()
        
        # 等待连接建立
        time.sleep(3)
        
        # 订阅行情频道
        ws_client.subscribe_public("tickers", "BTC-USDT-SWAP")
        
        # 运行10秒
        time.sleep(10)
        
        # 停止客户端
        ws_client.stop()
        
    except Exception as e:
        logger.error(f"测试失败: {e}")

# 创建全局WebSocket客户端实例
global_ws_client = None

def get_global_ws_client():
    """
    获取全局WebSocket客户端实例
    
    Returns:
        OKXWebsocketClient: 全局WebSocket客户端实例
    """
    global global_ws_client
    if not global_ws_client:
        global_ws_client = OKXWebsocketClient()
    return global_ws_client
