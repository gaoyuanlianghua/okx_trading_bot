from okx_websocket_client import OKXWebsocketClient
import time
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 获取的wspap.okx.com的真实IP列表
OKX_WS_IPS = ["104.18.43.174", "172.64.144.82"]  # 使用nslookup获取的真实IP列表

# 测试单个IP地址的连接
def test_single_ip_connection(ip):
    logger.info(f"=== 开始测试IP地址: {ip} ===")
    try:
        ws_client = OKXWebsocketClient(
            is_test=True,  # 使用测试网
            ws_ip=ip  # 使用直接IP连接
        )

        # 定义消息处理器
        def handle_ticker_message(msg):
            try:
                if "data" in msg and msg["data"]:
                    inst_id = msg["data"][0]["instId"]
                    last_price = msg["data"][0]["last"]
                    logger.info(f'[{ip}] 收到行情消息: {inst_id}，最新价格: {last_price}')
            except Exception as e:
                logger.error(f'[{ip}] 处理行情消息失败: {e}')

        # 添加消息处理器
        ws_client.add_message_handler('tickers', handle_ticker_message)

        # 启动客户端
        logger.info(f"[{ip}] 启动WebSocket客户端...")
        ws_client.start()

        # 等待连接建立
        logger.info(f"[{ip}] 等待连接建立...")
        time.sleep(5)  # 延长等待时间，确保连接有足够时间建立

        # 订阅行情频道
        logger.info(f"[{ip}] 订阅行情频道...")
        ws_client.subscribe_public('tickers', 'BTC-USDT-SWAP')

        # 运行10秒
        logger.info(f"[{ip}] 运行10秒...")
        time.sleep(10)

        # 停止客户端
        logger.info(f"[{ip}] 停止WebSocket客户端...")
        ws_client.stop()

        logger.info(f"[{ip}] 测试通过")
        return True
    except Exception as e:
        logger.error(f"[{ip}] 测试失败: {e}")
        return False
    finally:
        logger.info(f"=== 结束测试IP地址: {ip} ===")

# 测试多个IP地址
def test_multiple_ips():
    logger.info("开始测试多个WebSocket IP地址...")
    results = {}
    
    for ip in OKX_WS_IPS:
        results[ip] = test_single_ip_connection(ip)
        # 测试之间间隔5秒，避免频繁连接导致的问题
        logger.info("\n测试之间间隔5秒...\n")
        time.sleep(5)
    
    # 打印测试结果汇总
    logger.info("=== 测试结果汇总 ===")
    for ip, success in results.items():
        status = "通过" if success else "失败"
        logger.info(f"IP地址: {ip} - 测试结果: {status}")
    
    # 统计通过数量
    passed_count = sum(1 for success in results.values() if success)
    logger.info(f"总测试IP数: {len(results)}, 通过数: {passed_count}, 失败数: {len(results) - passed_count}")
    
    return results

# 测试IP轮询功能
def test_ip_rotation():
    logger.info("=== 开始测试IP轮询功能 ===")
    try:
        # 创建客户端，使用IP列表
        ws_client = OKXWebsocketClient(
            is_test=True,  # 使用测试网
            ws_ips=OKX_WS_IPS  # 使用IP列表进行轮询
        )
        
        # 定义消息处理器
        def handle_ticker_message(msg):
            try:
                if "data" in msg and msg["data"]:
                    inst_id = msg["data"][0]["instId"]
                    last_price = msg["data"][0]["last"]
                    logger.info(f'[{ws_client.ws_ip}] 收到行情消息: {inst_id}，最新价格: {last_price}')
            except Exception as e:
                logger.error(f'处理行情消息失败: {e}')
        
        # 添加消息处理器
        ws_client.add_message_handler('tickers', handle_ticker_message)
        
        # 测试IP轮询功能
        logger.info(f"初始WebSocket IP: {ws_client.ws_ip}")
        
        # 模拟连接失败，手动切换IP
        for i in range(3):
            new_ip = ws_client.switch_to_next_ws_ip()
            logger.info(f"切换到下一个IP (尝试{i+1}): {new_ip}")
            time.sleep(1)
        
        # 启动客户端并测试
        logger.info("启动WebSocket客户端...")
        ws_client.start()
        
        logger.info("等待连接建立...")
        time.sleep(5)
        
        logger.info("订阅行情频道...")
        ws_client.subscribe_public('tickers', 'BTC-USDT-SWAP')
        
        logger.info("运行10秒...")
        time.sleep(10)
        
        logger.info("停止WebSocket客户端...")
        ws_client.stop()
        
        logger.info("IP轮询功能测试通过")
        return True
    except Exception as e:
        logger.error(f"IP轮询功能测试失败: {e}")
        return False
    finally:
        logger.info("=== 结束测试IP轮询功能 ===")

if __name__ == "__main__":
    logger.info("=== WebSocket直接IP连接测试 ===")
    
    # 测试多个IP地址
    test_multiple_ips()
    
    logger.info("\n" + "="*50 + "\n")
    
    # 测试IP轮询功能
    test_ip_rotation()
    
    logger.info("\n=== 所有测试完成 ===")
