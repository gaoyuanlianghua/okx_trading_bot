import os
import time
import json
import socket
import ssl
import requests
import hmac
import base64
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from threading import Lock
from cachetools import TTLCache

# 初始化日志配置
from commons.logger_config import global_logger as logger
from urllib.parse import urlparse, urlencode

# DNS解析白名单，仅允许解析这些域名
DNS_WHITELIST = ['www.okx.com', 'ws.okx.com', 'okx.com']

# DNS解析结果缓存，TTL为5分钟
DNS_CACHE = TTLCache(maxsize=1000, ttl=300)

# DNS解析统计信息
DNS_STATS = {
    'total_queries': 0,       # 总查询次数
    'successful_queries': 0,   # 成功查询次数
    'failed_queries': 0,       # 失败查询次数
    'cached_queries': 0,       # 缓存命中次数
    'resolve_time': [],        # 解析时间列表
    'server_performance': {}   # 服务器性能统计 {server: {'success': 0, 'failure': 0, 'time': []}}
}

# DNS解析告警配置
DNS_ALERTS = {
    'failure_rate_threshold': 0.2,  # 失败率阈值，超过则告警
    'alert_count': 0,                # 告警次数
    'last_alert_time': 0             # 上次告警时间
}

# 多地域DNS服务器配置
MULTI_REGION_DNS_SERVERS = {
    'global': ['1.1.1.1', '1.0.0.1'],
    'asia': ['8.8.8.8', '8.8.4.4'],
    'europe': ['9.9.9.9', '149.112.112.112'],
    'north_america': ['208.67.222.222', '208.67.220.220']
}

# 当前使用的DNS服务器配置
CURRENT_DNS_CONFIG = {
    'servers': MULTI_REGION_DNS_SERVERS['global'],
    'region': 'global',
    'timeout': 5,
    'retry_count': 3,
    'failure_rate_threshold': 0.2,
    'use_custom_dns': True  # 是否使用自定义DNS解析
}

# 验证域名格式
import re
def validate_domain(domain):
    """
    验证域名格式是否合法，防止DNS注入攻击
    
    Args:
        domain (str): 要验证的域名
        
    Returns:
        bool: 域名是否合法
    """
    if not domain or not isinstance(domain, str):
        return False
    
    # 域名格式正则表达式，防止DNS注入
    domain_pattern = r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(domain_pattern, domain):
        return False
    
    # 检查是否在白名单中
    if domain not in DNS_WHITELIST:
        logger.warning(f"域名 {domain} 不在DNS白名单中，拒绝解析")
        return False
    
    return True

# 自定义DNS解析函数，优先使用系统DNS，支持DoH/DoT作为备选
def custom_dns_resolve(hostname, dns_servers=None):
    """
    使用系统DNS优先解析主机名，失败时尝试DoH/DoT加密传输
    
    Args:
        hostname (str): 要解析的主机名
        dns_servers (list, optional): DNS服务器列表，默认使用当前配置的服务器
        
    Returns:
        str: 解析到的IP地址，如果解析失败则返回None
    """
    # 更新统计信息：总查询次数
    DNS_STATS['total_queries'] += 1
    
    # 验证域名格式和白名单
    if not validate_domain(hostname):
        logger.error(f"无效的域名: {hostname}")
        DNS_STATS['failed_queries'] += 1
        check_dns_health()
        return None
    
    # 检查缓存，如果存在则直接返回
    if hostname in DNS_CACHE:
        cached_ip = DNS_CACHE[hostname]
        logger.debug(f"从缓存中获取 {hostname} 的IP: {cached_ip}")
        DNS_STATS['cached_queries'] += 1
        DNS_STATS['successful_queries'] += 1
        return cached_ip
    
    resolved_ip = None
    resolve_start_time = time.time()
    
    # 1. 优先使用系统DNS解析（最可靠）
    try:
        logger.debug(f"优先使用系统DNS解析 {hostname}")
        ip = socket.gethostbyname(hostname)
        # 检查是否为有效IP（非APIPA地址）
        if not ip.startswith('169.254.') and ip != '0.0.0.0' and ip != '255.255.255.255':
            logger.debug(f"系统DNS解析 {hostname} 到 {ip} 成功")
            resolved_ip = ip
        else:
            logger.warning(f"系统DNS返回无效IP {ip} 解析 {hostname}")
    except socket.gaierror as e:
        logger.warning(f"系统DNS解析 {hostname} 失败: {e}")
    
    # 2. 如果系统DNS解析失败，尝试使用dnspython进行传统DNS查询
    if not resolved_ip:
        try:
            import dns.resolver
            
            logger.debug(f"系统DNS解析失败，尝试使用dnspython进行传统DNS查询 {hostname}")
            resolver = dns.resolver.Resolver()
            resolver.timeout = CURRENT_DNS_CONFIG['timeout']
            resolver.lifetime = CURRENT_DNS_CONFIG['timeout'] * CURRENT_DNS_CONFIG['retry_count']
            
            # 解析A记录
            answers = resolver.resolve(hostname, 'A', raise_on_no_answer=False)
            if answers.rdset:
                for rdata in answers:
                    ip = str(rdata.address)
                    # 检查是否为有效IP（非APIPA地址）
                    if not ip.startswith('169.254.') and ip != '0.0.0.0' and ip != '255.255.255.255':
                        logger.debug(f"使用dnspython解析 {hostname} 到 {ip} 成功")
                        resolved_ip = ip
                        break
        except ImportError:
            logger.debug("dnspython未安装，跳过传统DNS查询")
        except Exception as e:
            logger.debug(f"dnspython解析 {hostname} 失败: {e}")
    
    # 3. 如果仍失败，尝试DoH/DoT（作为最后的备选）
    if not resolved_ip:
        try:
            import dns.resolver
            import dns.flags
            import dns.query
            import dns.message
            
            # 使用默认DNS服务器配置
            if dns_servers is None:
                dns_servers = CURRENT_DNS_CONFIG['servers']
            
            # 优先使用可靠的DNS服务器
            reliable_dns_servers = ['1.1.1.1', '1.0.0.1', '208.67.222.222', '208.67.220.220']
            all_dns_servers = reliable_dns_servers + [s for s in dns_servers if s not in reliable_dns_servers]
            
            # 支持DoH的DNS服务器
            doh_servers = {
                '1.1.1.1': 'https://1.1.1.1/dns-query',
                '1.0.0.1': 'https://1.0.0.1/dns-query',
                '8.8.8.8': 'https://dns.google/dns-query',
                '8.8.4.4': 'https://dns.google/dns-query',
                '208.67.222.222': 'https://dns.opendns.com/dns-query',
                '208.67.220.220': 'https://dns.opendns.com/dns-query'
            }
            
            # 尝试DoH
            for server in all_dns_servers:
                if server in doh_servers:
                    try:
                        logger.debug(f"尝试使用DoH服务器 {server} 解析 {hostname}")
                        # 构建DNS查询消息
                        query = dns.message.make_query(hostname, dns.rdatatype.A)
                        
                        # 使用DoH查询
                        response = dns.query.https(query, doh_servers[server], timeout=CURRENT_DNS_CONFIG['timeout'])
                        
                        # 解析响应
                        for answer in response.answer:
                            if answer.rdtype == dns.rdatatype.A:
                                for rdata in answer:
                                    ip = str(rdata.address)
                                    if not ip.startswith('169.254.') and ip != '0.0.0.0' and ip != '255.255.255.255':
                                        logger.debug(f"使用DoH服务器 {server} 解析 {hostname} 到 {ip}")
                                        resolved_ip = ip
                                        break
                            if resolved_ip:
                                break
                        if resolved_ip:
                            break
                    except Exception as e:
                        logger.debug(f"DoH服务器 {server} 解析 {hostname} 失败: {e}")
                        continue
            
            # 尝试DoT
            if not resolved_ip:
                for server in all_dns_servers:
                    try:
                        logger.debug(f"尝试使用DoT服务器 {server} 解析 {hostname}")
                        # 构建DNS查询消息
                        query = dns.message.make_query(hostname, dns.rdatatype.A)
                        
                        # 使用DoT查询
                        response = dns.query.tls(query, server, timeout=CURRENT_DNS_CONFIG['timeout'])
                        
                        # 解析响应
                        for answer in response.answer:
                            if answer.rdtype == dns.rdatatype.A:
                                for rdata in answer:
                                    ip = str(rdata.address)
                                    if not ip.startswith('169.254.') and ip != '0.0.0.0' and ip != '255.255.255.255':
                                        logger.debug(f"使用DoT服务器 {server} 解析 {hostname} 到 {ip}")
                                        resolved_ip = ip
                                        break
                            if resolved_ip:
                                break
                        if resolved_ip:
                            break
                    except Exception as e:
                        logger.debug(f"DoT服务器 {server} 解析 {hostname} 失败: {e}")
                        continue
        except ImportError:
            logger.debug("dnspython未安装，跳过DoH/DoT解析")
        except Exception as e:
            logger.error(f"DoH/DoT解析失败: {e}")
    
    # 计算解析时间
    resolve_time = time.time() - resolve_start_time
    DNS_STATS['resolve_time'].append(resolve_time)
    
    # 更新统计信息
    if resolved_ip:
        DNS_STATS['successful_queries'] += 1
        # 将解析结果保存到缓存
        DNS_CACHE[hostname] = resolved_ip
        logger.debug(f"将 {hostname} -> {resolved_ip} 保存到DNS缓存")
    else:
        DNS_STATS['failed_queries'] += 1
        logger.error(f"所有DNS解析方法均失败: {hostname}")
    
    # 检查DNS健康状况，触发告警
    check_dns_health()
    
    return resolved_ip

