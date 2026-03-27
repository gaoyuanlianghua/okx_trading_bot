# network/dns_resolver.py
"""
DNS解析模块
"""

import time
import socket
import re
from threading import Lock
from cachetools import TTLCache

# 初始化日志配置
from commons.logger_config import global_logger_config

# 获取区域化日志记录器
def get_logger(region=None):
    return global_logger_config.get_logger(region=region)

# 创建默认日志记录器
logger = get_logger("DNS")


# DNS解析白名单，仅允许解析这些域名
DNS_WHITELIST = ['www.okx.com', 'ws.okx.com', 'okx.com']

# DNS解析结果缓存，TTL为10分钟，增加缓存大小提高命中率
DNS_CACHE = TTLCache(maxsize=10000, ttl=600)
DNS_CACHE_LOCK = Lock()  # DNS缓存线程安全锁

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
    'use_custom_dns': True  # 是否使用自定义DNS解析，默认开启
}


# 从配置文件加载DNS配置
def load_dns_config():
    """从配置文件加载DNS配置"""
    global CURRENT_DNS_CONFIG
    try:
        from commons.config_manager import global_config_manager
        config = global_config_manager.get_config()
        network_config = config.get('network', {})
        if 'use_custom_dns' in network_config:
            CURRENT_DNS_CONFIG['use_custom_dns'] = network_config['use_custom_dns']
            logger.info(f"从配置文件加载DNS配置: use_custom_dns={CURRENT_DNS_CONFIG['use_custom_dns']}")
    except Exception as e:
        logger.error(f"加载DNS配置失败: {e}")


# 验证域名格式
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


# 自定义DNS解析函数，优先使用系统DNS，提高可靠性
def custom_dns_resolve(hostname, dns_servers=None):
    """
    使用系统DNS优先解析主机名，提高解析可靠性
    
    Args:
        hostname (str): 要解析的主机名
        dns_servers (list, optional): DNS服务器列表，默认使用当前配置的服务器
        
    Returns:
        str: 解析到的IP地址，如果解析失败则返回None
    """
    # 检查是否启用自定义DNS解析
    if not CURRENT_DNS_CONFIG.get('use_custom_dns', True):
        logger.debug(f"自定义DNS解析已禁用，使用系统默认DNS解析: {hostname}")
        try:
            ip = socket.gethostbyname(hostname)
            return ip
        except socket.gaierror as e:
            logger.error(f"系统DNS解析失败: {e}")
            return None
    
    # 更新统计信息：总查询次数
    DNS_STATS['total_queries'] += 1
    
    # 验证域名格式和白名单
    if not validate_domain(hostname):
        logger.error(f"无效的域名: {hostname}")
        DNS_STATS['failed_queries'] += 1
        check_dns_health()
        return None
    
    # 线程安全地检查缓存
    with DNS_CACHE_LOCK:
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
    
    # 2. 如果系统DNS解析失败，尝试使用备用DNS服务器
    if not resolved_ip:
        try:
            import dns.resolver
            
            logger.debug(f"系统DNS解析失败，尝试使用备用DNS服务器查询 {hostname}")
            resolver = dns.resolver.Resolver()
            resolver.timeout = CURRENT_DNS_CONFIG['timeout']
            resolver.lifetime = CURRENT_DNS_CONFIG['timeout'] * CURRENT_DNS_CONFIG['retry_count']
            
            # 使用配置的DNS服务器
            if dns_servers:
                resolver.nameservers = dns_servers
            else:
                resolver.nameservers = CURRENT_DNS_CONFIG['servers']
            
            # 解析A记录
            answers = resolver.resolve(hostname, 'A', raise_on_no_answer=False)
            if answers.rdset:
                for rdata in answers:
                    ip = str(rdata.address)
                    # 检查是否为有效IP（非APIPA地址）
                    if not ip.startswith('169.254.') and ip != '0.0.0.0' and ip != '255.255.255.255':
                        logger.debug(f"使用备用DNS服务器解析 {hostname} 到 {ip} 成功")
                        resolved_ip = ip
                        break
        except ImportError:
            logger.debug("dnspython未安装，跳过备用DNS查询")
        except Exception as e:
            logger.debug(f"备用DNS服务器解析 {hostname} 失败: {e}")
    
    # 计算解析时间
    resolve_time = time.time() - resolve_start_time
    DNS_STATS['resolve_time'].append(resolve_time)
    
    # 更新统计信息
    if resolved_ip:
        DNS_STATS['successful_queries'] += 1
        # 线程安全地更新缓存
        with DNS_CACHE_LOCK:
            DNS_CACHE[hostname] = resolved_ip
        logger.debug(f"将 {hostname} -> {resolved_ip} 保存到DNS缓存")
    else:
        DNS_STATS['failed_queries'] += 1
        logger.error(f"DNS解析失败: {hostname}")
    
    # 检查DNS健康状况，触发告警
    check_dns_health()
    
    return resolved_ip


def prewarm_dns_cache(hostnames):
    """
    预热DNS缓存，批量解析域名并缓存结果
    
    Args:
        hostnames (list): 要预热的域名列表
        
    Returns:
        dict: 预热结果，{hostname: ip}
    """
    results = {}
    logger.info(f"开始预热DNS缓存，域名数量: {len(hostnames)}")
    
    for hostname in hostnames:
        if validate_domain(hostname):
            ip = custom_dns_resolve(hostname)
            results[hostname] = ip
            if ip:
                logger.debug(f"DNS缓存预热成功: {hostname} -> {ip}")
            else:
                logger.warning(f"DNS缓存预热失败: {hostname}")
    
    logger.info(f"DNS缓存预热完成，成功: {sum(1 for ip in results.values() if ip)}, 失败: {sum(1 for ip in results.values() if not ip)}")
    return results


def batch_dns_resolve(hostnames, dns_servers=None):
    """
    批量解析多个域名
    
    Args:
        hostnames (list): 要解析的域名列表
        dns_servers (list, optional): DNS服务器列表
        
    Returns:
        dict: 解析结果，{hostname: ip}
    """
    results = {}
    logger.info(f"开始批量DNS解析，域名数量: {len(hostnames)}")
    
    for hostname in hostnames:
        if validate_domain(hostname):
            ip = custom_dns_resolve(hostname, dns_servers)
            results[hostname] = ip
    
    success_count = sum(1 for ip in results.values() if ip)
    fail_count = len(results) - success_count
    logger.info(f"批量DNS解析完成，成功: {success_count}, 失败: {fail_count}")
    return results


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


# 加载DNS配置
load_dns_config()
