from okx_websocket_client import OKXWebsocketClient
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 测试WebSocket客户端IP列表加载
def test_ws_ip_list():
    logger.info("=== 测试WebSocket客户端IP列表加载 ===")
    
    # 从nslookup获取的真实IP列表
    okx_ws_ips = ["104.18.43.174", "172.64.144.82"]
    
    # 创建客户端，使用IP列表
    ws_client = OKXWebsocketClient(
        is_test=True,  # 使用测试网
        ws_ips=okx_ws_ips  # 使用IP列表
    )
    
    # 检查IP列表
    logger.info(f"WebSocket IP列表: {ws_client.ws_ips}")
    logger.info(f"当前WebSocket IP: {ws_client.ws_ip}")
    logger.info(f"当前IP索引: {ws_client.current_ws_ip_index}")
    
    # 测试IP轮询
    logger.info("\n=== 测试IP轮询 ===")
    for i in range(5):
        new_ip = ws_client.switch_to_next_ws_ip()
        logger.info(f"第{i+1}次切换IP，新IP: {new_ip}, 当前索引: {ws_client.current_ws_ip_index}")
    
    logger.info("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_ws_ip_list()