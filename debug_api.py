import sys
import json
import socket
from okx_api_client import OKXAPIClient, custom_dns_resolve
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, level="DEBUG")

def debug_api_connection():
    """调试API连接问题"""
    logger.info("开始调试API连接...")
    
    try:
        # 1. 测试自定义DNS解析
        logger.info("1. 测试自定义DNS解析...")
        ip = custom_dns_resolve("www.okx.com")
        if ip:
            logger.info(f"   自定义DNS解析成功: www.okx.com -> {ip}")
        else:
            logger.error("   自定义DNS解析失败")
            return
        
        # 2. 测试socket连接
        logger.info(f"2. 测试socket连接到 {ip}:443...")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(10)
        s.connect((ip, 443))
        s.close()
        logger.info("   Socket连接成功")
        
        # 3. 测试OKX API客户端初始化
        logger.info("3. 测试OKX API客户端初始化...")
        client = OKXAPIClient()
        logger.info("   OKX API客户端初始化成功")
        
        # 4. 测试API请求
        logger.info("4. 测试API请求 - 获取行情数据...")
        ticker = client.get_ticker("BTC-USDT-SWAP")
        if ticker:
            logger.info(f"   API请求成功: {ticker}")
        else:
            logger.error("   API请求失败: 无法获取行情数据")
            
    except Exception as e:
        logger.error(f"调试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_api_connection()

