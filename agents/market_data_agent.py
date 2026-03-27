from commons.logger_config import get_logger
logger = get_logger(region="MarketData")
from agents.base_agent import BaseAgent
from services.market_data.market_data_service import MarketDataService
import time

class MarketDataAgent(BaseAgent):
    """市场数据智能体，负责获取和处理市场数据"""
    
    def __init__(self, agent_id, config=None):
        super().__init__(agent_id, config)
        self.market_data_service = None
        self.subscribed_symbols = set()
        self.update_interval = config.get('update_interval', 1)  # 默认1秒更新一次
        self.is_running = False
        self.last_market_data = {}  # 存储上次获取的市场数据，用于增量更新
        self.data_cache = {}  # 数据缓存
        self.cache_ttl = config.get('cache_ttl', 5)  # 缓存过期时间（秒）
        self.cache_timestamp = {}  # 缓存时间戳
        
        # 订阅事件
        self.subscribe('agent_status_changed', self.on_agent_status_changed)
        
        logger.info(f"市场数据智能体初始化完成: {self.agent_id}")
    
    def start(self):
        """启动市场数据智能体"""
        super().start()
        
        # 初始化市场数据服务
        from okx_api_client import OKXAPIClient
        api_client = OKXAPIClient(
            api_key=self.config.get('api_key'),
            api_secret=self.config.get('api_secret'),
            passphrase=self.config.get('passphrase'),
            is_test=self.config.get('is_test', False)
        )
        self.market_data_service = MarketDataService(api_client)
        
        # 启动数据更新线程
        self.is_running = True
        self.run_in_thread(self.update_market_data_loop)
        
        logger.info(f"市场数据智能体启动完成: {self.agent_id}")
    
    def stop(self):
        """停止市场数据智能体"""
        self.is_running = False
        super().stop()
        logger.info(f"市场数据智能体停止完成: {self.agent_id}")
    
    def update_market_data_loop(self):
        """市场数据更新循环"""
        while self.is_running:
            try:
                if self.subscribed_symbols:
                    for symbol in self.subscribed_symbols:
                        # 检查缓存是否有效
                        if self._is_cache_valid(symbol):
                            # 使用缓存数据
                            market_data = self.data_cache.get(symbol)
                        else:
                            # 获取市场数据
                            market_data = self.get_market_data(symbol)
                            if market_data:
                                # 更新缓存
                                self._update_cache(symbol, market_data)
                        
                        if market_data:
                            # 检查数据是否发生变化
                            if self._has_data_changed(symbol, market_data):
                                # 生成增量更新数据
                                incremental_data = self._generate_incremental_update(symbol, market_data)
                                
                                # 发布市场数据更新事件
                                self.publish('market_data_updated', {
                                    'symbol': symbol,
                                    'data': market_data,
                                    'incremental_data': incremental_data,
                                    'timestamp': time.time()
                                })
                                
                                # 更新上次数据
                                self.last_market_data[symbol] = market_data.copy()
                # 等待下一次更新
                time.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"市场数据更新失败: {e}")
                time.sleep(self.update_interval)
    
    def get_market_data(self, symbol):
        """获取指定交易对的市场数据
        
        Args:
            symbol (str): 交易对
            
        Returns:
            dict: 市场数据
        """
        try:
            if not self.market_data_service:
                return None
            
            # 获取实时行情数据
            ticker = self.market_data_service.get_real_time_ticker(symbol)
            if ticker:
                # 处理返回值可能是列表的情况
                if isinstance(ticker, list) and len(ticker) > 0:
                    ticker = ticker[0]
                
                # 构建市场数据
                market_data = {
                    'symbol': symbol,
                    'price': float(ticker.get('last', 0)),
                    'open': float(ticker.get('open24h', 0)),
                    'high': float(ticker.get('high24h', 0)),
                    'low': float(ticker.get('low24h', 0)),
                    'volume': float(ticker.get('vol24h', 0)),
                    'change': float(ticker.get('change24h', 0)),
                    'change_pct': float(ticker.get('change24h', 0))
                }
                return market_data
            return None
        except Exception as e:
            logger.error(f"获取市场数据失败: {symbol}, 错误: {e}")
            return None
    
    def subscribe_symbol(self, symbol):
        """订阅交易对
        
        Args:
            symbol (str): 交易对
        """
        self.subscribed_symbols.add(symbol)
        logger.info(f"订阅交易对: {symbol}")
    
    def unsubscribe_symbol(self, symbol):
        """取消订阅交易对
        
        Args:
            symbol (str): 交易对
        """
        if symbol in self.subscribed_symbols:
            self.subscribed_symbols.remove(symbol)
            logger.info(f"取消订阅交易对: {symbol}")
    
    def on_agent_status_changed(self, data):
        """处理智能体状态变化事件
        
        Args:
            data (dict): 事件数据
        """
        agent_id = data.get('agent_id')
        status = data.get('status')
        # 使用中文智能体名称
        agent_name = BaseAgent.AGENT_ID_MAP.get(agent_id, agent_id)
        logger.debug(f"智能体状态变化: {agent_name} -> {status}")
    
    def process_message(self, message):
        """处理收到的消息
        
        Args:
            message (dict): 消息内容
        """
        super().process_message(message)
        
        if message.get('type') == 'subscribe_symbol':
            symbol = message.get('symbol')
            self.subscribe_symbol(symbol)
        elif message.get('type') == 'unsubscribe_symbol':
            symbol = message.get('symbol')
            self.unsubscribe_symbol(symbol)
        elif message.get('type') == 'get_market_data':
            symbol = message.get('symbol')
            data = self.get_market_data(symbol)
            if data:
                self.send_message(message.get('sender'), {
                    'type': 'market_data_response',
                    'symbol': symbol,
                    'data': data
                })
    
    def get_subscribed_symbols(self):
        """获取已订阅的交易对列表
        
        Returns:
            set: 已订阅的交易对集合
        """
        return self.subscribed_symbols.copy()
    
    def _is_cache_valid(self, symbol):
        """检查缓存是否有效
        
        Args:
            symbol (str): 交易对
            
        Returns:
            bool: 缓存是否有效
        """
        if symbol not in self.data_cache:
            return False
        
        timestamp = self.cache_timestamp.get(symbol, 0)
        return time.time() - timestamp < self.cache_ttl
    
    def _update_cache(self, symbol, market_data):
        """更新缓存
        
        Args:
            symbol (str): 交易对
            market_data (dict): 市场数据
        """
        self.data_cache[symbol] = market_data
        self.cache_timestamp[symbol] = time.time()
    
    def _has_data_changed(self, symbol, market_data):
        """检查数据是否发生变化
        
        Args:
            symbol (str): 交易对
            market_data (dict): 市场数据
            
        Returns:
            bool: 数据是否发生变化
        """
        if symbol not in self.last_market_data:
            return True
        
        last_data = self.last_market_data[symbol]
        
        # 检查关键字段是否发生变化
        key_fields = ['price', 'volume', 'change', 'change_pct']
        for field in key_fields:
            if abs(market_data.get(field, 0) - last_data.get(field, 0)) > 0.0001:
                return True
        
        return False
    
    def _generate_incremental_update(self, symbol, market_data):
        """生成增量更新数据
        
        Args:
            symbol (str): 交易对
            market_data (dict): 市场数据
            
        Returns:
            dict: 增量更新数据
        """
        if symbol not in self.last_market_data:
            return market_data
        
        last_data = self.last_market_data[symbol]
        incremental_data = {}
        
        # 计算变化的字段
        for key, value in market_data.items():
            if key not in last_data or value != last_data[key]:
                incremental_data[key] = value
        
        return incremental_data
    
    def get_network_status(self):
        """获取网络状态
        
        Returns:
            dict: 网络状态信息
        """
        try:
            # 导入网络监控模块
            from network.network_monitor import global_network_monitor
            
            # 获取性能报告
            performance_report = global_network_monitor.get_performance_report()
            
            # 构建网络状态信息
            network_status = {
                'connection_status': True,  # 假设连接正常
                'current_ip': '127.0.0.1',  # 占位符，实际应该从配置或网络模块获取
                'response_times': {
                    '127.0.0.1': performance_report.get('avg_response_time', 0) * 1000  # 转换为毫秒
                },
                'dns_stats': {
                    'success_count': 1,  # 占位符
                    'failure_count': 0  # 占位符
                },
                'websocket_status': self.get_websocket_status()
            }
            
            return network_status
        except Exception as e:
            logger.error(f"获取网络状态失败: {e}")
            return {
                'connection_status': False,
                'current_ip': '未检测',
                'response_times': {},
                'dns_stats': {
                    'success_count': 0,
                    'failure_count': 1
                },
                'websocket_status': False
            }
    
    def get_websocket_status(self):
        """获取WebSocket连接状态
        
        Returns:
            bool: WebSocket连接状态
        """
        try:
            if self.market_data_service and self.market_data_service.ws_client:
                return self.market_data_service.ws_client.is_connected('public')
            return False
        except Exception as e:
            logger.error(f"获取WebSocket状态失败: {e}")
            return False