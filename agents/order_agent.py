from commons.logger_config import get_logger
logger = get_logger(region="Order")
from agents.base_agent import BaseAgent
from services.order_management.order_manager import OrderManager
import time

class OrderAgent(BaseAgent):
    """订单管理智能体，负责处理订单相关的操作"""
    
    def __init__(self, agent_id, config=None):
        super().__init__(agent_id, config)
        self.order_manager = None
        self.pending_orders = {}  # 未成交订单缓存
        self.order_batch_queue = []  # 订单批量处理队列
        self.batch_processing_interval = config.get('batch_processing_interval', 0.5)  # 批量处理间隔（秒）
        self.max_batch_size = config.get('max_batch_size', 20)  # 最大批量大小
        self.is_batch_processing = False
        
        # 订阅事件
        self.subscribe('trading_signal', self.on_trading_signal)
        self.subscribe('agent_status_changed', self.on_agent_status_changed)
        
        logger.info(f"订单管理智能体初始化完成: {self.agent_id}")
    
    def start(self):
        """启动订单管理智能体"""
        super().start()
        
        # 初始化订单管理服务
        from okx_api_client import OKXAPIClient
        api_client = OKXAPIClient(
            api_key=self.config.get('api_key'),
            api_secret=self.config.get('api_secret'),
            passphrase=self.config.get('passphrase'),
            is_test=self.config.get('is_test', False)
        )
        self.order_manager = OrderManager(api_client)
        
        # 启动订单状态更新线程
        self.run_in_thread(self.update_order_status_loop)
        
        # 启动订单批量处理线程
        self.run_in_thread(self.batch_processing_loop)
        
        logger.info(f"订单管理智能体启动完成: {self.agent_id}")
    
    def stop(self):
        """停止订单管理智能体"""
        super().stop()
        logger.info(f"订单管理智能体停止完成: {self.agent_id}")
    
    def update_order_status_loop(self):
        """订单状态更新循环"""
        while self.status == 'running':
            try:
                if self.pending_orders:
                    # 获取所有未成交订单
                    pending_orders = self.order_manager.get_pending_orders()
                    if pending_orders:
                        # 更新未成交订单缓存
                        self.pending_orders = {order['ordId']: order for order in pending_orders}
                        
                        # 发布订单状态更新事件
                        for order in pending_orders:
                            self.publish('order_updated', {
                                'order': order,
                                'timestamp': time.time()
                            })
                    else:
                        # 清空未成交订单缓存
                        self.pending_orders.clear()
                    
                    # 有未成交订单时，保持较高的更新频率
                    time.sleep(3)  # 每3秒更新一次订单状态
                else:
                    # 没有未成交订单时，降低更新频率，减少资源消耗
                    time.sleep(10)  # 每10秒检查一次订单状态
            except Exception as e:
                logger.error(f"订单状态更新失败: {e}")
                time.sleep(5)
    
    def on_trading_signal(self, data):
        """处理交易信号
        
        Args:
            data (dict): 交易信号数据
        """
        logger.info(f"收到交易信号: {data}")
        
        # 解析交易信号
        signal = data
        strategy = signal.get('strategy')
        side = signal.get('side')
        price = signal.get('price')
        symbol = signal.get('inst_id', data.get('symbol', 'BTC-USDT-SWAP'))
        signal_strength = signal.get('signal_strength')
        
        try:
            # 下单
            order = self.place_order(symbol, side, 'limit', price, amount=0.001)  # 固定数量，实际应根据策略计算
            if order:
                # 发布订单已下单事件
                self.publish('order_placed', {
                    'order': order,
                    'signal': signal,
                    'timestamp': time.time()
                })
        except Exception as e:
            logger.error(f"处理交易信号失败: {e}")
    
    def place_order(self, symbol, side, ord_type, price, amount):
        """下单
        
        Args:
            symbol (str): 交易对
            side (str): 买卖方向
            ord_type (str): 订单类型
            price (float): 订单价格
            amount (float): 订单数量
            
        Returns:
            dict: 订单信息
        """
        try:
            logger.info(f"下单请求: {symbol}, {side}, {ord_type}, 价格: {price}, 数量: {amount}")
            
            # 调用订单管理服务下单
            order = self.order_manager.place_order(
                inst_id=symbol,
                side=side,
                ord_type=ord_type,
                sz=str(amount),
                px=str(price) if price else None
            )
            
            if order:
                # 添加到未成交订单缓存
                if order.get('state') in ['live', 'partially_filled']:
                    self.pending_orders[order['ordId']] = order
                
                logger.info(f"下单成功: {order['ordId']}")
                return order
            else:
                logger.error(f"下单失败")
                return None
        except Exception as e:
            logger.error(f"下单异常: {e}")
            return None
    
    def cancel_order(self, order_id, symbol):
        """取消订单
        
        Args:
            order_id (str): 订单ID
            symbol (str): 交易对
            
        Returns:
            dict: 取消结果
        """
        try:
            logger.info(f"取消订单请求: {order_id}, {symbol}")
            
            # 调用订单管理服务取消订单
            result = self.order_manager.cancel_order(symbol, order_id)
            
            if result:
                # 从未成交订单缓存中移除
                if order_id in self.pending_orders:
                    del self.pending_orders[order_id]
                
                # 发布订单已取消事件
                self.publish('order_canceled', {
                    'order_id': order_id,
                    'result': result,
                    'timestamp': time.time()
                })
                
                logger.info(f"取消订单成功: {order_id}")
                return result
            else:
                logger.error(f"取消订单失败")
                return None
        except Exception as e:
            logger.error(f"取消订单异常: {e}")
            return None
    
    def cancel_all_orders(self, symbol=None):
        """取消所有订单
        
        Args:
            symbol (str, optional): 交易对
            
        Returns:
            list: 取消结果列表
        """
        try:
            logger.info(f"取消所有订单请求: {symbol or '所有交易对'}")
            
            # 调用订单管理服务取消所有订单
            results = self.order_manager.cancel_all_orders(symbol)
            
            # 清空未成交订单缓存
            if not symbol:
                self.pending_orders.clear()
            else:
                # 移除指定交易对的未成交订单
                self.pending_orders = {ord_id: order for ord_id, order in self.pending_orders.items() 
                                     if order['instId'] != symbol}
            
            # 发布所有订单已取消事件
            self.publish('all_orders_canceled', {
                'symbol': symbol,
                'results': results,
                'timestamp': time.time()
            })
            
            logger.info(f"取消所有订单成功，共取消 {len(results)} 个订单")
            return results
        except Exception as e:
            logger.error(f"取消所有订单异常: {e}")
            return []
    
    def get_order(self, order_id, symbol=None):
        """获取订单信息
        
        Args:
            order_id (str): 订单ID
            symbol (str, optional): 交易对
            
        Returns:
            dict: 订单信息
        """
        try:
            return self.order_manager.get_order(symbol, order_id)
        except Exception as e:
            logger.error(f"获取订单信息失败: {e}")
            return None
    
    def get_pending_orders(self, symbol=None):
        """获取未成交订单
        
        Args:
            symbol (str, optional): 交易对
            
        Returns:
            list: 未成交订单列表
        """
        try:
            return self.order_manager.get_pending_orders(symbol)
        except Exception as e:
            logger.error(f"获取未成交订单失败: {e}")
            return []
    
    def get_order_history(self, limit=100):
        """获取订单历史
        
        Args:
            limit (int, optional): 返回数量
            
        Returns:
            list: 订单历史列表
        """
        try:
            return self.order_manager.get_order_history(limit)
        except Exception as e:
            logger.error(f"获取订单历史失败: {e}")
            return []
    
    def get_orders(self, symbol=None):
        """获取订单信息
        
        Args:
            symbol (str, optional): 交易对
            
        Returns:
            list: 订单列表
        """
        try:
            return self.order_manager.get_orders(symbol)
        except Exception as e:
            logger.error(f"获取订单信息失败: {e}")
            return []
    
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
        
        if message.get('type') == 'place_order':
            # 下单请求
            result = self.place_order(
                message.get('symbol'),
                message.get('side'),
                message.get('ord_type', 'limit'),
                message.get('price'),
                message.get('amount')
            )
            if message.get('sender'):
                self.send_message(message.get('sender'), {
                    'type': 'order_placed_response',
                    'order': result
                })
        elif message.get('type') == 'cancel_order':
            # 取消订单请求
            result = self.cancel_order(
                message.get('order_id'),
                message.get('symbol')
            )
            if message.get('sender'):
                self.send_message(message.get('sender'), {
                    'type': 'order_canceled_response',
                    'result': result
                })
        elif message.get('type') == 'get_order':
            # 获取订单请求
            result = self.get_order(
                message.get('order_id'),
                message.get('symbol')
            )
            if message.get('sender'):
                self.send_message(message.get('sender'), {
                    'type': 'get_order_response',
                    'order': result
                })
    
    def get_pending_order_count(self):
        """获取未成交订单数量
        
        Returns:
            int: 未成交订单数量
        """
        return len(self.pending_orders)
    
    def batch_processing_loop(self):
        """订单批量处理循环"""
        while self.status == 'running':
            try:
                if self.order_batch_queue:
                    # 处理批量订单
                    self._process_order_batch()
                # 等待下一次批量处理
                time.sleep(self.batch_processing_interval)
            except Exception as e:
                logger.error(f"批量处理订单失败: {e}")
                time.sleep(self.batch_processing_interval)
    
    def _process_order_batch(self):
        """处理批量订单"""
        if not self.order_batch_queue:
            return
        
        # 取出批量队列中的订单
        batch_orders = self.order_batch_queue[:self.max_batch_size]
        self.order_batch_queue = self.order_batch_queue[self.max_batch_size:]
        
        logger.info(f"开始处理批量订单，数量: {len(batch_orders)}")
        
        # 分类订单（按交易对和操作类型）
        orders_by_symbol = {}
        for order_info in batch_orders:
            symbol = order_info['symbol']
            if symbol not in orders_by_symbol:
                orders_by_symbol[symbol] = []
            orders_by_symbol[symbol].append(order_info)
        
        # 按交易对批量处理
        for symbol, orders in orders_by_symbol.items():
            try:
                # 这里应该调用订单管理服务的批量下单方法
                # 由于OKX API可能不支持批量下单，这里使用循环处理
                # 但通过批量收集可以减少API调用频率
                for order_info in orders:
                    order = self._place_single_order(order_info)
                    if order:
                        # 发布订单已下单事件
                        self.publish('order_placed', {
                            'order': order,
                            'signal': order_info.get('signal'),
                            'timestamp': time.time()
                        })
            except Exception as e:
                logger.error(f"处理{symbol}批量订单失败: {e}")
    
    def _place_single_order(self, order_info):
        """下单（单个订单）
        
        Args:
            order_info (dict): 订单信息
            
        Returns:
            dict: 订单信息
        """
        try:
            symbol = order_info['symbol']
            side = order_info['side']
            ord_type = order_info.get('ord_type', 'limit')
            price = order_info.get('price')
            amount = order_info.get('amount', 0.001)
            
            logger.debug(f"批量下单: {symbol}, {side}, {ord_type}, 价格: {price}, 数量: {amount}")
            
            # 调用订单管理服务下单
            order = self.order_manager.place_order(
                inst_id=symbol,
                side=side,
                ord_type=ord_type,
                sz=str(amount),
                px=str(price) if price else None
            )
            
            if order:
                # 添加到未成交订单缓存
                if order.get('state') in ['live', 'partially_filled']:
                    self.pending_orders[order['ordId']] = order
                
                logger.info(f"批量下单成功: {order['ordId']}")
                return order
            else:
                logger.error(f"批量下单失败")
                return None
        except Exception as e:
            logger.error(f"批量下单异常: {e}")
            return None
    
    def place_batch_orders(self, orders):
        """批量下单
        
        Args:
            orders (list): 订单列表
            
        Returns:
            int: 加入队列的订单数量
        """
        try:
            for order_info in orders:
                if isinstance(order_info, dict) and 'symbol' in order_info and 'side' in order_info:
                    self.order_batch_queue.append(order_info)
            
            logger.info(f"批量订单已加入队列，数量: {len(orders)}")
            return len(orders)
        except Exception as e:
            logger.error(f"批量下单失败: {e}")
            return 0