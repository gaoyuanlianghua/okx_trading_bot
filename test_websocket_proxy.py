#!/usr/bin/env python3
"""
WebSocket代理测试脚本
用于验证8443端口WebSocket连接通过代理是否正常工作
"""

import asyncio
import json
import os
from loguru import logger

# 配置日志
logger.remove()
logger.add(
    "test_websocket_proxy.log",
    level="DEBUG",
    rotation="1 MB",
    compression="zip"
)
logger.add(
    lambda msg: print(msg, end=""),
    level="INFO"
)

# 读取配置文件
def read_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'okx_config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except Exception as e:
        logger.error(f"❌ 读取配置文件失败: {e}")
        return None

# 测试WebSocket连接
def test_websocket_connection(proxy_config):
    """测试WebSocket连接"""
    print("=== 测试 8443 端口 WebSocket 连接 ===")
    
    if not proxy_config.get('enabled', False):
        print("❌ 代理未启用")
        return False
    
    # 获取代理地址
    proxy_address = None
    for proxy_type in ['socks5', 'https', 'http']:
        if proxy_config.get(proxy_type):
            proxy_address = proxy_config[proxy_type]
            break
    
    if not proxy_address:
        print("❌ 未配置代理地址")
        return False
    
    print(f"🔍 正在使用代理: {proxy_address}")
    
    # 导入websockets和代理库
    try:
        import websockets
        from python_socks import parse_proxy_url
        from python_socks.sync import Proxy
        
        # 解析代理URL
        proxy_type, host, port, username, password = parse_proxy_url(proxy_address)
        print(f"📋 代理详情: 类型={proxy_type}, 地址={host}:{port}")
        
        # 测试代理连接
        print("📡 测试代理连接...")
        proxy = Proxy(
            proxy_type=proxy_type,
            host=host,
            port=port,
            username=username,
            password=password
        )
        
        # 建立到WebSocket服务器的代理连接
        print("🔌 建立到WebSocket服务器的代理连接...")
        sock = proxy.connect(dest_host='ws.okx.com', dest_port=8443)
        
        # 设置SSL上下文
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        
        # 包装socket为SSL连接
        print("🔒 建立SSL连接...")
        ssl_sock = ssl_context.wrap_socket(
            sock,
            server_hostname='ws.okx.com'
        )
        
        async def connect_and_test():
            """异步连接并测试WebSocket"""
            # 使用包装后的socket建立WebSocket连接
            print("📞 建立WebSocket连接...")
            async with websockets.connect(
                "wss://ws.okx.com:8443/ws/v5/public",
                sock=ssl_sock,
                open_timeout=15
            ) as ws:
                print("✅ WebSocket连接成功！")
                
                # 订阅行情测试
                print("📩 发送订阅请求...")
                subscribe_msg = {
                    "op": "subscribe",
                    "args": [{"channel": "ticker", "instId": "BTC-USDT-SWAP"}]
                }
                await ws.send(json.dumps(subscribe_msg))
                
                # 接收1条消息
                print("📨 等待接收消息...")
                msg = await ws.recv()
                print(f"✅ 收到消息: {msg[:100]}...")
                
                # 解析消息
                msg_data = json.loads(msg)
                if msg_data.get('event') == 'subscribe':
                    print("✅ 订阅成功！")
                    # 再接收1条行情数据
                    print("📨 等待接收行情数据...")
                    ticker_msg = await ws.recv()
                    print(f"✅ 收到行情数据: {ticker_msg[:100]}...")
                
                # 取消订阅
                print("📩 发送取消订阅请求...")
                unsubscribe_msg = {
                    "op": "unsubscribe",
                    "args": [{"channel": "ticker", "instId": "BTC-USDT-SWAP"}]
                }
                await ws.send(json.dumps(unsubscribe_msg))
                
                # 等待取消确认
                print("📨 等待取消订阅确认...")
                unsubscribe_resp = await ws.recv()
                print(f"✅ 取消订阅成功: {unsubscribe_resp[:100]}...")
                
                return True
        
        # 运行异步测试
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(connect_and_test())
        
        # 关闭连接
        ssl_sock.close()
        sock.close()
        
        return success
    
    except ImportError as e:
        logger.error(f"❌ 缺少依赖库: {e}")
        logger.error("请运行: pip install python-socks[asyncio] websockets")
        return False
    except Exception as e:
        logger.error(f"❌ WebSocket 连接失败: {e}")
        return False

# 主函数
def main():
    print("🚀 WebSocket代理测试脚本")
    print("================================")
    
    # 读取配置
    config = read_config()
    if not config:
        return
    
    proxy_config = config.get('api', {}).get('proxy', {})
    
    # 显示当前代理配置
    print("📋 当前代理配置:")
    print(f"   启用状态: {'✅ 已启用' if proxy_config.get('enabled') else '❌ 未启用'}")
    print(f"   SOCKS5代理: {proxy_config.get('socks5', '未配置')}")
    print(f"   HTTP代理: {proxy_config.get('http', '未配置')}")
    print(f"   HTTPS代理: {proxy_config.get('https', '未配置')}")
    print("================================")
    
    # 测试WebSocket连接
    success = test_websocket_connection(proxy_config)
    
    print("\n" + "="*50)
    print("📊 测试结果汇总:")
    print(f"   8443端口WebSocket: {'✅ 成功' if success else '❌ 失败'}")
    
    if success:
        print("\n🎉 WebSocket代理测试通过！")
    else:
        print("\n💥 WebSocket代理测试失败，请检查代理配置！")

if __name__ == "__main__":
    main()