# 更新DNS服务器性能统计
def update_server_performance(server, success, resolve_time):
    """
    更新DNS服务器性能统计信息
    
    Args:
        server (str): DNS服务器IP
        success (bool): 是否解析成功
        resolve_time (float): 解析耗时（秒）
    """
    if server not in DNS_STATS['server_performance']:
        DNS_STATS['server_performance'][server] = {
            'success': 0,
            'failure': 0,
            'time': []
        }
    
    if success:
        DNS_STATS['server_performance'][server]['success'] += 1
    else:
        DNS_STATS['server_performance'][server]['failure'] += 1
    
    DNS_STATS['server_performance'][server]['time'].append(resolve_time)

# 检查DNS健康状况，触发告警
def check_dns_health():
    """
    检查DNS解析健康状况，如果失败率超过阈值则触发告警
    """
    total = DNS_STATS['total_queries']
    if total < 10:  # 至少10次查询才检查健康状况
        return
    
    failure_rate = DNS_STATS['failed_queries'] / total
    if failure_rate > DNS_ALERTS['failure_rate_threshold']:
        current_time = time.time()
        # 避免频繁告警，至少间隔5分钟
        if current_time - DNS_ALERTS['last_alert_time'] > 300:
            logger.warning(f"DNS解析失败率过高: {failure_rate:.2%}，超过阈值 {DNS_ALERTS['failure_rate_threshold']:.2%}")
            logger.warning(f"DNS统计信息: {DNS_STATS}")
            DNS_ALERTS['alert_count'] += 1
            DNS_ALERTS['last_alert_time'] = current_time

# 异步DNS解析函数，使用aiodns库实现异步非阻塞查询
async def async_custom_dns_resolve(hostname, dns_servers=None):
    """
    异步使用指定的DNS服务器解析主机名，支持DNSSEC验证和DoH/DoT加密传输
    
    Args:
        hostname (str): 要解析的主机名
        dns_servers (list, optional): DNS服务器列表，默认使用当前配置的服务器
        
    Returns:
        str: 解析到的IP地址，如果解析失败则返回None
    """
    # 更新统计信息：总查询次数
    DNS_STATS['total_queries'] += 1
    
    # 验证域名格式和白名单
    if not validate_domain(hostname):
        logger.error(f"无效的域名: {hostname}")
        DNS_STATS['failed_queries'] += 1
        check_dns_health()
        return None
    
    # 检查缓存，如果存在则直接返回
    if hostname in DNS_CACHE:
        cached_ip = DNS_CACHE[hostname]
        logger.debug(f"从缓存中获取 {hostname} 的IP: {cached_ip}")
        DNS_STATS['cached_queries'] += 1
        DNS_STATS['successful_queries'] += 1
        return cached_ip
    
    # 使用默认DNS服务器配置
    if dns_servers is None:
        dns_servers = CURRENT_DNS_CONFIG['servers']
    
    resolve_start_time = time.time()
    resolved_ip = None
    
    try:
        import aiodns
        
        # 创建异步DNS解析器
        resolver = aiodns.DNSResolver(nameservers=dns_servers, timeout=CURRENT_DNS_CONFIG['timeout'])
        
        # 异步解析A记录
        result = await resolver.query(hostname, 'A')
        
        # 从解析结果中获取IP地址
        for answer in result:
            ip = answer.host
            if not ip.startswith('169.254.') and ip != '0.0.0.0' and ip != '255.255.255.255':
                logger.debug(f"使用异步DNS解析 {hostname} 到 {ip}")
                resolved_ip = ip
                break
    except ImportError:
        logger.warning("aiodns未安装，使用同步DNS解析")
        # 回退到同步DNS解析
        resolved_ip = custom_dns_resolve(hostname, dns_servers)
        return resolved_ip
    except Exception as e:
        logger.error(f"异步DNS解析失败: {e}")
    
    # 计算解析时间
    resolve_time = time.time() - resolve_start_time
    DNS_STATS['resolve_time'].append(resolve_time)
    
    # 更新统计信息
    if resolved_ip:
        DNS_STATS['successful_queries'] += 1
        # 将解析结果保存到缓存
        DNS_CACHE[hostname] = resolved_ip
        logger.debug(f"将 {hostname} -> {resolved_ip} 保存到DNS缓存")
    else:
        DNS_STATS['failed_queries'] += 1
    
    # 检查DNS健康状况，触发告警
    check_dns_health()
    
    return resolved_ip

# 更新DNS配置
def update_dns_config(new_config):
    """
    动态更新DNS配置
    
    Args:
        new_config (dict): 新的DNS配置
    
    Returns:
        bool: 更新是否成功
    """
    global CURRENT_DNS_CONFIG
    
    try:
        # 验证配置格式
        valid_keys = ['servers', 'region', 'timeout', 'retry_count', 'failure_rate_threshold', 'use_custom_dns']
        for key in new_config:
            if key not in valid_keys:
                logger.error(f"无效的DNS配置项: {key}")
                return False
        
        # 更新配置
        CURRENT_DNS_CONFIG.update(new_config)
        
        # 如果指定了region，更新servers
        if 'region' in new_config and new_config['region'] in MULTI_REGION_DNS_SERVERS:
            CURRENT_DNS_CONFIG['servers'] = MULTI_REGION_DNS_SERVERS[new_config['region']]
        
        logger.info(f"DNS配置已更新: {CURRENT_DNS_CONFIG}")
        return True
    except Exception as e:
        logger.error(f"更新DNS配置失败: {e}")
        return False

