import os
import json
import time
import asyncio
from datetime import datetime, timedelta
from loguru import logger
from okx_api_client import OKXAPIClient
from okx_websocket_client import OKXWebsocketClient

class MarketDataService:
    """市场数据服务，封装OKX API的市场数据功能"""
    
    def __init__(self, api_client=None):
        """
        初始化市场数据服务
        
        Args:
            api_client (OKXAPIClient, optional): OKX API客户端实例
        """
        if api_client:
            self.api_client = api_client
        else:
            # 从配置文件加载API配置
            config_path = os.path.join(os.path.dirname(__file__), '../../config/okx_config.json')
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            api_config = config.get('api', {})
            self.api_client = OKXAPIClient(
                api_key=api_config.get('api_key'),
                api_secret=api_config.get('api_secret'),
                passphrase=api_config.get('passphrase'),
                is_test=api_config.get('is_test', False),
                api_url=api_config.get('api_url'),
                api_ip=api_config.get('api_ip'),
                timeout=api_config.get('timeout', 30)
            )
        
        # 初始化WebSocket客户端
        self.ws_client = OKXWebsocketClient(
            api_key=self.api_client.api_key,
            api_secret=self.api_client.api_secret,
            passphrase=self.api_client.passphrase,
            is_test=self.api_client.is_test
        )
        
        # 添加消息处理器
        self.ws_client.add_message_handler('tickers', self._handle_websocket_message)
        
        # WebSocket数据缓存
        self.ws_data_cache = {}
        self.ws_subscriptions = set()
        
        # 启动WebSocket连接
        self._start_websocket()
        
        self.data_dir = os.path.join(os.path.dirname(__file__), '../../data')
        
        # 确保数据目录存在
        os.makedirs(self.data_dir, exist_ok=True)
        
        logger.info("市场数据服务初始化完成")
    
    def _start_websocket(self):
        """启动WebSocket连接"""
        # 启动公共频道连接
        asyncio.create_task(self._run_websocket())
        logger.info("WebSocket连接启动中...")
    
    async def _run_websocket(self):
        """运行WebSocket连接"""
        try:
            # 启动公共频道连接
            public_task = asyncio.create_task(self.ws_client._public_handler())
            
            # 等待连接建立
            await asyncio.sleep(2)
            
            # 订阅已有的交易对
            for symbol in self.ws_subscriptions:
                await self._subscribe_websocket(symbol)
                
        except Exception as e:
            logger.error(f"WebSocket运行失败: {e}")
    
    async def _subscribe_websocket(self, inst_id):
        """订阅WebSocket频道
        
        Args:
            inst_id (str): 交易对
        """
        if self.ws_client.public_ws:
            await self.ws_client._subscribe(self.ws_client.public_ws, 'tickers', inst_id, is_public=True)
            logger.info(f"已订阅WebSocket行情频道: {inst_id}")
    
    def _handle_websocket_message(self, message):
        """处理WebSocket消息
        
        Args:
            message (dict): WebSocket消息
        """
        try:
            if 'data' in message and 'arg' in message:
                channel = message['arg']['channel']
                inst_id = message['arg']['instId']
                
                if channel == 'tickers':
                    # 更新行情数据缓存
                    self.ws_data_cache[inst_id] = message['data'][0]
                    logger.debug(f"WebSocket行情更新: {inst_id}，最新价格: {message['data'][0]['last']}")
        except Exception as e:
            logger.error(f"处理WebSocket消息失败: {e}")
    
    def get_real_time_ticker(self, inst_id):
        """
        获取实时行情
        
        Args:
            inst_id (str): 交易对，如 'BTC-USDT-SWAP'
        
        Returns:
            dict: 行情数据
        """
        try:
            # 优先从WebSocket缓存获取数据
            if inst_id in self.ws_data_cache:
                logger.debug(f"从WebSocket缓存获取实时行情: {inst_id}，最新价格: {self.ws_data_cache[inst_id]['last']}")
                return self.ws_data_cache[inst_id]
            
            # 否则使用REST API
            ticker_data = self.api_client.get_ticker(inst_id)
            if ticker_data:
                logger.debug(f"获取实时行情成功: {inst_id}，最新价格: {ticker_data[0]['last']}")
                # 添加到WebSocket订阅
                if inst_id not in self.ws_subscriptions:
                    self.ws_subscriptions.add(inst_id)
                    asyncio.create_task(self._subscribe_websocket(inst_id))
                return ticker_data[0]
            return None
        except Exception as e:
            if "getaddrinfo failed" in str(e):
                logger.error(f"DNS解析失败，无法连接到API服务器 [{inst_id}]: {e}")
                logger.error("请检查网络连接或API URL配置")
            else:
                logger.error(f"获取实时行情失败 [{inst_id}]: {e}")
            return None
    
    def get_order_book(self, inst_id, depth=10):
        """
        获取订单簿数据
        
        Args:
            inst_id (str): 交易对
            depth (int, optional): 订单簿深度，默认10
        
        Returns:
            dict: 订单簿数据
        """
        try:
            order_book_data = self.api_client.get_order_book(inst_id, depth)
            if order_book_data:
                logger.debug(f"获取订单簿成功: {inst_id}，深度: {depth}")
                return order_book_data[0]
            return None
        except Exception as e:
            if "getaddrinfo failed" in str(e):
                logger.error(f"DNS解析失败，无法连接到API服务器 [{inst_id}]: {e}")
            else:
                logger.error(f"获取订单簿失败 [{inst_id}]: {e}")
            return None
    
    def get_candlesticks(self, inst_id, bar='1m', limit=100):
        """
        获取K线数据
        
        Args:
            inst_id (str): 交易对
            bar (str, optional): K线周期，如 '1m', '1h', '1d'
            limit (int, optional): 返回数量，默认100
        
        Returns:
            list: K线数据列表
        """
        try:
            candles_data = self.api_client.get_candlesticks(inst_id, bar, limit)
            if candles_data:
                logger.debug(f"获取K线数据成功: {inst_id}，周期: {bar}，数量: {len(candles_data)}")
                # 转换为标准化格式
                normalized_candles = self._normalize_candles(candles_data)
                return normalized_candles
            return []
        except Exception as e:
            if "getaddrinfo failed" in str(e):
                logger.error(f"DNS解析失败，无法连接到API服务器 [{inst_id}]: {e}")
            else:
                logger.error(f"获取K线数据失败 [{inst_id}]: {e}")
            return []
    
    def get_trades(self, inst_id, limit=50):
        """
        获取最近成交数据
        
        Args:
            inst_id (str): 交易对
            limit (int, optional): 返回数量，默认50
        
        Returns:
            list: 成交数据列表
        """
        try:
            trades_data = self.api_client.get_trades(inst_id, limit)
            if trades_data:
                logger.debug(f"获取成交数据成功: {inst_id}，数量: {len(trades_data)}")
                return trades_data
            return []
        except Exception as e:
            if "getaddrinfo failed" in str(e):
                logger.error(f"DNS解析失败，无法连接到API服务器 [{inst_id}]: {e}")
            else:
                logger.error(f"获取成交数据失败 [{inst_id}]: {e}")
            return []
    
    def download_historical_data(self, inst_id, bar='1h', start_time=None, end_time=None, save_to_file=True):
        """
        下载历史K线数据
        
        Args:
            inst_id (str): 交易对
            bar (str, optional): K线周期，默认1h
            start_time (str, optional): 开始时间，格式: YYYY-MM-DD
            end_time (str, optional): 结束时间，格式: YYYY-MM-DD
            save_to_file (bool, optional): 是否保存到文件，默认True
        
        Returns:
            list: 历史K线数据
        """
        try:
            # 设置默认时间范围
            if not end_time:
                end_time = datetime.now().strftime('%Y-%m-%d')
            if not start_time:
                # 默认下载30天数据
                start_time = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            logger.info(f"开始下载历史数据: {inst_id}，周期: {bar}，时间范围: {start_time} → {end_time}")
            
            # OKX API一次最多返回100条，需要分页获取
            all_candles = []
            last_timestamp = None
            max_retries = 5
            
            while True:
                # 获取K线数据
                candles = self.api_client.get_candlesticks(inst_id, bar, 100)
                if not candles:
                    break
                
                # 转换为标准化格式
                normalized_candles = self._normalize_candles(candles)
                
                # 添加到结果列表
                all_candles.extend(normalized_candles)
                
                # 更新最后一个时间戳
                last_candle = normalized_candles[-1]
                last_timestamp = last_candle['timestamp']
                
                # 检查是否到达起始时间
                candle_datetime = datetime.fromtimestamp(last_timestamp / 1000)
                if candle_datetime.strftime('%Y-%m-%d') <= start_time:
                    break
                
                # 避免请求过快
                time.sleep(0.5)
                
            # 去重和排序
            all_candles = list({c['timestamp']: c for c in all_candles}.values())
            all_candles.sort(key=lambda x: x['timestamp'])
            
            logger.info(f"历史数据下载完成: {inst_id}，共 {len(all_candles)} 条记录")
            
            # 保存到文件
            if save_to_file:
                self._save_candles_to_file(all_candles, inst_id, bar)
            
            return all_candles
            
        except Exception as e:
            logger.error(f"下载历史数据失败 [{inst_id}]: {e}")
            return []
    
    def _normalize_candles(self, candles):
        """
        标准化K线数据格式
        
        Args:
            candles (list): 原始K线数据
        
        Returns:
            list: 标准化后的K线数据
        """
        normalized = []
        for candle in candles:
            # OKX API返回格式: [timestamp, open, high, low, close, volume, volumeCcy, volumeCcyQuote]
            normalized.append({
                'timestamp': int(candle[0]),
                'datetime': datetime.fromtimestamp(int(candle[0]) / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                'open': float(candle[1]),
                'high': float(candle[2]),
                'low': float(candle[3]),
                'close': float(candle[4]),
                'volume': float(candle[5]),
                'volume_ccy': float(candle[6]),
                'volume_ccy_quote': float(candle[7])
            })
        return normalized
    
    def _save_candles_to_file(self, candles, inst_id, bar):
        """
        将K线数据保存到文件
        
        Args:
            candles (list): K线数据
            inst_id (str): 交易对
            bar (str): K线周期
        """
        try:
            # 创建交易对目录
            symbol_dir = os.path.join(self.data_dir, inst_id.replace('/', '_'))
            os.makedirs(symbol_dir, exist_ok=True)
            
            # 生成文件名
            filename = f"{bar}.json"
            filepath = os.path.join(symbol_dir, filename)
            
            # 保存数据
            with open(filepath, 'w') as f:
                json.dump(candles, f, indent=2, ensure_ascii=False)
            
            logger.info(f"K线数据保存成功: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"保存K线数据失败: {e}")
            return None
    
    def load_candles_from_file(self, inst_id, bar='1h'):
        """
        从文件加载K线数据
        
        Args:
            inst_id (str): 交易对
            bar (str, optional): K线周期，默认1h
        
        Returns:
            list: K线数据列表
        """
        try:
            # 构建文件路径
            symbol_dir = os.path.join(self.data_dir, inst_id.replace('/', '_'))
            filepath = os.path.join(symbol_dir, f"{bar}.json")
            
            if not os.path.exists(filepath):
                logger.warning(f"K线数据文件不存在: {filepath}")
                return []
            
            # 读取文件
            with open(filepath, 'r') as f:
                candles = json.load(f)
            
            logger.info(f"从文件加载K线数据成功: {filepath}，共 {len(candles)} 条记录")
            return candles
            
        except Exception as e:
            logger.error(f"从文件加载K线数据失败: {e}")
            return []
    
    def get_market_summary(self, inst_id):
        """
        获取市场综合信息
        
        Args:
            inst_id (str): 交易对
        
        Returns:
            dict: 综合市场信息
        """
        try:
            # 并行获取多种数据
            ticker = self.get_real_time_ticker(inst_id)
            order_book = self.get_order_book(inst_id, 5)
            recent_trades = self.get_trades(inst_id, 10)
            
            summary = {
                'inst_id': inst_id,
                'timestamp': int(time.time() * 1000),
                'ticker': ticker,
                'order_book': order_book,
                'recent_trades': recent_trades
            }
            
            logger.debug(f"获取市场综合信息成功: {inst_id}")
            return summary
            
        except Exception as e:
            logger.error(f"获取市场综合信息失败 [{inst_id}]: {e}")
            return None

# 创建默认服务实例
default_service = None

def get_market_data_service():
    """获取默认市场数据服务实例"""
    global default_service
    if not default_service:
        default_service = MarketDataService()
    return default_service

if __name__ == "__main__":
    # 测试市场数据服务
    try:
        # 创建服务实例
        service = MarketDataService()
        
        # 测试获取实时行情
        ticker = service.get_real_time_ticker('BTC-USDT-SWAP')
        if ticker:
            logger.info(f"BTC-USDT-SWAP 实时行情: 最新价格: {ticker['last']}, 24h 涨跌: {ticker['change24h']}")
        
        # 测试获取订单簿
        order_book = service.get_order_book('BTC-USDT-SWAP', 5)
        if order_book:
            logger.info(f"BTC-USDT-SWAP 订单簿: 买一: {order_book['bids'][0][0]}, 卖一: {order_book['asks'][0][0]}")
        
        # 测试获取K线数据
        candles = service.get_candlesticks('BTC-USDT-SWAP', '1h', 10)
        if candles:
            logger.info(f"BTC-USDT-SWAP 1小时K线: 最近收盘价: {candles[-1]['close']}")
        
        # 测试获取成交数据
        trades = service.get_trades('BTC-USDT-SWAP', 5)
        if trades:
            logger.info(f"BTC-USDT-SWAP 最近成交: {len(trades)} 笔")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
