from okx_websocket_client import OKXWebsocketClient
import time
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 创建客户端
logger.info("创建WebSocket客户端...")
ws_client = OKXWebsocketClient(is_test=True)

# 定义消息处理器
def handle_ticker_message(msg):
    try:
        inst_id = msg["data"][0]["instId"]
        last_price = msg["data"][0]["last"]
        logger.info(f'收到行情消息: {inst_id}，最新价格: {last_price}')
    except Exception as e:
        logger.error(f'处理行情消息失败: {e}')

# 添加消息处理器
logger.info("添加消息处理器...")
ws_client.add_message_handler('tickers', handle_ticker_message)

# 启动客户端
logger.info("启动WebSocket客户端...")
ws_client.start()

# 等待连接建立
logger.info("等待连接建立...")
time.sleep(3)

# 订阅行情频道
logger.info("订阅行情频道...")
ws_client.subscribe_public('tickers', 'BTC-USDT-SWAP')

# 运行5秒
logger.info("运行5秒...")
time.sleep(5)

# 停止客户端
logger.info("停止WebSocket客户端...")
ws_client.stop()

logger.info("测试完成")