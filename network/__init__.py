# network/__init__.py
"""
网络模块包初始化文件
"""

from .network_errors import (
    NetworkError, ConnectionError, TimeoutError, DNSResolutionError, 
    SSLHandshakeError, RateLimitError, ServerError, global_network_error_handler
)

from .dns_resolver import (
    custom_dns_resolve, prewarm_dns_cache, batch_dns_resolve, 
    update_dns_config, switch_dns_region, get_dns_stats, reset_dns_stats,
    async_custom_dns_resolve, DNS_WHITELIST, CURRENT_DNS_CONFIG
)

from .http_adapters import (
    CustomHTTPSConnection, CustomPoolManager, CustomHTTPSAdapter, 
    DNSResolverAdapter, DNSBypassingSession, custom_getaddrinfo, original_getaddrinfo
)

from .network_monitor import (
    NetworkMonitor, global_network_monitor
)

from .retry_utils import (
    smart_retry, retry_with_backoff
)

__all__ = [
    # network_errors
    'NetworkError', 'ConnectionError', 'TimeoutError', 'DNSResolutionError', 
    'SSLHandshakeError', 'RateLimitError', 'ServerError', 'global_network_error_handler',
    # dns_resolver
    'custom_dns_resolve', 'prewarm_dns_cache', 'batch_dns_resolve', 
    'update_dns_config', 'switch_dns_region', 'get_dns_stats', 'reset_dns_stats',
    'async_custom_dns_resolve', 'DNS_WHITELIST', 'CURRENT_DNS_CONFIG',
    # http_adapters
    'CustomHTTPSConnection', 'CustomPoolManager', 'CustomHTTPSAdapter', 
    'DNSResolverAdapter', 'DNSBypassingSession', 'custom_getaddrinfo', 'original_getaddrinfo',
    # network_monitor
    'NetworkMonitor', 'global_network_monitor',
    # retry_utils
    'smart_retry', 'retry_with_backoff'
]
