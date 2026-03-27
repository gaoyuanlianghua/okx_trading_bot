# network/http_adapters.py
"""
HTTP适配器模块
"""

import socket
import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPSConnection
from urllib3.poolmanager import PoolManager
from .dns_resolver import custom_dns_resolve, CURRENT_DNS_CONFIG

# 初始化日志配置
from commons.logger_config import global_logger_config

# 获取区域化日志记录器
def get_logger(region=None):
    return global_logger_config.get_logger(region=region)

# 创建默认日志记录器
logger = get_logger("Network")


class CustomHTTPSConnection(HTTPSConnection):
    """自定义HTTPS连接，支持使用IP地址但验证证书针对原始主机名"""
    def __init__(self, *args, **kwargs):
        self.hostname = kwargs.pop('hostname', None)
        super().__init__(*args, **kwargs)
    
    def connect(self):
        """连接到服务器，使用正确的主机名进行证书验证和SNI"""
        # 保存原始host用于证书验证
        original_host = self.host
        
        # 如果提供了hostname，使用它进行证书验证和SNI
        if self.hostname:
            self.assert_hostname = self.hostname
            # 设置SNI (Server Name Indication)，这对于Cloudflare SSL验证至关重要
            self._tunnel_host = self.hostname
        
        # 连接到服务器
        super().connect()
        
        # 恢复原始host
        self.host = original_host


class CustomPoolManager(PoolManager):
    """自定义连接池管理器，使用CustomHTTPSConnection"""
    def _new_conn(self, conn_cls, *args, **kwargs):
        """创建新连接"""
        if conn_cls == HTTPSConnection:
            # 保存原始主机名用于证书验证
            original_host = kwargs.get('host')
            if original_host:
                kwargs['hostname'] = original_host
            return super()._new_conn(CustomHTTPSConnection, *args, **kwargs)
        return super()._new_conn(conn_cls, *args, **kwargs)


class CustomHTTPSAdapter(HTTPAdapter):
    """自定义HTTP适配器，使用CustomPoolManager"""
    def init_poolmanager(self, connections, maxsize, block=False):
        """初始化连接池管理器"""
        # 获取SSL相关参数
        ssl_context = getattr(self, 'ssl_context', None)
        cert_reqs = getattr(self, 'cert_reqs', 'CERT_REQUIRED')
        ca_certs = getattr(self, 'ca_certs', None)
        ca_cert_dir = getattr(self, 'ca_cert_dir', None)
        ca_cert_data = getattr(self, 'ca_cert_data', None)
        ssl_version = getattr(self, 'ssl_version', None)
        ssl_minimum_version = getattr(self, 'ssl_minimum_version', None)
        ssl_maximum_version = getattr(self, 'ssl_maximum_version', None)
        assert_fingerprint = getattr(self, 'assert_fingerprint', None)
        
        self.poolmanager = CustomPoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=ssl_context,
            cert_reqs=cert_reqs,
            ca_certs=ca_certs,
            ca_cert_dir=ca_cert_dir,
            ca_cert_data=ca_cert_data,
            ssl_version=ssl_version,
            ssl_minimum_version=ssl_minimum_version,
            ssl_maximum_version=ssl_maximum_version,
            assert_hostname=True,
            assert_fingerprint=assert_fingerprint,
        )


