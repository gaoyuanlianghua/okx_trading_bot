#!/usr/bin/env python3
"""
简单测试DNS解析功能
"""

import os
import sys
import asyncio
import time

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from okx_api_client import (
    validate_domain,
    custom_dns_resolve,
    async_custom_dns_resolve,
    DNS_CACHE,
    DNS_WHITELIST,
    OKXAPIClient
)

def test_validate_domain():
    """测试域名验证功能"""
    print("=== 测试域名验证功能 ===")
    
    # 有效域名
    valid_domains = ["www.okx.com", "ws.okx.com", "okx.com"]
    for domain in valid_domains:
        result = validate_domain(domain)
        print(f"域名 {domain}: {'有效' if result else '无效'}")
    
    # 无效域名
    invalid_domains = ["", None, 123, "invalid-domain", "invalid_domain.com", "*.example.com", "example"]
    for domain in invalid_domains:
        result = validate_domain(domain)
        print(f"域名 {domain}: {'有效' if result else '无效'}")
    
    # 不在白名单中的域名
    non_whitelist_domains = ["www.example.com", "api.example.com"]
    for domain in non_whitelist_domains:
        result = validate_domain(domain)
        print(f"域名 {domain}: {'有效' if result else '无效'}")
    
    print()

def test_custom_dns_resolve():
    """测试自定义DNS解析功能"""
    print("=== 测试自定义DNS解析功能 ===")
    
    # 测试白名单域名解析
    for domain in DNS_WHITELIST:
        ip = custom_dns_resolve(domain)
        print(f"解析 {domain}: {ip}")
    
    # 测试无效域名解析
    ip = custom_dns_resolve("invalid-domain")
    print(f"解析 invalid-domain: {ip}")
    
    # 测试不在白名单中的域名解析
    ip = custom_dns_resolve("www.example.com")
    print(f"解析 www.example.com: {ip}")
    
    print()

def test_dns_cache():
    """测试DNS缓存功能"""
    print("=== 测试DNS缓存功能 ===")
    
    # 清空缓存
    DNS_CACHE.clear()
    print(f"缓存初始状态: {len(DNS_CACHE)} 条记录")
    
    # 第一次解析，应该缓存结果
    domain = "www.okx.com"
    start_time = time.time()
    ip1 = custom_dns_resolve(domain)
    elapsed1 = time.time() - start_time
    print(f"第一次解析 {domain}: {ip1} (耗时: {elapsed1:.3f}s)")
    print(f"缓存状态: {len(DNS_CACHE)} 条记录")
    
    # 第二次解析，应该从缓存中获取
    start_time = time.time()
    ip2 = custom_dns_resolve(domain)
    elapsed2 = time.time() - start_time
    print(f"第二次解析 {domain}: {ip2} (耗时: {elapsed2:.3f}s)")
    print(f"缓存状态: {len(DNS_CACHE)} 条记录")
    
    print()

async def test_async_dns_resolve():
    """测试异步DNS解析功能"""
    print("=== 测试异步DNS解析功能 ===")
    
    # 测试白名单域名解析
    for domain in DNS_WHITELIST:
        ip = await async_custom_dns_resolve(domain)
        print(f"异步解析 {domain}: {ip}")
    
    print()

def test_auto_configure_dns():
    """测试自动配置DNS解析IP功能"""
    print("=== 测试自动配置DNS解析IP功能 ===")
    
    # 保存原始环境变量
    original_okx_ips = os.environ.get("OKX_API_IPS")
    
    try:
        # 创建OKX API客户端，触发自动配置
        client = OKXAPIClient(is_test=True)
        
        # 检查环境变量是否设置
        if "OKX_API_IPS" in os.environ:
            ips = os.environ["OKX_API_IPS"].split(",")
            print(f"环境变量 OKX_API_IPS: {os.environ['OKX_API_IPS']}")
            print(f"解析到的IP数量: {len(ips)}")
        else:
            print("环境变量 OKX_API_IPS 未设置")
        
        print()
    finally:
        # 恢复原始环境变量
        if original_okx_ips:
            os.environ["OKX_API_IPS"] = original_okx_ips
        elif "OKX_API_IPS" in os.environ:
            del os.environ["OKX_API_IPS"]