# 切换DNS区域
def switch_dns_region(region):
    """
    切换DNS服务器区域
    
    Args:
        region (str): 区域名称
    
    Returns:
        bool: 切换是否成功
    """
    if region not in MULTI_REGION_DNS_SERVERS:
        logger.error(f"无效的DNS区域: {region}")
        return False
    
    return update_dns_config({'region': region})

# 获取DNS统计信息
def get_dns_stats():
    """
    获取DNS解析统计信息
    
    Returns:
        dict: DNS解析统计信息
    """
    # 计算平均解析时间
    avg_time = 0
    if DNS_STATS['resolve_time']:
        avg_time = sum(DNS_STATS['resolve_time']) / len(DNS_STATS['resolve_time'])
    
    # 计算总查询次数和成功率
    total = DNS_STATS['total_queries']
    success_rate = 0
    if total > 0:
        success_rate = DNS_STATS['successful_queries'] / total
    
    # 计算缓存命中率
    cache_hit_rate = 0
    if total > 0:
        cache_hit_rate = DNS_STATS['cached_queries'] / total
    
    return {
        'total_queries': total,
        'successful_queries': DNS_STATS['successful_queries'],
        'failed_queries': DNS_STATS['failed_queries'],
        'cached_queries': DNS_STATS['cached_queries'],
        'success_rate': success_rate,
        'cache_hit_rate': cache_hit_rate,
        'average_resolve_time': avg_time,
        'server_performance': DNS_STATS['server_performance'],
        'alerts': {
            'count': DNS_ALERTS['alert_count'],
            'failure_rate_threshold': DNS_ALERTS['failure_rate_threshold']
        },
        'current_config': CURRENT_DNS_CONFIG
    }

# 重置DNS统计信息
def reset_dns_stats():
    """
    重置DNS解析统计信息
    """
    global DNS_STATS
    global DNS_ALERTS
    
    DNS_STATS = {
        'total_queries': 0,
        'successful_queries': 0,
        'failed_queries': 0,
        'cached_queries': 0,
        'resolve_time': [],
        'server_performance': {}
    }
    
    DNS_ALERTS = {
        'failure_rate_threshold': 0.2,
        'alert_count': 0,
        'last_alert_time': 0
    }
    
    logger.info("DNS统计信息已重置")

from okx.exceptions import OkxAPIException

from urllib3.connection import HTTPSConnection
from urllib3.poolmanager import PoolManager
from urllib3.exceptions import SSLError


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



# 自定义HTTP连接，支持DNS绕过和SSL验证
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

# 自定义连接池管理器，使用CustomHTTPSConnection
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

# 自定义HTTP适配器，使用可靠的DNS解析和正确的SSL验证
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
        
        # 补丁socket.getaddrinfo函数，使用我们的自定义DNS解析
        socket.getaddrinfo = custom_getaddrinfo
        logger.info("已启用自定义DNS解析")
    
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
            except requests.exceptions.ConnectionResetError as e:
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