class DNSResolverAdapter(HTTPAdapter):
    """自定义HTTP适配器，使用可靠的DNS解析和正确的SSL验证"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def init_poolmanager(self, connections, maxsize, block=False):
        """初始化连接池管理器"""
        # 获取SSL相关参数
        ssl_context = getattr(self, 'ssl_context', None)
        cert_reqs = getattr(self, 'cert_reqs', 'CERT_REQUIRED')
        ca_certs = getattr(self, 'ca_certs', None)
        ca_cert_dir = getattr(self, 'ca_cert_dir', None)
        ca_cert_data = getattr(self, 'ca_cert_data', None)
        ssl_version = getattr(self, 'ssl_version', None)
        ssl_minimum_version = getattr(self, 'ssl_minimum_version', None)
        ssl_maximum_version = getattr(self, 'ssl_maximum_version', None)
        assert_fingerprint = getattr(self, 'assert_fingerprint', None)
        
        self.poolmanager = CustomPoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=ssl_context,
            cert_reqs=cert_reqs,
            ca_certs=ca_certs,
            ca_cert_dir=ca_cert_dir,
            ca_cert_data=ca_cert_data,
            ssl_version=ssl_version,
            ssl_minimum_version=ssl_minimum_version,
            ssl_maximum_version=ssl_maximum_version,
            assert_hostname=True,
            assert_fingerprint=assert_fingerprint,
        )
    
    def proxy_manager_for(self, proxy, **proxy_kwargs):
        """获取代理管理器"""
        # 获取SSL相关参数
        ssl_context = getattr(self, 'ssl_context', None)
        cert_reqs = getattr(self, 'cert_reqs', 'CERT_REQUIRED')
        ca_certs = getattr(self, 'ca_certs', None)
        ca_cert_dir = getattr(self, 'ca_cert_dir', None)
        ca_cert_data = getattr(self, 'ca_cert_data', None)
        ssl_version = getattr(self, 'ssl_version', None)
        ssl_minimum_version = getattr(self, 'ssl_minimum_version', None)
        ssl_maximum_version = getattr(self, 'ssl_maximum_version', None)
        assert_fingerprint = getattr(self, 'assert_fingerprint', None)
        
        proxy_kwargs.setdefault('ssl_context', ssl_context)
        proxy_kwargs.setdefault('cert_reqs', cert_reqs)
        proxy_kwargs.setdefault('ca_certs', ca_certs)
        proxy_kwargs.setdefault('ca_cert_dir', ca_cert_dir)
        proxy_kwargs.setdefault('ca_cert_data', ca_cert_data)
        proxy_kwargs.setdefault('ssl_version', ssl_version)
        proxy_kwargs.setdefault('ssl_minimum_version', ssl_minimum_version)
        proxy_kwargs.setdefault('ssl_maximum_version', ssl_maximum_version)
        proxy_kwargs.setdefault('assert_hostname', True)
        proxy_kwargs.setdefault('assert_fingerprint', assert_fingerprint)
        
        return super().proxy_manager_for(proxy, **proxy_kwargs)
    
    def _create_connection(self, conn_factory, host, port, **kwargs):
        """
        创建连接，使用可靠的DNS解析
        
        Args:
            conn_factory: 连接工厂函数
            host (str): 主机名
            port (int): 端口号
            kwargs: 其他参数
            
        Returns:
            connection: 创建的连接
        """
        # 保存原始主机名
        original_host = host
        
        # 使用自定义DNS解析获取IP
        resolved_ip = custom_dns_resolve(host)
        if resolved_ip:
            logger.debug(f"使用自定义DNS解析 {host} → {resolved_ip}")
            # 使用解析到的IP建立连接，但保留原始主机名用于SSL验证
            kwargs['hostname'] = original_host
            return super()._create_connection(conn_factory, resolved_ip, port, **kwargs)
        else:
            # 解析失败，使用默认解析
            logger.warning(f"自定义DNS解析 {host} 失败，使用默认解析")
            return super()._create_connection(conn_factory, host, port, **kwargs)


# 保存原始socket.getaddrinfo函数
original_getaddrinfo = socket.getaddrinfo


# 自定义getaddrinfo函数，使用我们的DNS解析
def custom_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    """
    自定义getaddrinfo函数，根据配置使用可靠的DNS解析
    
    Args:
        host (str): 主机名
        port (int): 端口号
        family (int): 地址族
        type (int): 套接字类型
        proto (int): 协议
        flags (int): 标志
        
    Returns:
        list: 地址信息列表
    """
    try:
        # 检查是否启用了自定义DNS解析
        if CURRENT_DNS_CONFIG.get('use_custom_dns', True):
            # 如果是OKX域名，使用我们的自定义DNS解析
            if host == 'www.okx.com' or host == 'ws.okx.com' or host == 'okx.com':
                resolved_ip = custom_dns_resolve(host)
                if resolved_ip:
                    logger.debug(f"使用自定义DNS解析 {host} 到 {resolved_ip}")
                    # 使用解析到的IP调用原始getaddrinfo
                    return original_getaddrinfo(resolved_ip, port, family, type, proto, flags)
            logger.debug(f"跳过自定义DNS解析，使用系统DNS: {host}")
        else:
            logger.debug(f"自定义DNS解析已禁用，使用系统默认DNS: {host}")
    except Exception as e:
        logger.error(f"自定义DNS解析失败: {e}")
    
    # 对于其他域名或解析失败，使用原始getaddrinfo
    return original_getaddrinfo(host, port, family, type, proto, flags)


class DNSBypassingSession(requests.Session):
    """自定义HTTP会话，支持可靠DNS解析和故障恢复"""
    
    def __init__(self, retry_count=3, backoff_factor=0.5):
        """
        初始化DNS绕过会话
        
        Args:
            retry_count (int): 重试次数
            backoff_factor (float): 退避因子
        """
        super().__init__()
        self.ip_response_times = {}
        self.active_proxy_url = None
        
        # 配置重试策略，包括DNS解析失败
        from urllib3.util.retry import Retry
        retry_strategy = Retry(
            total=retry_count,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST"],
            backoff_factor=backoff_factor
        )
        
        # 使用标准HTTP适配器，我们将通过socket.getaddrinfo补丁来处理DNS解析
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.mount("https://", adapter)
        
        # 确保OKX API所需的headers
        self.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "okx-trading-bot/1.0"
        })
        
        # 再次从配置文件加载DNS配置，确保使用最新的配置值
        try:
            from commons.config_manager import global_config_manager
            config = global_config_manager.get_config()
            network_config = config.get('network', {})
            use_custom_dns = network_config.get('use_custom_dns', True)
        except Exception as e:
            logger.error(f"加载DNS配置失败: {e}")
            use_custom_dns = True
        
        # 检查是否启用自定义DNS解析
        if use_custom_dns:
            # 补丁socket.getaddrinfo函数，使用我们的自定义DNS解析
            socket.getaddrinfo = custom_getaddrinfo
            logger.info("已启用自定义DNS解析")
        else:
            logger.info("已禁用自定义DNS解析")
    
    def prepare_request(self, request):
        """准备请求"""
        # 不需要修改URL，使用原始域名确保SNI正常工作
        # 自定义DNS解析通过socket.getaddrinfo补丁实现
        return super().prepare_request(request)
    
    def request(self, method, url, **kwargs):
        """
        发送请求，添加额外的错误处理和DNS解析错误处理
        """
        start_time = time.time()
        max_retries = 3
        retry_count = 0
        initial_delay = 0.5
        backoff_factor = 2
        
        # 记录代理使用情况
        proxy_info = "，使用代理: 是" if self.proxies else "，未使用代理"
        
        while retry_count < max_retries:
            try:
                logger.info(f"发送请求: {method} {url}{proxy_info}")
                logger.debug(f"请求头: {self.headers}")
                
                response = super().request(method, url, **kwargs)
                response.raise_for_status()
                
                # 记录响应时间和状态码
                elapsed_time = time.time() - start_time
                logger.info(f"请求成功: {method} {url}，状态码: {response.status_code}，响应时间: {elapsed_time:.3f}s{proxy_info}")
                logger.debug(f"响应头: {response.headers}")
                
                return response
            except requests.exceptions.ProxyError as e:
                retry_count += 1
                delay = initial_delay * (backoff_factor ** (retry_count - 1))
                logger.error(f"代理连接失败: {e}{proxy_info}")
                logger.error(f"请求详情: {method} {url}")
                logger.error(f"代理配置: {self.proxies}")
                
                if retry_count < max_retries:
                    logger.info(f"{delay}秒后重试请求")
                    time.sleep(delay)
                else:
                    logger.error(f"请求重试次数耗尽: {method} {url}{proxy_info}")
                    raise
            except requests.exceptions.SSLError as e:
                retry_count += 1
                delay = initial_delay * (backoff_factor ** (retry_count - 1))
                logger.error(f"SSL/TLS握手失败: {e}{proxy_info}")
                logger.error(f"请求详情: {method} {url}")
                logger.error(f"这可能是DPI拦截导致的SSL握手重置，请检查代理配置或尝试更换代理")
                
                if retry_count < max_retries:
                    logger.info(f"{delay}秒后重试请求")
                    time.sleep(delay)
                else:
                    logger.error(f"请求重试次数耗尽: {method} {url}{proxy_info}")
                    raise
            except ConnectionResetError as e:
                retry_count += 1
                delay = initial_delay * (backoff_factor ** (retry_count - 1))
                logger.error(f"连接被远程服务器重置: {e}{proxy_info}")
                logger.error(f"请求详情: {method} {url}")
                logger.error(f"这可能是DPI拦截或服务器限流导致的，请检查代理配置或降低请求频率")
                
                if retry_count < max_retries:
                    logger.info(f"{delay}秒后重试请求")
                    time.sleep(delay)
                else:
                    logger.error(f"请求重试次数耗尽: {method} {url}{proxy_info}")
                    raise
            except requests.exceptions.RequestException as e:
                retry_count += 1
                delay = initial_delay * (backoff_factor ** (retry_count - 1))
                
                # 记录失败
                logger.error(f"HTTP请求失败: {e}{proxy_info}")
                logger.error(f"请求详情: {method} {url}")
                
                # 检查是否需要重试
                if retry_count < max_retries:
                    logger.info(f"{delay}秒后重试请求")
                    time.sleep(delay)
                else:
                    logger.error(f"请求重试次数耗尽: {method} {url}{proxy_info}")
                    raise


# 导入time模块
def __import_time():
    global time
    import time


# 确保time模块被导入
__import_time()