def test_dns_resolve_performance():
    """测试DNS解析性能"""
    print("=== 测试DNS解析性能 ===")
    
    # 清空缓存
    DNS_CACHE.clear()
    
    # 测试多次解析同一域名的性能
    domain = "www.okx.com"
    iterations = 10
    
    start_time = time.time()
    for i in range(iterations):
        ip = custom_dns_resolve(domain)
    end_time = time.time()
    
    elapsed = end_time - start_time
    print(f"解析 {domain} {iterations} 次总耗时: {elapsed:.3f}s")
    print(f"平均每次耗时: {elapsed/iterations:.3f}s")
    print(f"缓存命中次数: {iterations - 1}")
    print()

def test_dns_stats():
    """测试DNS统计信息功能"""
    print("=== 测试DNS统计信息功能 ===")
    
    # 清空缓存和统计信息
    DNS_CACHE.clear()
    from okx_api_client import reset_dns_stats
    reset_dns_stats()
    
    # 进行几次DNS查询
    for _ in range(3):
        custom_dns_resolve("www.okx.com")
    
    # 获取统计信息
    from okx_api_client import get_dns_stats
    stats = get_dns_stats()
    
    print(f"总查询次数: {stats['total_queries']}")
    print(f"成功查询次数: {stats['successful_queries']}")
    print(f"缓存命中次数: {stats['cached_queries']}")
    print(f"平均解析时间: {stats['average_resolve_time']:.3f}s")
    print(f"成功率: {stats['success_rate']:.2%}")
    print(f"缓存命中率: {stats['cache_hit_rate']:.2%}")
    
    print()

def test_dns_config_update():
    """测试动态更新DNS配置功能"""
    print("=== 测试动态更新DNS配置功能 ===")
    
    from okx_api_client import update_dns_config, CURRENT_DNS_CONFIG
    
    # 保存原始配置
    original_config = CURRENT_DNS_CONFIG.copy()
    
    try:
        # 更新超时时间
        new_config = {'timeout': 3}
        result = update_dns_config(new_config)
        print(f"更新超时时间: {'成功' if result else '失败'}")
        print(f"当前配置: {CURRENT_DNS_CONFIG}")
        
        # 切换DNS区域
        from okx_api_client import switch_dns_region
        result = switch_dns_region('asia')
        print(f"切换到亚洲区域: {'成功' if result else '失败'}")
        print(f"当前配置: {CURRENT_DNS_CONFIG}")
        
        # 切换回原始区域
        result = switch_dns_region('global')
        print(f"切换回全球区域: {'成功' if result else '失败'}")
        print(f"当前配置: {CURRENT_DNS_CONFIG}")
    finally:
        # 恢复原始配置
        update_dns_config(original_config)
    
    print()

def test_dns_client_integration():
    """测试OKX API客户端集成DNS新功能"""
    print("=== 测试OKX API客户端集成DNS新功能 ===")
    
    # 创建OKX API客户端
    client = OKXAPIClient(is_test=True)
    
    # 获取DNS统计信息
    stats = client.get_dns_stats()
    print(f"客户端获取DNS统计信息: {stats}")
    
    # 重置DNS统计信息
    client.reset_dns_stats()
    print("已重置DNS统计信息")
    
    # 切换DNS区域
    result = client.switch_dns_region('europe')
    print(f"客户端切换到欧洲区域: {'成功' if result else '失败'}")
    
    # 获取当前DNS配置
    config = client.get_dns_config()
    print(f"客户端获取DNS配置: {config}")
    
    # 切换回全球区域
    client.switch_dns_region('global')
    
    print()

if __name__ == "__main__":
    print("开始测试DNS解析功能...\n")
    
    # 测试域名验证
    test_validate_domain()
    
    # 测试自定义DNS解析
    test_custom_dns_resolve()
    
    # 测试DNS缓存
    test_dns_cache()
    
    # 测试异步DNS解析
    asyncio.run(test_async_dns_resolve())
    
    # 测试自动配置DNS
    test_auto_configure_dns()
    
    # 测试DNS解析性能
    test_dns_resolve_performance()
    
    # 测试DNS统计信息
    test_dns_stats()
    
    # 测试动态更新DNS配置
    test_dns_config_update()
    
    # 测试OKX API客户端集成DNS新功能
    test_dns_client_integration()
    
    print("测试完成！")
