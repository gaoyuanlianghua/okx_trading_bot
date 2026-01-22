import requests
import asyncio
import websockets
from python_socks.sync import Proxy

# 使用配置文件中的代理地址
PROXY_URL = "socks5://127.0.0.1:1080"

# 测试 443 端口 API 访问（HTTP/HTTPS）
def test_443_api():
    try:
        # 使用requests的socks代理支持
        proxies = {
            "http": PROXY_URL,
            "https": PROXY_URL
        }
        resp = requests.get(
            "https://www.okx.com:443/api/v5/public/ticker?instId=BTC-USDT-SWAP",
            proxies=proxies,
            timeout=15,
            verify=True
        )
        print("✅ 443 端口 API 访问成功！")
        print(f"响应状态码: {resp.status_code}")
        print(f"响应内容: {resp.json()['data'][0]['last']}")
        return True
    except Exception as e:
        print(f"❌ 443 端口 API 访问失败: {str(e)}")
        return False

# 测试 8443 端口 Websocket 访问（简化版本）
async def test_8443_ws():
    try:
        # 简化测试，直接使用websockets连接，通过代理
        async with websockets.connect(
            "wss://ws.okx.com:8443/ws/v5/public",
            open_timeout=15
        ) as ws:
            print("✅ 8443 端口 Websocket 连接成功！")
            # 订阅行情测试
            await ws.send('{"op":"subscribe","args":[{"channel":"ticker","instId":"BTC-USDT-SWAP"}]}')
            # 接收 1 条消息后退出
            msg = await ws.recv()
            print(f"收到 Websocket 消息: {msg[:100]}...")
    except Exception as e:
        print(f"❌ 8443 端口 Websocket 连接失败: {str(e)}")

# 执行测试
if __name__ == "__main__":
    print("=== 测试 443 端口 API ===")
    api_ok = test_443_api()
    if api_ok:
        print("\n=== 测试 8443 端口 Websocket ===")
        asyncio.run(test_8443_ws())