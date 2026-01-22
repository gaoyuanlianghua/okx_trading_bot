#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
代理配置测试脚本
用于验证SOCKS5代理是否能成功绕过网络DPI拦截
测试443端口API访问和8443端口WebSocket连接
"""

import requests
import asyncio
import json
import time
from loguru import logger

# 配置日志
logger.add("proxy_test.log", rotation="1 MB")

# 测试配置
TEST_CONFIG = {
    "proxy_enabled": True,
    "proxy_url": "socks5://127.0.0.1:1080",
    "api_url": "https://www.okx.com",
    "ws_url": "wss://ws.okx.com:8443/ws/v5/public",
    "test_symbol": "BTC-USDT-SWAP",
    "timeout": 15
}


def test_http_proxy():
    """
    测试HTTP代理连接，验证443端口API访问
    """
    logger.info("=== 测试HTTP代理连接 (443端口) ===")
    
    try:
        # 准备代理配置
        proxies = {
            "http": TEST_CONFIG["proxy_url"],
            "https": TEST_CONFIG["proxy_url"]
        } if TEST_CONFIG["proxy_enabled"] else None
        
        logger.info(f"使用代理: {TEST_CONFIG['proxy_url'] if TEST_CONFIG['proxy_enabled'] else '无'}")
        logger.info(f"测试API: {TEST_CONFIG['api_url']}")
        
        # 发送测试请求
        start_time = time.time()
        response = requests.get(
            f"{TEST_CONFIG['api_url']}/api/v5/public/ticker?instId={TEST_CONFIG['test_symbol']}",
            proxies=proxies,
            timeout=TEST_CONFIG["timeout"],
            verify=True
        )
        end_time = time.time()
        
        # 检查响应
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == "0":
                logger.success(f"✅ HTTP代理测试成功！")
                logger.success(f"   状态码: {response.status_code}")
                logger.success(f"   响应时间: {end_time - start_time:.2f}秒")
                logger.success(f"   最新价格: {data['data'][0]['last']}")
                logger.success(f"   交易量: {data['data'][0]['volCcy24h']}")
                return True
            else:
                logger.error(f"❌ API返回错误: {data.get('msg')}")
                return False
        else:
            logger.error(f"❌ HTTP请求失败，状态码: {response.status_code}")
            logger.error(f"   响应内容: {response.text}")
            return False
            
    except requests.exceptions.ProxyError as e:
        logger.error(f"❌ 代理连接失败: {e}")
        logger.error("   可能原因:")
        logger.error("   1. 代理服务器未运行")
        logger.error("   2. 代理地址或端口错误")
        logger.error("   3. 代理服务器拒绝连接")
        return False
    except requests.exceptions.SSLError as e:
        logger.error(f"❌ SSL握手失败: {e}")
        logger.error("   可能原因:")
        logger.error("   1. 网络DPI拦截")
        logger.error("   2. 代理服务器SSL配置错误")
        logger.error("   3. 证书验证失败")
        return False
    except requests.exceptions.ConnectionError as e:
        logger.error(f"❌ 连接错误: {e}")
        logger.error("   可能原因:")
        logger.error("   1. 网络连接断开")
        logger.error("   2. 防火墙阻止连接")
        logger.error("   3. 服务器不可达")
        return False
    except requests.exceptions.Timeout as e:
        logger.error(f"❌ 请求超时: {e}")
        logger.error("   可能原因:")
        logger.error("   1. 网络延迟过高")
        logger.error("   2. 代理服务器响应缓慢")
        logger.error("   3. 服务器负载过高")
        return False
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        logger.error(f"   异常堆栈: {traceback.format_exc()}")
        return False


async def test_websocket_proxy():
    """
    测试WebSocket代理连接，验证8443端口WebSocket访问
    """
    logger.info("\n=== 测试WebSocket代理连接 (8443端口) ===")
    
    try:
        # 动态导入，避免依赖问题
        import websockets
        
        ws = None
        ssl_sock = None
        
        # 如果启用了代理，使用python-socks库创建代理连接
        if TEST_CONFIG["proxy_enabled"]:
            logger.info(f"使用python-socks库测试WebSocket代理: {TEST_CONFIG['proxy_url']}")
            
            try:
                from python_socks import ProxyType, parse_proxy_url
                
                # 解析代理URL，返回元组: (proxy_type, host, port, username, password)
                proxy_type, host, port, username, password = parse_proxy_url(TEST_CONFIG["proxy_url"])
                logger.info(f"代理类型: {proxy_type}, 地址: {host}, 端口: {port}")
                
                # 创建异步代理连接，使用正确的导入路径
                from python_socks.asyncio._proxy import Proxy
                proxy = Proxy(
                    proxy_type=proxy_type,
                    host=host,
                    port=port,
                    username=username,
                    password=password
                )
                
                # 建立代理连接到目标服务器
                logger.info(f"建立代理连接到 ws.okx.com:8443")
                sock = await proxy.connect(dest_host='ws.okx.com', dest_port=8443)
                logger.success(f"✅ 代理连接建立成功")
                
                # 创建SSL上下文
                import ssl
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = True
                ssl_context.verify_mode = ssl.CERT_REQUIRED
                ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
                
                # 包装为SSL连接
                logger.info(f"包装为SSL连接")
                ssl_sock = await ssl_context.wrap_asyncio_socket(
                    sock, server_hostname='ws.okx.com'
                )
                logger.success(f"✅ SSL连接建立成功")
                
                # 使用已建立的SSL连接创建WebSocket
                start_time = time.time()
                logger.info(f"创建WebSocket连接")
                ws = await websockets.connect(
                    TEST_CONFIG["ws_url"],
                    sock=ssl_sock,
                    open_timeout=TEST_CONFIG["timeout"],
                    ping_interval=20,
                    ping_timeout=10
                )
            except Exception as e:
                logger.error(f"❌ WebSocket代理连接失败: {e}")
                import traceback
                logger.error(f"   异常堆栈: {traceback.format_exc()}")
                return False
        else:
            # 直接连接WebSocket
            start_time = time.time()
            logger.info(f"直接连接到WebSocket: {TEST_CONFIG['ws_url']}")
            ws = await websockets.connect(
                TEST_CONFIG["ws_url"],
                open_timeout=TEST_CONFIG["timeout"],
                ping_interval=20,
                ping_timeout=10
            )
        
        end_time = time.time()
        logger.success(f"✅ WebSocket连接成功！")
        logger.success(f"   连接时间: {end_time - start_time:.2f}秒")
        
        # 订阅行情测试
        subscribe_msg = {
            "op": "subscribe",
            "args": [{"channel": "ticker", "instId": TEST_CONFIG["test_symbol"]}]
        }
        
        logger.info(f"订阅行情频道: ticker/{TEST_CONFIG['test_symbol']}")
        await ws.send(json.dumps(subscribe_msg))
        
        # 接收消息
        logger.info("等待接收行情数据...")
        msg_count = 0
        max_msgs = 3
        
        async for message in ws:
            msg_data = json.loads(message)
            msg_count += 1
            
            if "event" in msg_data and msg_data["event"] == "subscribe":
                if msg_data["code"] == "0":
                    logger.success(f"✅ 订阅成功！")
                else:
                    logger.error(f"❌ 订阅失败: {msg_data.get('msg')}")
                    break
            elif "data" in msg_data:
                logger.success(f"✅ 收到行情数据 #{msg_count}:")
                logger.success(f"   交易对: {msg_data['data'][0]['instId']}")
                logger.success(f"   最新价格: {msg_data['data'][0]['last']}")
                logger.success(f"   买一价: {msg_data['data'][0]['bidPx']}")
                logger.success(f"   卖一价: {msg_data['data'][0]['askPx']}")
                
                if msg_count >= max_msgs:
                    logger.info(f"已接收 {max_msgs} 条消息，测试完成")
                    break
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ 导入依赖失败: {e}")
        logger.error("   请安装依赖: pip install python-socks[asyncio] websockets")
        return False
    except Exception as e:
        logger.error(f"❌ WebSocket测试失败: {e}")
        import traceback
        logger.error(f"   异常堆栈: {traceback.format_exc()}")
        return False
    finally:
        # 关闭WebSocket连接
        if 'ws' in locals() and ws:
            await ws.close()


async def run_full_test():
    """
    运行完整的代理测试
    """
    logger.info("=" * 60)
    logger.info("SOCKS5代理配置测试脚本")
    logger.info("=" * 60)
    logger.info(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"代理配置: {TEST_CONFIG['proxy_url']}")
    logger.info(f"代理状态: {'已启用' if TEST_CONFIG['proxy_enabled'] else '已禁用'}")
    logger.info(f"测试交易对: {TEST_CONFIG['test_symbol']}")
    logger.info("=" * 60)
    
    # 测试HTTP代理
    http_success = test_http_proxy()
    
    # 测试WebSocket代理
    ws_success = await test_websocket_proxy()
    
    logger.info("\n" + "=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)
    
    if http_success and ws_success:
        logger.success("🎉 所有测试通过！代理配置正常工作")
        logger.success("   SOCKS5代理已成功绕过网络DPI拦截")
        logger.success("   API和WebSocket连接均正常")
        return True
    else:
        logger.error("❌ 测试失败！代理配置存在问题")
        logger.error("   请检查以下内容:")
        logger.error("   1. 代理服务器是否正常运行")
        logger.error("   2. 代理地址和端口是否正确")
        logger.error("   3. 代理服务器是否支持SOCKS5协议")
        logger.error("   4. 网络防火墙是否允许代理连接")
        return False


if __name__ == "__main__":
    try:
        # 运行测试
        success = asyncio.run(run_full_test())
        
        # 退出状态码
        exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.info("\n测试被用户中断")
        exit(0)
    except Exception as e:
        logger.error(f"测试脚本出错: {e}")
        import traceback
        logger.error(f"异常堆栈: {traceback.format_exc()}")
        exit(1)
