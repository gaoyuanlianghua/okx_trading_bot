#!/usr/bin/env python3

import asyncio
import json
import aiohttp

async def test_okx_api():
    """测试OKX API连接"""
    
    # API配置
    api_key = "19500a62-5586-44ac-ad05-0aa8b1410af0"
    api_secret = "5939DA431FA0C9D820C46D13F7AB17F8"
    passphrase = "Gy528329818.123"
    is_test = True
    
    # 构建请求
    url = "https://www.okx.com/api/v5/account/balance"
    
    # 生成时间戳
    import time
    import hmac
    import hashlib
    import base64
    from datetime import datetime, timezone
    
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    
    # 生成签名
    method = "GET"
    request_path = "/api/v5/account/balance"
    body = ""
    
    message = timestamp + method + request_path + body
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
    
    print("=== 测试OKX API连接 ===")
    print(f"URL: {url}")
    print(f"Headers: {headers}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
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
    loop.run_until_complete(test_okx_api())