def retry_with_backoff(max_retries=3, initial_delay=0.5, backoff_factor=2, exceptions=(Exception,)):
    """
    重试装饰器，支持指数退避策略
    
    Args:
        max_retries (int): 最大重试次数
        initial_delay (float): 初始延迟（秒）
        backoff_factor (float): 退避因子
        exceptions (tuple): 要捕获并重试的异常类型
    
    Returns:
        function: 装饰后的函数
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(f"重试次数耗尽，函数 {func.__name__} 执行失败: {e}")
                        raise
                    logger.warning(f"函数 {func.__name__} 执行失败（尝试 {attempt+1}/{max_retries+1}）: {e}")
                    logger.info(f"{delay} 秒后重试...")
                    time.sleep(delay)
                    delay *= backoff_factor
        return wrapper
    return decorator

class OKXAPIClient:
    """OKX API客户端封装，简化API调用和认证管理"""
    
    def __init__(self, api_key=None, api_secret=None, passphrase=None, is_test=False, api_url=None, api_ip=None, api_ips=None, timeout=30, proxy=None):
        """
        初始化OKX API客户端
        
        Args:
            api_key (str, optional): OKX API密钥
            api_secret (str, optional): OKX API密钥密码
            passphrase (str, optional): OKX API密钥短语
            is_test (bool, optional): 是否使用测试网
            api_url (str, optional): 自定义OKX API URL
            api_ip (str, optional): OKX API服务器IP地址（已废弃）
            api_ips (list, optional): OKX API服务器IP地址列表（已废弃）
            timeout (int, optional): API请求超时时间，单位秒，默认30秒
            proxy (dict, optional): 代理配置，格式: {"enabled": bool, "http": str, "https": str, "socks5": str}
        """
        # 加载环境变量
        load_dotenv()
        
        # 使用全局配置管理器获取配置
        api_config = {}
        try:
            from commons.config_manager import global_config_manager
            self.config_manager = global_config_manager
            api_config = self.config_manager.get("api", {})
            logger.info("从配置管理器加载API配置成功")
        except ImportError as e:
            logger.warning(f"无法导入配置管理器，将使用本地配置加载: {e}")
            # 回退到本地配置文件加载
            config_path = os.path.join(os.path.dirname(__file__), 'config', 'okx_config.json')
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                api_config = config.get('api', {})
                logger.info(f"从配置文件加载配置成功: {config_path}")
            except Exception as ex:
                logger.warning(f"回退配置文件加载也失败: {ex}")
        except Exception as e:
            logger.error(f"从配置管理器加载配置失败: {e}")
        
        # WebSocket配置
        self.ws_ip = api_config.get('ws_ip')
        self.ws_ips = api_config.get('ws_ips', [])
        self.ws_open_timeout = api_config.get('ws_open_timeout', 15.0)
        self.ws_ping_timeout = api_config.get('ws_ping_timeout', 10.0)
        self.ws_close_timeout = api_config.get('ws_close_timeout', 5.0)
        self.ws_max_queue = api_config.get('ws_max_queue', 1000)
        self.ws_ping_interval = api_config.get('ws_ping_interval', 30.0)
        
        # 设置API密钥
        self.api_key = api_key or os.getenv('OKX_API_KEY') or api_config.get('api_key') or '-1'
        self.api_secret = api_secret or os.getenv('OKX_API_SECRET') or api_config.get('api_secret') or '-1'
        self.passphrase = passphrase or os.getenv('OKX_PASSPHRASE') or api_config.get('passphrase') or '-1'
        self.is_test = is_test
        self.timeout = timeout or int(os.getenv('OKX_API_TIMEOUT', '30')) or api_config.get('timeout', 30)
        
        # API URL - 优先使用传入的api_url，然后是环境变量，最后是默认值
        # 模拟盘和实盘使用相同的REST API URL，但需要添加x-simulated-trading: 1请求头
        self.api_url = api_url or os.getenv('OKX_API_URL') or api_config.get('api_url') or 'https://www.okx.com'
        
        # 解析URL，获取主机名和路径
        self.parsed_url = urlparse(self.api_url)
        self.host_name = self.parsed_url.netloc
        self.base_path = self.parsed_url.path
        
        # API版本，当前OKX API版本为v5
        self.api_version = "v5"
        
        # 处理代理配置：优先使用构造函数传入的proxy参数，否则使用配置文件设置
        if proxy:
            self.proxy_config = proxy
            self.proxy_enabled = proxy.get('enabled', False)
            logger.info(f"使用构造函数传入的代理配置: {self.proxy_config}")
        else:
            # 加载配置文件中的代理设置
            self.proxy_config = api_config.get('proxy', {})
            self.proxy_enabled = self.proxy_config.get('enabled', False)
            logger.info(f"使用配置文件中的代理配置: {self.proxy_config}")
        
        # 详细记录代理配置
        logger.debug(f"代理配置详细信息: 启用={self.proxy_enabled}, SOCKS5={self.proxy_config.get('socks5', '未配置')}, HTTPS={self.proxy_config.get('https', '未配置')}, HTTP={self.proxy_config.get('http', '未配置')}")
        
        # 创建自定义会话，支持可靠DNS解析、重试机制和代理
        self.session = DNSBypassingSession(
            retry_count=3,
            backoff_factor=0.5
        )
        self.session.timeout = self.timeout
        
        # 自定义SSL上下文，伪装TLS指纹
        import ssl
        ssl_context = ssl.create_default_context()
        # 强制使用TLS 1.2（避免TLS 1.3的特征被识别）
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        ssl_context.maximum_version = ssl.TLSVersion.TLSv1_2
        # 使用常见的加密套件（避免冷门套件被标记）
        ssl_context.set_ciphers("ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256")
        # 关闭会话复用（减少特征），兼容不同Python版本
        if hasattr(ssl, 'OP_NO_SESSION_RESUMPTION_ON_RECONNECT'):
            ssl_context.options |= ssl.OP_NO_SESSION_RESUMPTION_ON_RECONNECT
        # 禁用旧版本协议和不安全特性
        ssl_context.options |= ssl.OP_NO_SSLv2
        ssl_context.options |= ssl.OP_NO_SSLv3
        ssl_context.options |= ssl.OP_NO_TLSv1
        ssl_context.options |= ssl.OP_NO_TLSv1_1
        
        # 创建带有重试策略的HTTP适配器
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE"],
            backoff_factor=2,  # 指数退避因子
            respect_retry_after_header=True
        )
        
        # 应用SSL上下文，修复旧版本requests库不支持ssl_context参数的问题
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=20,  # 增加连接池大小
            pool_maxsize=20,     # 增加连接池最大大小
            pool_block=False
        )
        adapter._ssl_context = ssl_context
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)
        
        # 设置会话超时
        self.session.timeout = self.timeout  # 使用配置文件中的超时时间
        self.session.trust_env = True  # 信任环境变量中的代理设置
        
        # 添加合规浏览器请求头，伪装流量特征
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Origin": self.api_url,
            "Referer": f"{self.api_url}/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        })
        
        logger.info(f"已配置API客户端超时时间: {self.timeout}秒")
        logger.info(f"已配置HTTP适配器重试策略: {retry_strategy}")
        
        # 配置代理
        self.active_proxy_url = None
        if self.proxy_enabled:
            # 优先级：socks5 > https > http
            for proxy_type in ['socks5', 'https', 'http']:
                proxy_url = self.proxy_config.get(proxy_type)
                if proxy_url:
                    self.active_proxy_url = proxy_url
                    
                    # 应用代理配置到主会话
                    self.session.proxies = {
                        'http': proxy_url,
                        'https': proxy_url
                    }
                    logger.info(f"已配置{proxy_type.upper()}代理: {proxy_url}")
                    break
            
            if not self.active_proxy_url:
                logger.warning("代理已启用，但未配置任何可用的代理地址")
                self.proxy_enabled = False
                self.session.proxies = {}
        else:
            logger.info("未启用代理")
            self.session.proxies = {}
        
        # 添加线程锁，确保线程安全
        self._lock = Lock()
        
        # 初始化状态标志
        self.initialized = False
        self.initialization_error = None
        
        logger.info(f"OKX API客户端初始化完成，测试网: {is_test}，超时时间: {self.timeout}秒")
        logger.info(f"API URL: {self.api_url}")
        logger.info("使用可靠DNS解析，通过自定义DNS服务器确保连接稳定性")
        
        # 异步初始化网络相关配置
        self.async_init()
    
    def async_init(self):
        """异步初始化网络相关配置，避免阻塞主线程"""
        def init_thread():
            try:
                # 自动配置DNS解析IP
                self.auto_configure_dns()
                
                # 测试网络连接
                self.test_network_connection()
                
                self.initialized = True
                logger.info("OKX API客户端网络初始化完成")
            except Exception as e:
                self.initialization_error = str(e)
                logger.error(f"OKX API客户端网络初始化失败: {e}")
        
        import threading
        thread = threading.Thread(target=init_thread)
        thread.daemon = True
        thread.start()
    
    def get_current_ip(self):
        """获取当前活跃的API IP地址"""
        try:
            # 从配置文件获取当前API IP
            config_path = os.path.join(os.path.dirname(__file__), 'config/okx_config.json')
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # 优先返回配置的api_ip，如果没有则返回api_ips列表中的第一个
            api_ip = config['api'].get('api_ip')
            if api_ip:
                return api_ip
            
            api_ips = config['api'].get('api_ips', [])
            if api_ips:
                return api_ips[0]
            
            return None
        except Exception as e:
            logger.error(f"获取当前IP失败: {e}")
            return None
    
    def get_network_status(self):
        """
        获取当前网络状态
        """
        return {
            "current_ip": self.get_current_ip(),
            "response_times": self.get_ip_response_times(),
            "dns_stats": self.get_dns_stats(),
            "connection_status": self.test_network_connection()
        }
    
    def verify_api_key(self):
        """
        验证API密钥有效性
        
        Returns:
            dict: 验证结果，包含status和message字段
        """
        try:
            logger.info(f"正在验证API密钥有效性，API URL: {self.api_url}")
            
            # 使用账户余额接口验证API密钥
            path = f"/api/{self.api_version}/account/balance"
            method = "GET"
            
            # 生成签名
            timestamp = str(time.time())
            message = f"{timestamp}{method}{path}"
            mac = hmac.new(bytes(self.api_secret, 'utf-8'), bytes(message, 'utf-8'), hashlib.sha256)
            signature = base64.b64encode(mac.digest()).decode()
            
            # 准备请求头
            headers = {
                "OK-ACCESS-KEY": self.api_key,
                "OK-ACCESS-SIGN": signature,
                "OK-ACCESS-TIMESTAMP": timestamp,
                "OK-ACCESS-PASSPHRASE": self.passphrase,
                "Content-Type": "application/json"
            }
            
            # 发送请求
            url = f"{self.api_url}{path}"
            response = self.session.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            # 解析响应
            result = response.json()
            if result.get("code") == "0":
                logger.info("API密钥验证成功")
                return {
                    "status": "success",
                    "message": "API密钥验证成功",
                    "data": result.get("data")
                }
            else:
                error_msg = result.get("msg", "未知错误")
                logger.error(f"API密钥验证失败: {error_msg}")
                return {
                    "status": "error",
                    "message": f"API密钥验证失败: {error_msg}",
                    "code": result.get("code")
                }
        except requests.exceptions.ConnectionResetError as e:
            logger.error(f"API密钥验证时连接被重置: {e}")
            return {
                "status": "error",
                "message": f"连接被远程服务器重置: {e}",
                "hint": "这可能是DPI拦截或服务器限流导致的，请检查代理配置或降低请求频率"
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"API密钥验证失败: {e}")
            return {
                "status": "error",
                "message": f"请求失败: {e}"
            }
        except Exception as e:
            logger.error(f"API密钥验证过程中发生未知错误: {e}")
            return {
                "status": "error",
                "message": f"未知错误: {e}"
            }
    
    def auto_configure_dns(self):
        """
        自动配置DNS解析IP，将解析结果保存到环境变量中
        """
        logger.info("自动配置DNS解析IP...")
        
        try:
            # 解析OKX API域名
            okx_ips = []
            for domain in DNS_WHITELIST:
                ip = custom_dns_resolve(domain)
                if ip:
                    okx_ips.append(ip)
                    logger.info(f"解析 {domain} 到 {ip}")
            
            # 去重并转换为逗号分隔的字符串
            unique_ips = list(set(okx_ips))
            ips_str = ",".join(unique_ips)
            
            # 设置环境变量
            os.environ["OKX_API_IPS"] = ips_str
            logger.info(f"已设置环境变量 OKX_API_IPS: {ips_str}")
            
            # 写入配置文件
            self.write_dns_config(unique_ips)
            
        except Exception as e:
            logger.error(f"自动配置DNS解析IP失败: {e}")
    
    def write_dns_config(self, ips):
        """
        将DNS解析结果写入配置文件
        
        Args:
            ips (list): 解析到的IP地址列表
        """
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'config/okx_config.json')
            
            # 读取现有配置
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # 更新配置
            if 'api' not in config:
                config['api'] = {}
            config['api']['api_ips'] = ips
            
            # 写入配置文件
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"已更新配置文件，添加API IP地址: {ips}")
        except Exception as e:
            logger.error(f"写入DNS配置失败: {e}")
    
    def test_network_connection(self):
        """测试网络连接"""
        logger.info("测试网络连接...")
        
        try:
            # 测试DNS解析
            logger.info(f"正在解析主机名: {self.host_name}")
            ip = custom_dns_resolve(self.host_name)
            if not ip:
                logger.error(f"无法解析主机名: {self.host_name}")
                logger.error("可能的原因:")
                logger.error("1. 系统DNS配置问题")
                logger.error("2. 网络环境对DNS查询的拦截")
                logger.error("3. 域名不存在或已过期")
                logger.error("建议: 检查网络连接或禁用自定义DNS解析")
                return False
            
            logger.info(f"DNS解析成功: {self.host_name} -> {ip}")
            
            # 测试socket连接
            logger.info(f"正在测试Socket连接: {ip}:443")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((ip, 443))
            s.close()
            
            logger.info(f"Socket连接成功: {ip}:443")
            
            # 测试SSL握手
            logger.info(f"正在测试SSL握手: {ip}:443")
            context = ssl.create_default_context()
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
            
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((ip, 443))
            
            ssl_sock = context.wrap_socket(s, server_hostname=self.host_name)
            ssl_sock.close()
            s.close()
            
            logger.info(f"SSL握手成功: {ip}:443")
            logger.info("网络连接测试通过")
            return True
            
        except ssl.SSLError as e:
            logger.error(f"SSL握手失败: {e}")
            logger.error("可能的原因:")
            logger.error("1. 防火墙或代理服务器阻止了SSL连接")
            logger.error("2. SSL证书验证失败")
            logger.error("3. 网络环境问题")
            logger.error("4. 服务器配置问题")
            logger.error("建议: 检查网络连接或使用代理服务器")
            logger.error(f"详细错误信息: {type(e).__name__}: {e}")
            return False
        except socket.timeout:
            logger.error(f"连接超时: 无法连接到 {ip if 'ip' in locals() else self.host_name}:443")
            logger.error("可能的原因:")
            logger.error("1. 网络延迟过高")
            logger.error("2. 服务器负载过高")
            logger.error("3. 防火墙或代理服务器阻止了连接")
            logger.error("建议: 检查网络连接或调整超时时间")
            return False
        except socket.error as e:
            logger.error(f"网络连接失败: {e}")
            logger.error("可能的原因:")
            logger.error("1. 网络连接断开")
            logger.error("2. 服务器不可用")
            logger.error("3. 防火墙或代理服务器阻止了连接")
            logger.error("建议: 检查网络连接或API服务器状态")
            logger.error(f"详细错误信息: {type(e).__name__}: {e}")
            return False
        except Exception as e:
            logger.error(f"网络连接测试失败: {e}")
            logger.error("可能的原因:")
            logger.error("1. 未知的网络错误")
            logger.error("2. 代码逻辑错误")
            logger.error("3. 依赖库问题")
            logger.error("建议: 检查日志详细信息或联系开发者")
            logger.error(f"详细错误信息: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            return False
    
    def run_network_adapter(self, auto_update=True):
        """运行网络自动适配脚本
        
        Args:
            auto_update (bool): 是否自动更新配置文件
            
        Returns:
            bool: 执行是否成功
        """
        import subprocess
        import os
        
        logger.info("运行网络自动适配脚本...")
        
        # 构建PowerShell命令
        script_path = os.path.join(os.path.dirname(__file__), "AutoNetworkAdapter.ps1")
        auto_update_param = "true" if auto_update else "false"
        
        # 执行PowerShell脚本
        command = [
            "powershell",
            "-ExecutionPolicy", "Bypass",
            "-File", script_path,
            "-AutoUpdate", auto_update_param
        ]
        
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=os.path.dirname(__file__),
                timeout=60
            )
            
            logger.info(f"网络自动适配脚本执行结果: {result.returncode}")
            logger.debug(f"脚本输出: {result.stdout}")
            if result.stderr:
                logger.error(f"脚本错误: {result.stderr}")
            
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.error("网络自动适配脚本执行超时")
            return False
        except Exception as e:
            logger.error(f"执行网络自动适配脚本失败: {e}")
            return False
    
    def switch_to_next_ip(self):
        """切换到下一个API IP地址（已废弃）"""
        return None
    
    def switch_to_fastest_ip(self):
        """切换到响应时间最快的API IP地址（已废弃）"""
        return None
    
    def get_ip_response_times(self):
        """获取各IP地址的响应时间"""
        return self.session.ip_response_times
    
    def get_dns_stats(self):
        """
        获取DNS解析统计信息
        
        Returns:
            dict: DNS解析统计信息
        """
        return get_dns_stats()
    
    def reset_dns_stats(self):
        """
        重置DNS解析统计信息
        """
        reset_dns_stats()
    
    def switch_dns_region(self, region):
        """
        切换DNS服务器区域
        
        Args:
            region (str): 区域名称，可选值: global, asia, europe, north_america
            
        Returns:
            bool: 切换是否成功
        """
        return switch_dns_region(region)
    
    def update_dns_config(self, new_config):
        """
        动态更新DNS配置
        
        Args:
            new_config (dict): 新的DNS配置
            
        Returns:
            bool: 更新是否成功
        """
        return update_dns_config(new_config)
    
    def get_dns_config(self):
        """
        获取当前DNS配置
        
        Returns:
            dict: 当前DNS配置
        """
        return CURRENT_DNS_CONFIG.copy()
    
    def _generate_signature(self, timestamp, method, request_path, body):
        """
        生成OKX API签名
        
        Args:
            timestamp (str): 时间戳
            method (str): HTTP方法（GET/POST）
            request_path (str): 请求路径
            body (str): 请求体（JSON字符串）
        
        Returns:
            str: 签名
        """
        # 确保method全部大写
        method = method.upper()
        
        # 拼接字符串，GET请求body为空字符串
        message = timestamp + method + request_path + body
        
        # 生成HMAC SHA256签名
        mac = hmac.new(bytes(self.api_secret, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
        d = mac.digest()
        
        # Base64编码
        return base64.b64encode(d).decode()
    
    def _get_headers(self, timestamp, sign, exp_time=None):
        """
        获取API请求头
        
        Args:
            timestamp (str): 时间戳
            sign (str): 签名
            exp_time (str, optional): 请求有效截止时间
        
        Returns:
            dict: 请求头
        """
        headers = {
            "Content-Type": "application/json",
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
        }
        
        # 模拟盘添加请求头
        if self.is_test:
            headers["x-simulated-trading"] = "1"
        
        # 添加请求有效截止时间
        if exp_time:
            headers["expTime"] = exp_time
            
        return headers
    
    def _get_public_headers(self):
        """
        获取公共API请求头（不需要签名）
        
        Returns:
            dict: 请求头
        """
        return {
            "Content-Type": "application/json",
        }
    
    def _get_timestamp(self):
        """
        获取当前时间戳
        
        Returns:
            str: ISO格式的时间戳
        """
        return time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
    
    def _request(self, method, endpoint, params=None, need_sign=True, exp_time=None):
        """
        发送API请求
        
        Args:
            method (str): HTTP方法（GET/POST）
            endpoint (str): API端点（如"public/ticker"）
            params (dict): 请求参数
            need_sign (bool): 是否需要签名
            exp_time (str, optional): 请求有效截止时间
        
        Returns:
            dict: API响应
        """
        # 构建请求URL
        request_path = f"{self.base_path}/api/{self.api_version}/{endpoint}"
        url = f"{self.parsed_url.scheme}://{self.host_name}{request_path}"
        
        # 构建请求体
        body = json.dumps(params) if (method == "POST" and params) else ""
        
        # 构建查询参数
        query_params = "" if not params else f"?{urlencode(params)}"
        if method == "GET":
            url += query_params
            request_path += query_params
        
        # 获取时间戳和签名
        timestamp = self._get_timestamp()
        sign = self._generate_signature(timestamp, method, request_path, body) if need_sign else None
        
        # 获取请求头
        headers = self._get_headers(timestamp, sign, exp_time) if need_sign else self._get_public_headers()
        
        logger.debug(f"发送API请求: {method} {url}")
        logger.debug(f"请求头: {headers}")
        if body:
            logger.debug(f"请求体: {body}")
        
        try:
            # 发送请求
            if method == "GET":
                response = self.session.get(url, headers=headers)
            else:
                response = self.session.post(url, headers=headers, data=body)
            
            # 解析响应
            response_data = response.json()
            logger.debug(f"API响应: {response_data}")
            
            # 验证响应
            if not self._validate_response(response_data, method, url):
                return None
            
            return response_data
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP请求失败: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"解析API响应失败: {e}")
            return None
    
    def _validate_response(self, response, method, url):
        """
        验证API响应
        
        Args:
            response (dict): API响应
            method (str): HTTP方法
            url (str): 请求URL
        
        Returns:
            bool: 是否验证通过
        """
        if not response:
            logger.error(f"API请求失败，未收到响应: {method} {url}")
            return False
        
        if not isinstance(response, dict):
            logger.error(f"API响应格式错误，预期为字典类型: {method} {url}")
            return False
        
        if response.get('code') != '0':
            error_msg = response.get('msg', 'Unknown error')
            error_code = response.get('code', 'Unknown code')
            self._handle_api_error(error_code, error_msg, method, url)
            return False
        
        return True
    
    def _handle_api_error(self, error_code, error_msg, method, url):
        """
        处理API错误，根据OKX API错误代码文档提供详细解释和处理建议
        
        Args:
            error_code (str): 错误码
            error_msg (str): 错误信息
            method (str): HTTP方法
            url (str): 请求URL
        """
        # 错误码分类处理
        error_info = {
            # 认证相关错误
            '100001': ('API密钥格式错误', '检查API密钥是否正确，确保没有空格或特殊字符'),
            '100002': ('签名无效', '检查签名生成算法是否正确，确保时间戳与服务器时间同步'),
            '100003': ('时间戳无效', '检查本地时间是否与服务器时间同步，时间差应小于30秒'),
            '100004': ('API密钥已过期', '请在OKX平台重新生成API密钥'),
            '100005': ('API密钥权限不足', '请在OKX平台检查API密钥权限设置'),
            
            # 参数相关错误
            '101001': ('参数格式错误', '检查请求参数格式是否符合API文档要求'),
            '101002': ('必填参数缺失', '检查是否遗漏了必填参数'),
            '101003': ('参数值超出范围', '检查参数值是否在允许范围内'),
            '101004': ('无效的交易对', '检查交易对是否存在或是否支持'),
            
            # 订单相关错误
            '102001': ('余额不足', '检查账户余额是否充足'),
            '102002': ('订单数量超出限制', '减少订单数量或联系OKX客服'),
            '102003': ('订单价格超出限制', '检查订单价格是否在允许范围内'),
            '102004': ('订单已存在', '请勿重复提交同一订单'),
            '102005': ('订单不存在', '检查订单ID是否正确'),
            
            # 系统相关错误
            '500001': ('系统错误', '请稍后重试或联系OKX客服'),
            '500002': ('服务繁忙', '请稍后重试或减少请求频率'),
            '500003': ('网络异常', '检查网络连接或代理设置'),
        }
        
        # 获取错误解释和处理建议
        if error_code in error_info:
            error_desc, error_suggestion = error_info[error_code]
            logger.error(f"API请求失败 (错误码: {error_code}): {error_msg} - {method} {url}")
            logger.error(f"错误解释: {error_desc}")
            logger.error(f"处理建议: {error_suggestion}")
        else:
            logger.error(f"API请求失败 (错误码: {error_code}): {error_msg} - {method} {url}")
            logger.error(f"请参考OKX API文档了解详细错误信息: https://www.oyuzh.org/docs-v5/zh/#error-code-rest-api-account")
    
    def _process_result(self, result):
        """
        处理API返回结果
        """
        if result and isinstance(result, dict):
            if result.get('code') == '0':
                return result.get('data')
            else:
                error_msg = result.get('msg', 'Unknown error')
                error_code = result.get('code', 'Unknown code')
                self._handle_api_error(error_code, error_msg, "N/A", "N/A")
                return None
        return result
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def get_ticker(self, inst_id):
        """获取行情信息"""
        try:
            result = self._request(
                method="GET",
                endpoint="public/ticker",
                params={"instId": inst_id},
                need_sign=False
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"获取行情信息失败 [{inst_id}]: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def get_order_book(self, inst_id, depth=10):
        """获取订单簿数据"""
        try:
            result = self._request(
                method="GET",
                endpoint="public/books",
                params={"instId": inst_id, "sz": depth},
                need_sign=False
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"获取订单簿数据失败 [{inst_id}]: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def get_candlesticks(self, inst_id, bar='1m', limit=100):
        """获取K线数据"""
        try:
            result = self._request(
                method="GET",
                endpoint="public/candles",
                params={"instId": inst_id, "bar": bar, "limit": limit},
                need_sign=False
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"获取K线数据失败 [{inst_id}, {bar}]: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def get_trades(self, inst_id, limit=50):
        """获取成交数据"""
        try:
            result = self._request(
                method="GET",
                endpoint="public/trades",
                params={"instId": inst_id, "limit": limit},
                need_sign=False
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"获取成交数据失败 [{inst_id}]: {e}")
            return None
    
    # 交易相关方法
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def place_order(self, inst_id, side, ord_type, sz, px=None, td_mode=None, cl_ord_id=None, tag=None, pos_side=None, reduce_only=None, tgt_ccy=None, tp_px=None, tp_trigger_px=None, tp_ord_px=None, sl_px=None, sl_trigger_px=None, sl_ord_px=None, tp_trigger_px_type=None, sl_trigger_px_type=None, quick_mgn_type=None, req_id=None, exp_time=None):
        """下单
        
        Args:
            inst_id (str): 交易产品ID
            side (str): 订单方向 (buy/sell)
            ord_type (str): 订单类型 (market/limit/post_only/fok/ioc/optimal_limit_ioc/optimal_limit_fok)
            sz (str): 订单数量
            px (str, optional): 订单价格 (限价单必填)
            td_mode (str, optional): 交易模式 (cash/cross/isolated)
            cl_ord_id (str, optional): 客户自定义订单ID
            tag (str, optional): 订单标签
            pos_side (str, optional): 持仓方向 (net/long/short)
            reduce_only (bool, optional): 是否仅减仓
            tgt_ccy (str, optional): 目标币种
            tp_px (str, optional): 止盈价格
            tp_trigger_px (str, optional): 止盈触发价格
            tp_ord_px (str, optional): 止盈委托价格
            sl_px (str, optional): 止损价格
            sl_trigger_px (str, optional): 止损触发价格
            sl_ord_px (str, optional): 止损委托价格
            tp_trigger_px_type (str, optional): 止盈触发价格类型
            sl_trigger_px_type (str, optional): 止损触发价格类型
            quick_mgn_type (str, optional): 快捷杠杆类型
            req_id (str, optional): 请求ID
            exp_time (str, optional): 请求有效截止时间
        
        Returns:
            dict: 订单信息
        """
        try:
            params = {
                'instId': inst_id,
                'side': side,
                'ordType': ord_type,
                'sz': sz
            }
            
            # 可选参数
            if px:
                params['px'] = px
            if td_mode:
                params['tdMode'] = td_mode
            if cl_ord_id:
                params['clOrdId'] = cl_ord_id
            if tag:
                params['tag'] = tag
            if pos_side:
                params['posSide'] = pos_side
            if reduce_only:
                params['reduceOnly'] = reduce_only
            if tgt_ccy:
                params['tgtCcy'] = tgt_ccy
            if tp_px:
                params['tpPx'] = tp_px
            if tp_trigger_px:
                params['tpTriggerPx'] = tp_trigger_px
            if tp_ord_px:
                params['tpOrdPx'] = tp_ord_px
            if sl_px:
                params['slPx'] = sl_px
            if sl_trigger_px:
                params['slTriggerPx'] = sl_trigger_px
            if sl_ord_px:
                params['slOrdPx'] = sl_ord_px
            if tp_trigger_px_type:
                params['tpTriggerPxType'] = tp_trigger_px_type
            if sl_trigger_px_type:
                params['slTriggerPxType'] = sl_trigger_px_type
            if quick_mgn_type:
                params['quickMgnType'] = quick_mgn_type
            if req_id:
                params['reqId'] = req_id
            
            result = self._request(
                method="POST",
                endpoint="trade/order",
                params=params,
                need_sign=True,
                exp_time=exp_time
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"下单失败 [{inst_id}, {side}, {ord_type}]: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def batch_place_orders(self, orders, exp_time=None):
        """批量下单
        
        Args:
            orders (list): 订单列表，每个订单包含必要的下单参数
            exp_time (str, optional): 请求有效截止时间
        
        Returns:
            dict: 批量下单结果
        """
        try:
            result = self._request(
                method="POST",
                endpoint="trade/batch-orders",
                params=orders,
                need_sign=True,
                exp_time=exp_time
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"批量下单失败: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def cancel_order(self, inst_id, ord_id, cl_ord_id=None, sub_ord_id=None, req_id=None, exp_time=None):
        """取消订单
        
        Args:
            inst_id (str): 交易产品ID
            ord_id (str, optional): 订单ID
            cl_ord_id (str, optional): 客户自定义订单ID
            sub_ord_id (str, optional): 子订单ID
            req_id (str, optional): 请求ID
            exp_time (str, optional): 请求有效截止时间
        
        Returns:
            dict: 取消订单结果
        """
        try:
            params = {
                'instId': inst_id
            }
            
            if ord_id:
                params['ordId'] = ord_id
            if cl_ord_id:
                params['clOrdId'] = cl_ord_id
            if sub_ord_id:
                params['subOrdId'] = sub_ord_id
            if req_id:
                params['reqId'] = req_id
            
            result = self._request(
                method="POST",
                endpoint="trade/cancel-order",
                params=params,
                need_sign=True,
                exp_time=exp_time
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"取消订单失败 [{inst_id}, {ord_id}]: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def batch_cancel_orders(self, cancel_orders, exp_time=None):
        """批量取消订单
        
        Args:
            cancel_orders (list): 取消订单列表，每个订单包含必要的取消参数
            exp_time (str, optional): 请求有效截止时间
        
        Returns:
            dict: 批量取消订单结果
        """
        try:
            result = self._request(
                method="POST",
                endpoint="trade/batch-cancel-orders",
                params=cancel_orders,
                need_sign=True,
                exp_time=exp_time
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"批量取消订单失败: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def get_order(self, inst_id, ord_id=None, cl_ord_id=None, sub_ord_id=None):
        """获取订单信息
        
        Args:
            inst_id (str): 交易产品ID
            ord_id (str, optional): 订单ID
            cl_ord_id (str, optional): 客户自定义订单ID
            sub_ord_id (str, optional): 子订单ID
        
        Returns:
            dict: 订单信息
        """
        try:
            params = {
                'instId': inst_id
            }
            
            if ord_id:
                params['ordId'] = ord_id
            if cl_ord_id:
                params['clOrdId'] = cl_ord_id
            if sub_ord_id:
                params['subOrdId'] = sub_ord_id
            
            result = self._request(
                method="GET",
                endpoint="trade/order",
                params=params,
                need_sign=True
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"获取订单信息失败 [{inst_id}, {ord_id}]: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def amend_order(self, inst_id, ord_id=None, cl_ord_id=None, req_id=None, new_sz=None, new_px=None, tp_px=None, tp_trigger_px=None, tp_ord_px=None, sl_px=None, sl_trigger_px=None, sl_ord_px=None, tp_trigger_px_type=None, sl_trigger_px_type=None, sub_ord_id=None, exp_time=None):
        """修改订单
        
        Args:
            inst_id (str): 交易产品ID
            ord_id (str, optional): 订单ID
            cl_ord_id (str, optional): 客户自定义订单ID
            req_id (str, optional): 请求ID
            new_sz (str, optional): 新的订单数量
            new_px (str, optional): 新的订单价格
            tp_px (str, optional): 新的止盈价格
            tp_trigger_px (str, optional): 新的止盈触发价格
            tp_ord_px (str, optional): 新的止盈委托价格
            sl_px (str, optional): 新的止损价格
            sl_trigger_px (str, optional): 新的止损触发价格
            sl_ord_px (str, optional): 新的止损委托价格
            tp_trigger_px_type (str, optional): 新的止盈触发价格类型
            sl_trigger_px_type (str, optional): 新的止损触发价格类型
            sub_ord_id (str, optional): 子订单ID
            exp_time (str, optional): 请求有效截止时间
        
        Returns:
            dict: 修改订单结果
        """
        try:
            params = {
                'instId': inst_id
            }
            
            if ord_id:
                params['ordId'] = ord_id
            if cl_ord_id:
                params['clOrdId'] = cl_ord_id
            if req_id:
                params['reqId'] = req_id
            if new_sz:
                params['newSz'] = new_sz
            if new_px:
                params['newPx'] = new_px
            if tp_px:
                params['tpPx'] = tp_px
            if tp_trigger_px:
                params['tpTriggerPx'] = tp_trigger_px
            if tp_ord_px:
                params['tpOrdPx'] = tp_ord_px
            if sl_px:
                params['slPx'] = sl_px
            if sl_trigger_px:
                params['slTriggerPx'] = sl_trigger_px
            if sl_ord_px:
                params['slOrdPx'] = sl_ord_px
            if tp_trigger_px_type:
                params['tpTriggerPxType'] = tp_trigger_px_type
            if sl_trigger_px_type:
                params['slTriggerPxType'] = sl_trigger_px_type
            if sub_ord_id:
                params['subOrdId'] = sub_ord_id
            
            result = self._request(
                method="POST",
                endpoint="trade/amend-order",
                params=params,
                need_sign=True,
                exp_time=exp_time
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"修改订单失败 [{inst_id}, {ord_id}]: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def batch_amend_orders(self, amend_orders, exp_time=None):
        """批量修改订单
        
        Args:
            amend_orders (list): 修改订单列表，每个订单包含必要的修改参数
            exp_time (str, optional): 请求有效截止时间
        
        Returns:
            dict: 批量修改订单结果
        """
        try:
            result = self._request(
                method="POST",
                endpoint="trade/batch-amend-orders",
                params=amend_orders,
                need_sign=True,
                exp_time=exp_time
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"批量修改订单失败: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def get_pending_orders(self, inst_id=None, state=None, ord_type=None, after=None, before=None, limit=50):
        """获取未成交订单
        
        Args:
            inst_id (str, optional): 交易产品ID
            state (str, optional): 订单状态 (pending/partially_filled)
            ord_type (str, optional): 订单类型
            after (str, optional): 请求此ID之前（更旧）的分页数据
            before (str, optional): 请求此ID之后（更新）的分页数据
            limit (int, optional): 返回结果的数量，默认50
        
        Returns:
            dict: 未成交订单列表
        """
        try:
            params = {
                'limit': limit
            }
            
            if inst_id:
                params['instId'] = inst_id
            if state:
                params['state'] = state
            if ord_type:
                params['ordType'] = ord_type
            if after:
                params['after'] = after
            if before:
                params['before'] = before
            
            result = self._request(
                method="GET",
                endpoint="trade/orders-pending",
                params=params,
                need_sign=True
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"获取未成交订单失败 [{inst_id}]: {e}")
            return None
    
    # 账户相关方法
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def get_account_balance(self, ccy=None):
        """获取账户余额
        
        Args:
            ccy (str, optional): 币种，支持多币种查询，用逗号分隔，不超过20个
        
        Returns:
            dict: 账户余额信息
        """
        try:
            params = {}
            if ccy:
                params['ccy'] = ccy
            
            result = self._request(
                method="GET",
                endpoint="account/balance",
                params=params,
                need_sign=True
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"获取账户余额失败: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def get_positions(self, inst_id=None, inst_type=None, pos_id=None):
        """获取持仓信息
        
        Args:
            inst_id (str, optional): 交易产品ID，支持多个，用逗号分隔，不超过10个
            inst_type (str, optional): 产品类型 (MARGIN/SWAP/FUTURES/OPTION)
            pos_id (str, optional): 持仓ID，支持多个，用逗号分隔，不超过20个
        
        Returns:
            dict: 持仓信息列表
        """
        try:
            params = {}
            
            if inst_id:
                params['instId'] = inst_id
            if inst_type:
                params['instType'] = inst_type
            if pos_id:
                params['posId'] = pos_id
            
            result = self._request(
                method="GET",
                endpoint="account/positions",
                params=params,
                need_sign=True
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"获取持仓信息失败 [{inst_id}]: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def get_instruments(self, inst_type, inst_family=None, inst_id=None):
        """获取交易产品基础信息
        
        Args:
            inst_type (str): 产品类型 (SPOT/MARGIN/SWAP/FUTURES/OPTION)
            inst_family (str, optional): 交易品种，仅适用于交割/永续/期权，期权必填
            inst_id (str, optional): 产品ID
        
        Returns:
            dict: 交易产品基础信息列表
        """
        try:
            params = {
                'instType': inst_type
            }
            
            if inst_family:
                params['instFamily'] = inst_family
            if inst_id:
                params['instId'] = inst_id
            
            result = self._request(
                method="GET",
                endpoint="account/instruments",
                params=params,
                need_sign=True
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"获取交易产品基础信息失败 [{inst_type}]: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def set_leverage(self, inst_id, lever, mgn_mode='isolated', pos_side=None, ccy=None):
        """设置杠杆
        
        Args:
            inst_id (str): 交易产品ID
            lever (str): 杠杆倍数
            mgn_mode (str, optional): 保证金模式 (isolated/cross)
            pos_side (str, optional): 持仓方向 (long/short)
            ccy (str, optional): 币种，仅适用于跨币种保证金模式
        
        Returns:
            dict: 设置杠杆结果
        """
        try:
            params = {
                'instId': inst_id,
                'lever': str(lever),
                'mgnMode': mgn_mode
            }
            
            if pos_side:
                params['posSide'] = pos_side
            if ccy:
                params['ccy'] = ccy
            
            result = self._request(
                method="POST",
                endpoint="account/set-leverage",
                params=params,
                need_sign=True
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"设置杠杆失败 [{inst_id}, {lever}, {mgn_mode}]: {e}")
            return None
    
    # 资金相关方法
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def get_balances(self):
        """获取资金账户余额"""
        try:
            result = self._request(
                method="GET",
                endpoint="asset/balances",
                need_sign=True
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"获取资金账户余额失败: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def transfer(self, ccy, amt, from_, to, sub_acct=None):
        """资金划转"""
        try:
            params = {
                'ccy': ccy,
                'amt': amt,
                'from': from_,
                'to': to
            }
            if sub_acct:
                params['subAcct'] = sub_acct
            
            result = self._request(
                method="POST",
                endpoint="asset/transfer",
                params=params,
                need_sign=True
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"资金划转失败 [{ccy}, {amt}, {from_} → {to}]: {e}")
            return None

# 创建默认客户端实例
client = None

def get_client():
    """获取默认客户端实例"""
    global client
    if not client:
        # 从配置文件加载API配置
        import os
        import json
        config_path = os.path.join(os.path.dirname(__file__), 'config/okx_config.json')
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            api_config = config.get('api', {})
            client = OKXAPIClient(
                api_key=api_config.get('api_key'),
                api_secret=api_config.get('api_secret'),
                passphrase=api_config.get('passphrase'),
                is_test=api_config.get('is_test', False),
                api_url=api_config.get('api_url'),
                api_ip=api_config.get('api_ip'),
                api_ips=api_config.get('api_ips', []),
                timeout=api_config.get('timeout', 30)
            )
        except Exception as e:
            logger.error(f"从配置文件加载客户端配置失败: {e}")
            client = OKXAPIClient()
    return client

if __name__ == "__main__":
    # 测试客户端
    try:
        # 创建客户端，使用API IP地址绕过DNS解析
        test_client = OKXAPIClient(
            is_test=True,
            api_ip='18.141.249.241'  # OKX API的IP地址，用于绕过DNS解析
        )
        
        # 测试获取行情
        ticker = test_client.get_ticker('BTC-USDT-SWAP')
        if ticker:
            logger.info(f"BTC-USDT-SWAP 行情: {ticker[0]['last']}")
        else:
            logger.warning("无法获取行情数据，可能是API密钥未配置或测试网问题")
            
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
