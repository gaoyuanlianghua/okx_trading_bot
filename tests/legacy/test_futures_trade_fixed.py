#!/usr/bin/env python3

import asyncio
import json
import aiohttp

async def test_futures_trade_fixed():
    """测试合约交易（修正版）"""
    
    # API配置
    api_key = "19500a62-5586-44ac-ad05-0aa8b1410af0"
    api_secret = "5939DA431FA0C9D820C46D13F7AB17F8"
    passphrase = "Gy528329818.123"
    is_test = True
    
    # 构建请求
    url = "https://www.okx.com/api/v5/trade/order"
    
    # 生成时间戳
    import time
    import hmac
    import hashlib
    import base64
    from datetime import datetime, timezone
    
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    
    # 生成签名
    method = "POST"
    request_path = "/api/v5/trade/order"
    
    # 合约交易参数（修正版）
    # BTC-USDT-SWAP的最小交易单位是1
    body = {
        "instId": "BTC-USDT-SWAP",  # 合约产品
        "tdMode": "cross",          # 全仓模式
        "side": "sell",              # 卖出
        "ordType": "limit",          # 限价单
        "sz": "1",                   # 1个合约单位
        "px": "68000"                # 价格
    }
    
    body_json = json.dumps(body)
    
    message = timestamp + method + request_path + body_json
    signature = hmac.new(
        api_secret.encode("utf-8"), 
        message.encode("utf-8"), 
        hashlib.sha256
    ).digest()
    signature = base64.b64encode(signature).decode("utf-8")
    
    # 构建请求头
    headers = {
        "Content-Type": "application/json",
        "OK-ACCESS-KEY": api_key,
        "OK-ACCESS-SIGN": signature,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": passphrase
    }
    
    # 模拟盘请求头
    if is_test:
        headers["x-simulated-trading"] = "1"
    
    print("=== 测试合约交易（修正版）===")
    print(f"URL: {url}")
    print(f"Body: {body}")
    print(f"Headers: {headers}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=body_json) as response:
                print(f"Status: {response.status}")
                text = await response.text()
                print(f"Response: {text}")
                
                try:
                    data = json.loads(text)
                    print(f"Parsed response: {data}")
                except json.JSONDecodeError:
                    print("Failed to parse JSON response")
                    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_futures_trade_fixed())
