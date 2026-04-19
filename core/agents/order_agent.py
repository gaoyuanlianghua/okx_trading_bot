"""
订单智能体 - 负责订单管理
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base_agent import BaseAgent, AgentConfig
from core.events.event_bus import Event, EventType
from core.events.agent_communication import Message, MessageType
from core.api.exchange_manager import exchange_manager
from core.utils.logger import get_logger
from core.utils.persistence import persistence_manager

logger = get_logger(__name__)


class OrderAgent(BaseAgent):
    """
    订单智能体

    职责：
    1. 下单、撤单
    2. 查询订单状态
    3. 管理未成交订单
    4. 处理订单事件
    """

    def __init__(self, config: AgentConfig, trader=None, rest_client=None, **kwargs):
        super().__init__(config)
        self.trader = trader
        self.rest_client = rest_client
        
        # 处理交易所配置参数
        exchange_name = kwargs.get('exchange_name', 'okx')
        api_key = kwargs.get('api_key')
        api_secret = kwargs.get('api_secret')
        passphrase = kwargs.get('passphrase')
        is_test = kwargs.get('is_test', False)
        
        # 如果没有提供trader或rest_client，尝试从交易所管理器获取
        if not self.trader or not self.rest_client:
            from core.api.exchange_manager import exchange_manager
            if api_key and api_secret and passphrase:
                # 初始化交易所
                exchange = exchange_manager.get_exchange(
                    exchange_name,
                    api_key=api_key,
                    api_secret=api_secret,
                    passphrase=passphrase,
                    is_test=is_test
                )
                if exchange:
                    self.rest_client = exchange
                    # 创建交易器
                    from core.traders.trader_manager import TraderManager
                    self.trader_manager = TraderManager(exchange)
                    # 创建默认交易器
                    self.trader_manager.create_trader('spot', 'default_spot')
                    self.trader = self.trader_manager.get_trader('default_spot')
                    logger.info("✅ 从交易所配置创建了交易器和REST客户端")

        # 订单缓存
        self._orders_cache: Dict[str, Dict] = {}
        self._pending_orders: Dict[str, Dict] = {}
        # 订单创建时间（用于跟踪超时订单）
        self._order_creation_times: Dict[str, float] = {}

        # 交易记录
        self._trade_history: List[Dict] = []

        # 订单同步缓存
        self._order_sync_cache = {
            'orders': None,
            'pending_orders': None,
            'order_history': None,
            'timestamp': 0
        }
        self._order_cache_ttl = 3  # 订单缓存过期时间（秒）

        # 收益跟踪
        self._total_pnl = 0.0
        self._total_fees = 0.0

        # 统计
        self._order_count = 0
        self._filled_count = 0
        self._cancelled_count = 0
        # 执行计数（用于控制同步频率）
        self._execution_count = 0
        # 自动撤单配置
        self._order_timeout_seconds = 60  # 订单超时时间（秒）
        
        # 账户初始权益
        self._initial_balance = None  # 动态获取的初始权益

        # 账户同步缓存
        self._account_cache = {
            'balance': None,
            'positions': None,
            'timestamp': 0
        }
        self._cache_ttl = 5  # 缓存过期时间（秒）

        # 同步统计
        self._sync_stats = {
            'total_syncs': 0,
            'successful_syncs': 0,
            'failed_syncs': 0,
            'avg_sync_time': 0,
            'total_sync_time': 0,
            'cached_syncs': 0
        }

        # 加载上次的状态
        self._load_state()

        logger.info(f"订单智能体初始化完成: {self.agent_id}")

    async def _initialize(self):
        """初始化"""
        self.register_message_handler(
            MessageType.COMMAND_START, self._handle_order_command
        )

        # 订阅订单事件
        self.event_bus.subscribe(
            EventType.ORDER_CREATED, self._on_order_event, async_callback=True
        )
        self.event_bus.subscribe(
            EventType.ORDER_UPDATED, self._on_order_event, async_callback=True
        )
        self.event_bus.subscribe(
            EventType.ORDER_FILLED, self._on_order_event, async_callback=True
        )
        self.event_bus.subscribe(
            EventType.ORDER_CANCELLED, self._on_order_event, async_callback=True
        )
        # 订阅ORDER_EVENT事件（来自协调智能体）
        self.event_bus.subscribe(
            EventType.ORDER_EVENT, self._on_order_event, async_callback=True
        )

        logger.info("订单智能体初始化完成")

    async def _cleanup(self):
        """清理"""
        # 保存当前状态
        self._save_state()
        self._orders_cache.clear()
        self._pending_orders.clear()
        logger.info("订单智能体已清理")
    
    def save_state_now(self):
        """立即保存状态"""
        self._save_state()
    
    def _load_state(self):
        """加载上次的状态"""
        try:
            state = persistence_manager.load_order_agent_state()
            if state:
                # 加载订单缓存
                self._orders_cache = state.get('orders_cache', {})
                self._pending_orders = state.get('pending_orders', {})
                self._order_creation_times = state.get('order_creation_times', {})
                
                # 加载交易记录
                self._trade_history = state.get('trade_history', [])
                
                # 加载收益跟踪
                self._total_pnl = state.get('total_pnl', 0.0)
                self._total_fees = state.get('total_fees', 0.0)
                
                # 加载统计
                self._order_count = state.get('order_count', 0)
                self._filled_count = state.get('filled_count', 0)
                self._cancelled_count = state.get('cancelled_count', 0)
                
                # 加载账户初始权益
                self._initial_balance = state.get('initial_balance', None)
                
                logger.info(f"成功加载订单智能体状态: 初始权益={self._initial_balance}, 交易记录数={len(self._trade_history)}")
            else:
                logger.info("未找到上次的订单智能体状态")
        except Exception as e:
            logger.error(f"加载订单智能体状态失败: {e}")
    
    def _save_state(self):
        """保存当前状态"""
        try:
            state = {
                'orders_cache': self._orders_cache,
                'pending_orders': self._pending_orders,
                'order_creation_times': self._order_creation_times,
                'trade_history': self._trade_history,
                'total_pnl': self._total_pnl,
                'total_fees': self._total_fees,
                'order_count': self._order_count,
                'filled_count': self._filled_count,
                'cancelled_count': self._cancelled_count,
                'initial_balance': self._initial_balance
            }
            success = persistence_manager.save_order_agent_state(state)
            if success:
                logger.info(f"成功保存订单智能体状态: 初始权益={self._initial_balance}, 交易记录数={len(self._trade_history)}")
            else:
                logger.error("保存订单智能体状态失败")
        except Exception as e:
            logger.error(f"保存订单智能体状态失败: {e}")

    async def _execute_cycle(self):
        """执行周期"""
        # 定期同步订单状态
        await self._sync_orders()
        # 每30秒执行一次完整的账户和订单同步，避免过于频繁的API调用
        if self._execution_count % 3 == 0:  # 每3个周期执行一次，约30秒
            await self.sync_account_and_orders()
        # 检查超时订单并撤销
        await self._check_timeout_orders()
        self._execution_count += 1
        await asyncio.sleep(10)

    async def _check_timeout_orders(self):
        """检查并撤销超时订单"""
        import time
        current_time = time.time()
        timeout_orders = []
        
        # 找出超时的订单
        for order_id, creation_time in list(self._order_creation_times.items()):
            if current_time - creation_time > self._order_timeout_seconds:
                timeout_orders.append(order_id)
        
        # 撤销超时订单
        for order_id in timeout_orders:
            try:
                # 从缓存获取订单信息
                order_info = self._orders_cache.get(order_id)
                if not order_info:
                    # 如果缓存中没有，从API获取
                    order_info = await self.rest_client.get_order_info(
                        inst_id="BTC-USDT",  # 默认产品，实际应该从订单信息中获取
                        ord_id=order_id
                    )
                
                if order_info and order_info.get("state") in ["live", "partially_filled"]:
                    # 撤销订单
                    result = await self.cancel_order({
                        "order_id": order_id,
                        "inst_id": order_info.get("instId", "BTC-USDT")
                    })
                    
                    if result.get("success"):
                        logger.info(f"自动撤销超时订单: {order_id} (超过{self._order_timeout_seconds}秒未成交)")
                        # 从创建时间记录中删除
                        self._order_creation_times.pop(order_id, None)
                else:
                    # 订单状态不是未成交，从创建时间记录中删除
                    self._order_creation_times.pop(order_id, None)
                    
            except Exception as e:
                logger.error(f"检查超时订单时出错: {e}")
                # 从创建时间记录中删除，避免重复处理
                self._order_creation_times.pop(order_id, None)

    async def _sync_orders(self):
        """同步订单状态"""
        import time
        current_time = time.time()

        # 检查缓存
        if current_time - self._order_sync_cache['timestamp'] < self._order_cache_ttl:
            logger.debug("使用缓存的订单数据")
            if self._order_sync_cache['pending_orders']:
                self._pending_orders = self._order_sync_cache['pending_orders']
            if self._order_sync_cache['orders']:
                for order_id, order in self._order_sync_cache['orders'].items():
                    self._orders_cache[order_id] = order
            return

        if not self.trader and not self.rest_client:
            return

        try:
            # 优先使用交易器获取未成交订单
            if self.trader:
                pending = await self.trader.get_open_orders('BTC-USDT')
            else:
                pending = await self.rest_client.get_pending_orders()
            
            pending_orders_dict = {order.get("ordId"): order for order in pending}
            self._pending_orders = pending_orders_dict

            # 更新缓存
            orders_dict = {}
            for order in pending:
                order_id = order.get("ordId")
                self._orders_cache[order_id] = order
                orders_dict[order_id] = order

            # 更新同步缓存
            self._order_sync_cache.update({
                'orders': orders_dict,
                'pending_orders': pending_orders_dict,
                'timestamp': current_time
            })

        except Exception as e:
            logger.error(f"同步订单失败: {e}")

    async def sync_account_and_orders(self):
        """同步账户余额和订单状态
        
        确保本地记录与实际账户一致，保持数据以实际账户为准
        处理手动卖出的订单，确保交易历史与实际账户一致
        """
        import time
        start_time = time.time()
        self._sync_stats['total_syncs'] += 1

        # 检查缓存
        current_time = time.time()
        if current_time - self._account_cache['timestamp'] < self._cache_ttl:
            self._sync_stats['cached_syncs'] += 1
            logger.debug("使用缓存的账户数据")
            return {
                'success': True,
                'btc_balance': self._account_cache.get('btc_balance', 0.0),
                'usdt_balance': self._account_cache.get('usdt_balance', 0.0),
                'cached': True
            }

        if not self.trader and not self.rest_client:
            return {'success': False, 'error': '交易器和REST客户端均未初始化'}

        try:
            logger.info("🔄 开始同步账户和订单状态...")
            
            # 1. 同步账户余额
            if self.trader:
                balance = await self.trader.get_account_info()
            else:
                balance = await self.rest_client.get_account_balance()
                
            if balance:
                logger.info("✅ 账户余额同步成功")
                
                # 提取BTC和USDT余额
                btc_balance = 0.0
                usdt_balance = 0.0
                
                if isinstance(balance, dict):
                    details = balance.get('details', [])
                    for item in details:
                        if isinstance(item, dict):
                            ccy = item.get('ccy')
                            if ccy == 'BTC':
                                btc_balance = float(item.get('availBal', 0) or 0)
                            elif ccy == 'USDT':
                                usdt_balance = float(item.get('availBal', 0) or 0)
                
                logger.info(f"📊 账户余额: BTC={btc_balance:.8f}, USDT={usdt_balance:.2f}")
                
                # 更新缓存
                self._account_cache.update({
                    'balance': balance,
                    'btc_balance': btc_balance,
                    'usdt_balance': usdt_balance,
                    'timestamp': current_time
                })
            
            # 2. 同步订单状态
            await self._sync_orders()
            
            # 3. 同步订单历史（通过API获取的实际订单）
            # 已注释掉，避免显示过多历史订单
            # await self._sync_order_history()
            
            # 4. 同步OKX账户中的实际订单与本地记录
            # 已注释掉，避免显示过多历史订单
            # await self.sync_orders_with_exchange()
            
            # 5. 清理无效订单（已成交但状态未更新的订单）
            self._cleanup_invalid_orders()
            
            # 更新统计
            sync_time = time.time() - start_time
            self._sync_stats['successful_syncs'] += 1
            self._sync_stats['total_sync_time'] += sync_time
            if self._sync_stats['successful_syncs'] > 0:
                self._sync_stats['avg_sync_time'] = self._sync_stats['total_sync_time'] / self._sync_stats['successful_syncs']
            
            logger.info("✅ 账户和订单状态同步完成")
            return {
                'success': True,
                'btc_balance': btc_balance,
                'usdt_balance': usdt_balance,
                'sync_time': sync_time
            }
        
        except Exception as e:
            logger.error(f"❌ 同步账户和订单失败: {e}")
            self._sync_stats['failed_syncs'] += 1
            return {'success': False, 'error': str(e)}

    def get_sync_stats(self) -> Dict[str, Any]:
        """获取同步统计信息"""
        return self._sync_stats

    def clear_account_cache(self):
        """清空账户缓存"""
        self._account_cache = {
            'balance': None,
            'positions': None,
            'timestamp': 0
        }
        logger.info("账户缓存已清空")

    def clear_order_cache(self):
        """清空订单同步缓存"""
        self._order_sync_cache = {
            'orders': None,
            'pending_orders': None,
            'order_history': None,
            'timestamp': 0
        }
        logger.info("订单同步缓存已清空")

    def get_order_sync_cache(self) -> Dict[str, Any]:
        """获取订单同步缓存状态"""
        return self._order_sync_cache

    async def _sync_order_history(self):
        """同步订单历史
        
        通过API获取历史订单，同步到订单智能体的交易记录
        确保每个订单都能被正确处理，包括手动卖出的订单
        """
        import time
        start_time = time.time()

        # 检查缓存
        current_time = time.time()
        if current_time - self._order_sync_cache['timestamp'] < self._order_cache_ttl:
            logger.debug("使用缓存的订单历史数据")
            return

        if not self.trader and not self.rest_client:
            return

        try:
            logger.info("🔄 开始同步订单历史...")
            
            # 优先使用交易器获取订单历史
            if self.trader:
                order_history = await self.trader.get_order_history('MARGIN', 'BTC-USDT', 100)  # 最多获取100条记录
            else:
                order_history = await self.rest_client.get_order_history('MARGIN', 'BTC-USDT', 100)  # 最多获取100条记录
            
            if order_history and isinstance(order_history, list):
                logger.info(f"✅ 获取到 {len(order_history)} 条历史订单")
                
                # 批量处理订单
                new_trades = []
                updated_trades = []
                
                # 创建交易ID映射，提高查找效率
                trade_id_map = {trade.get('trade_id'): trade for trade in self._trade_history}
                
                # 处理每条历史订单
                for order in order_history:
                    ord_id = order.get('ordId')
                    side = order.get('side')
                    state = order.get('state')
                    filled_size = order.get('fillSz', '0')
                    # 对于已成交的订单，使用平均成交价格
                    price = order.get('avgPx', order.get('px', '0'))
                    create_time = order.get('cTime')
                    td_mode = order.get('tdMode', 'cash')  # 获取交易模式
                    
                    # 只处理已成交的订单
                    if state == 'filled' and float(filled_size) > 0:
                        # 检查是否已经存在该订单
                        existing_trade = trade_id_map.get(ord_id)
                        
                        if not existing_trade:
                            # 创建新的交易记录，使用与_create_trade_record方法一致的结构
                            trade_record = {
                                "trade_id": ord_id,
                                "inst_id": order.get('instId', 'BTC-USDT'),
                                "side": side,
                                "ord_type": order.get('ordType', 'market'),
                                "price": float(price),
                                "size": float(order.get('sz', filled_size)),
                                "filled_size": float(filled_size),
                                "fee": float(order.get('fee', '0')),
                                "state": state,
                                "timestamp": create_time,
                                "fill_time": order.get('fillTime'),
                                "td_mode": td_mode,  # 保存交易模式
                                "source": "API"  # 标记来源为API，确保交易依据来自API返回的信息
                            }
                            
                            new_trades.append(trade_record)
                        else:
                            # 更新现有订单状态，确保结构一致
                            existing_trade['state'] = state
                            existing_trade['filled_size'] = float(filled_size)
                            existing_trade['price'] = float(price)
                            existing_trade['size'] = float(order.get('sz', filled_size))
                            existing_trade['fee'] = float(order.get('fee', '0'))
                            existing_trade['timestamp'] = create_time
                            existing_trade['fill_time'] = order.get('fillTime')
                            existing_trade['td_mode'] = td_mode  # 保存交易模式
                            existing_trade['source'] = "API"  # 确保标记来源为API
                            updated_trades.append(existing_trade)
                    elif state == 'filled' and float(filled_size) > 0 and td_mode != 'cross':
                        # 跳过非杠杆交易的订单
                        logger.debug(f"跳过非杠杆交易订单: {ord_id} (td_mode={td_mode})")
            
            # 批量添加新交易
            if new_trades:
                self._trade_history.extend(new_trades)
                for trade in new_trades:
                    logger.info(f"✅ 新增API杠杆交易订单记录: {trade['trade_id']} ({trade['side']} {trade['filled_size']} BTC @ {trade['price']} USDT, td_mode={trade['td_mode']})")
            
            # 批量更新交易
            if updated_trades:
                for trade in updated_trades:
                    logger.info(f"✅ 更新API杠杆交易订单状态: {trade['trade_id']} - {trade['state']}")
            
            # 清理交易历史，只保留来自API的杠杆交易订单
            self._trade_history = [trade for trade in self._trade_history if trade.get('td_mode') == 'cross' and trade.get('source') == 'API']
            logger.info(f"✅ 清理交易历史，只保留API杠杆交易订单，当前交易历史长度: {len(self._trade_history)}")
            
            # 更新同步缓存
            self._order_sync_cache['order_history'] = order_history
            self._order_sync_cache['timestamp'] = current_time
            
            sync_time = time.time() - start_time
            logger.info(f"✅ 订单历史同步完成，耗时: {sync_time:.3f}s")
            
        except Exception as e:
            logger.error(f"❌ 同步订单历史失败: {e}")

    def _cleanup_invalid_orders(self):
        """清理无效订单
        
        移除已成交但状态未更新的订单，确保本地记录与实际一致
        """
        try:
            # 清理长时间未更新的订单
            import time
            current_time = time.time()
            expired_orders = []
            
            for order_id, create_time in self._order_creation_times.items():
                if current_time - create_time > 3600:  # 1小时过期
                    expired_orders.append(order_id)
            
            for order_id in expired_orders:
                self._order_creation_times.pop(order_id, None)
                self._pending_orders.pop(order_id, None)
                self._orders_cache.pop(order_id, None)
                logger.info(f"清理过期订单: {order_id}")
        
        except Exception as e:
            logger.error(f"清理无效订单失败: {e}")

    async def _handle_order_command(self, message: Message):
        """处理订单命令"""
        payload = message.payload
        action = payload.get("action")

        if action == "place":
            result = await self.place_order(payload)
        elif action == "cancel":
            result = await self.cancel_order(payload)
        elif action == "query":
            result = await self.query_order(payload)
        else:
            result = {"success": False, "error": "未知命令"}

        # 发送响应
        response = Message.create_response(
            sender=self.agent_id,
            receiver=message.sender,
            request_message=message,
            payload=result,
        )
        await self.send_message(response)

    async def _on_order_event(self, event: Event):
        """处理订单事件"""
        order_data = event.data.get("order", {})
        order_id = order_data.get("ordId")

        if order_id:
            self._orders_cache[order_id] = order_data
            self.metrics.update_activity()

            # 更新统计
            state = order_data.get("state")
            if state == "filled":
                self._filled_count += 1
                self._pending_orders.pop(order_id, None)
                # 从订单创建时间记录中删除
                self._order_creation_times.pop(order_id, None)

                # 从API获取最新的订单信息，确保包含手续费信息
                try:
                    inst_id = order_data.get("instId", "BTC-USDT")
                    latest_order_data = await self.rest_client.get_order_info(inst_id=inst_id, ord_id=order_id)
                    if latest_order_data:
                        order_data = latest_order_data
                        # 更新缓存
                        self._orders_cache[order_id] = order_data
                except Exception as e:
                    logger.error(f"获取订单信息失败: {e}")

                # 记录交易
                trade = self._create_trade_record(order_data)
                if trade:
                    self._trade_history.append(trade)
                    # 计算收益
                    self._calculate_pnl(trade)
                    # 保存状态，确保交易记录被持久化
                    self._save_state()
                    logger.info(f"交易记录已保存: {trade}")
                else:
                    logger.error(f"创建交易记录失败，订单数据: {order_data}")
            elif state == "canceled":
                self._cancelled_count += 1
                self._pending_orders.pop(order_id, None)
                # 从订单创建时间记录中删除
                self._order_creation_times.pop(order_id, None)

    def _create_trade_record(self, order_data: Dict) -> Dict:
        """创建交易记录"""
        try:
            # 安全获取并转换字段
            def safe_float(value, default=0.0):
                if value is None:
                    return default
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return default
            
            # 只记录消息，不依赖本地生成的订单信息
            # 交易的依据来自OKX API返回的订单信息
            trade = {
                "trade_id": order_data.get("ordId"),
                "inst_id": order_data.get("instId"),
                "side": order_data.get("side"),
                "ord_type": order_data.get("ordType"),
                "price": safe_float(order_data.get("avgPx")),
                "size": safe_float(order_data.get("sz")),
                "filled_size": safe_float(order_data.get("accFillSz")),
                "fee": safe_float(order_data.get("fee")),
                "state": order_data.get("state"),
                "timestamp": order_data.get("cTime"),
                "fill_time": order_data.get("fillTime"),
                "source": "API"  # 标记来源为API，确保交易依据来自API返回的信息
            }
            # 确保关键字段存在
            if not trade.get("trade_id"):
                logger.error("交易记录缺少订单ID")
                return {}
            return trade
        except Exception as e:
            logger.error(f"创建交易记录失败: {e}")
            return {}

    def _calculate_pnl(self, trade: Dict):
        """计算交易收益"""
        try:
            # 简化的PnL计算
            # 实际应用中需要根据当前价格和持仓情况计算
            # 这里仅记录交易信息，实际PnL计算需要更复杂的逻辑
            fee = trade.get("fee", 0)
            self._total_fees += fee
            logger.info(f"交易手续费: {fee} {trade.get('inst_id', 'BTC-USDT')}")
            logger.info(f"累计手续费: {self._total_fees} {trade.get('inst_id', 'BTC-USDT')}")
            
            # 发布交易事件，通知策略智能体
            import asyncio
            asyncio.ensure_future(self._publish_trade_event(trade))

        except Exception as e:
            logger.error(f"计算收益失败: {e}")
    
    async def _publish_trade_event(self, trade: Dict):
        """发布交易事件"""
        try:
            from core.events.event_bus import Event, EventType
            
            # 发布交易事件
            await self.event_bus.publish_async(
                Event(
                    type=EventType.TRADE_EVENT,
                    source=self.agent_id,
                    data={"trade": trade, "total_fees": self._total_fees},
                )
            )
            logger.info(f"发布交易事件: {trade.get('trade_id')}")
        except Exception as e:
            logger.error(f"发布交易事件失败: {e}")

    # ========== 公共接口 ==========

    async def place_order(self, params: Dict) -> Dict:
        """
        下单

        Args:
            params: 订单参数

        Returns:
            Dict: 下单结果
        """
        if not self.trader and not self.rest_client:
            return {"success": False, "error": "交易器和REST客户端均未初始化"}

        try:
            # 检查是否为平仓操作或做空操作
            side = params.get("side", "buy")
            inst_id = params.get("inst_id", "BTC-USDT")
            is_short_sell = params.get("is_short_sell", False)
            
            # 减少下单前的API调用，优先使用本地缓存和历史数据
            logger.info(f"准备下单: {side} {inst_id} - 数量: {params.get('sz', '0')}")
            
            # 检查是否跳过收益率检查
            skip_return_check = params.get("skip_return_check", False)
            
            # 如果是做空操作，跳过持仓检查，直接执行做空
            if is_short_sell:
                logger.info(f"🔄 做空操作：跳过持仓检查，直接执行做空")
            # 如果是平仓操作，检查未实现盈亏率和余额
            elif side == "sell":
                try:
                    # 优先使用本地交易历史数据，减少API调用
                    eligible_trades = []
                    total_btc_amount = 0.0
                    current_price = 0.0
                    
                    # 1. 先从本地交易历史获取数据
                    # 查找所有未卖出的买入订单
                    buy_trades = []
                    for trade in self._trade_history:
                        if trade.get('side') == 'buy' and trade.get('state') == 'filled':
                            # 检查是否已经卖出
                            sold = False
                            for t in self._trade_history:
                                if t.get('side') == 'sell' and t.get('state') == 'filled' and t.get('buy_trade_id') == trade.get('trade_id'):
                                    sold = True
                                    break
                            if not sold:
                                buy_trades.append(trade)
                    
                    if not buy_trades:
                        # 如果没有未卖出的买入订单，并且跳过收益率检查，执行做空操作
                        if skip_return_check:
                            logger.info("没有未卖出的买入订单，执行做空操作")
                            is_short_sell = True
                        else:
                            return {"success": False, "error": "没有未卖出的买入订单"}
                    
                    # 2. 只在需要时获取当前价格
                    # 尝试从本地缓存或市场数据智能体获取价格
                    if self.market_data_agent:
                        ticker = self.market_data_agent.get_ticker(inst_id)
                        if ticker:
                            current_price = float(ticker.get("last", 0))
                            logger.info(f"从市场数据智能体获取当前价格: {current_price:.2f} USDT")
                    
                    # 如果没有本地价格数据，才从API获取
                    if current_price <= 0 and self.rest_client:
                        try:
                            ticker = await self.rest_client.get_ticker(inst_id)
                            if ticker:
                                current_price = float(ticker.get('last', 0) or 0)
                                logger.info(f"从API获取当前价格: {current_price:.2f} USDT")
                        except Exception as e:
                            logger.error(f"获取当前价格失败: {e}")
                    
                    # 3. 计算收益率并筛选合格订单
                    if not is_short_sell:
                        fee_rate = 0.002  # 手续费率
                        for trade in buy_trades:
                            buy_price = trade.get('price', 0)
                            if buy_price > 0 and current_price > 0:
                                order_return = (current_price - buy_price) / buy_price
                                # 检查是否达到卖出条件
                                if skip_return_check or order_return > fee_rate:
                                    eligible_trades.append(trade)
                                    btc_amount = trade.get('filled_size', 0)
                                    total_btc_amount += btc_amount
                                    if skip_return_check:
                                        logger.info(f"订单ID {trade.get('trade_id')} 跳过收益率检查，直接执行卖出")
                                    else:
                                        logger.info(f"订单ID {trade.get('trade_id')} 达到卖出条件: 收益率 {order_return * 100:.2f}% > 手续费率 {fee_rate * 100:.2f}%")
                        
                        if not eligible_trades:
                            return {"success": False, "error": "没有达到卖出条件的订单"}
                        
                        # 4. 只在必要时检查账户余额
                        # 只有当本地历史数据和API价格都获取失败时，才需要检查余额
                        if total_btc_amount > 0:
                            # 优先使用历史订单总和，减少API调用
                            sell_amount = total_btc_amount
                            
                            # 只在需要时检查实际余额
                            actual_btc_balance = total_btc_amount  # 默认使用历史数据
                            if self.rest_client:
                                try:
                                    # 尝试获取余额，但作为辅助检查
                                    balance = await self.rest_client.get_account_balance()
                                    if balance and isinstance(balance, dict):
                                        details = balance.get('details', [])
                                        for item in details:
                                            if isinstance(item, dict) and item.get('ccy') == 'BTC':
                                                avail_bal_str = item.get('availBal', 0)
                                                try:
                                                    actual_btc_balance = float(avail_bal_str)
                                                    logger.info(f"从API获取BTC可用余额: {actual_btc_balance:.8f}")
                                                except (ValueError, TypeError):
                                                    pass
                                                break
                                except Exception as e:
                                    logger.warning(f"获取余额失败，使用历史数据: {e}")
                            
                            # 使用实际余额和历史数据的较小值
                            sell_amount = min(total_btc_amount, actual_btc_balance)
                            
                            if sell_amount <= 0:
                                return {"success": False, "error": f"BTC余额不足，可用: {actual_btc_balance:.8f} BTC"}
                            
                            # 确保卖出数量格式正确
                            sell_amount = round(sell_amount, 8)
                            params["sz"] = f"{sell_amount:.8f}"
                            
                            logger.info(f"设置卖出数量: {sell_amount:.8f} BTC")
                            logger.info(f"  历史订单总和: {total_btc_amount:.8f} BTC")
                            logger.info(f"  实际可用余额: {actual_btc_balance:.8f} BTC")
                            logger.info(f"  最终卖出数量: {sell_amount:.8f} BTC")
                            logger.info(f"共 {len(eligible_trades)} 笔达到卖出条件的订单")
                        else:
                            return {"success": False, "error": "达到卖出条件的订单BTC数量总和为0"}
                                
                except Exception as e:
                    logger.error(f"检查未实现盈亏率和余额失败: {e}")
                    import traceback
                    logger.error(f"详细错误: {traceback.format_exc()}")
            
            # 计算手续费率（买入0.1% + 卖出0.1% = 0.2%）
            fee_rate = 0.002
            
            # 检查是否跳过收益率检查
            skip_return_check = params.get("skip_return_check", False)
            
            # 如果不是做空操作且不跳过收益率检查，检查收益率是否大于手续费率
            if not is_short_sell and not skip_return_check:
                # 计算预期收益率
                expected_return = self._calculate_expected_return(params)
                
                # 检查收益率是否大于手续费率
                if expected_return <= fee_rate:
                    # 收益率低于手续费，不予交易
                    reason = f"收益率低于手续费: {expected_return:.4f} <= {fee_rate:.4f}"
                    logger.warning(f"拒绝交易: {reason}")
                    
                    # 发布低收益率事件，通知策略智能体
                    await self._publish_low_return_event(params, expected_return, reason)
                    
                    return {"success": False, "error": reason}
            else:
                logger.info("🔄 跳过收益率检查，直接执行交易")

            # 优先使用交易器下单
            order_id = None
            max_retries = 3
            retry_delay = 2.0
            
            for retry in range(max_retries + 1):
                try:
                    if self.trader:
                        # 对于做空操作，确保使用杠杆交易模式
                        td_mode = params.get("td_mode", "cross")
                        lever = params.get("lever", "20")  # 默认20倍杠杆
                        
                        # 构建订单参数
                        order_params = {
                            "inst_id": inst_id,
                            "side": side,
                            "ord_type": params.get("ord_type", "limit"),
                            "sz": str(params.get("sz", "0")),
                            "px": str(params.get("px", "")),
                            "td_mode": td_mode,
                            "lever": lever,
                        }
                        
                        # 执行下单
                        if side == "buy":
                            logger.info(f"执行买入操作: {order_params} (重试: {retry}/{max_retries})")
                            # 调用 buy 方法
                            if hasattr(self.trader, 'buy'):
                                from decimal import Decimal
                                size = Decimal(str(params.get("sz", "0")))
                                price = Decimal(str(params.get("px", "0"))) if params.get("px") else None
                                order_type = "market" if params.get("ord_type") == "market" else "limit"
                                # 传递额外参数，包括 tgtCcy
                                extra_params = {k: v for k, v in params.items() if k not in ['inst_id', 'side', 'ord_type', 'sz', 'px', 'td_mode', 'lever']}
                                result = await self.trader.buy(
                                    inst_id=inst_id,
                                    size=size,
                                    price=price,
                                    order_type=order_type,
                                    **extra_params
                                )
                                if result.success:
                                    order_id = result.order_id
                                else:
                                    logger.error(f"交易器下单失败: {result.error_message}")
                                    if retry < max_retries:
                                        logger.warning(f"重试下单 ({retry + 1}/{max_retries})")
                                        await asyncio.sleep(retry_delay * (retry + 1))
                                        continue
                                    return {"success": False, "error": result.error_message}
                            else:
                                logger.error("交易器没有 buy 方法")
                                return {"success": False, "error": "交易器没有 buy 方法"}
                        else:
                            logger.info(f"执行卖出操作: {order_params} (重试: {retry}/{max_retries})")
                            # 调用 sell 方法
                            if hasattr(self.trader, 'sell'):
                                from decimal import Decimal
                                size = Decimal(str(params.get("sz", "0")))
                                price = Decimal(str(params.get("px", "0"))) if params.get("px") else None
                                order_type = "market" if params.get("ord_type") == "market" else "limit"
                                # 传递额外参数，包括 is_short_sell
                                extra_params = {k: v for k, v in params.items() if k not in ['inst_id', 'side', 'ord_type', 'sz', 'px', 'td_mode', 'lever']}
                                result = await self.trader.sell(
                                    inst_id=inst_id,
                                    size=size,
                                    price=price,
                                    order_type=order_type,
                                    **extra_params
                                )
                                if result.success:
                                    order_id = result.order_id
                                else:
                                    logger.error(f"交易器下单失败: {result.error_message}")
                                    if retry < max_retries:
                                        logger.warning(f"重试下单 ({retry + 1}/{max_retries})")
                                        await asyncio.sleep(retry_delay * (retry + 1))
                                        continue
                                    return {"success": False, "error": result.error_message}
                            else:
                                logger.error("交易器没有 sell 方法")
                                return {"success": False, "error": "交易器没有 sell 方法"}
                    else:
                        # 使用REST客户端下单
                        logger.info(f"使用REST客户端下单: {side} {inst_id} (重试: {retry}/{max_retries})")
                        order_id = await self.rest_client.place_order(
                            inst_id=inst_id,
                            side=side,
                            ord_type=params.get("ord_type", "limit"),
                            sz=str(params.get("sz", "0")),
                            px=str(params.get("px", "")),
                            td_mode=params.get("td_mode", "cross"),
                            lever=params.get("lever", ""),
                        )
                    
                    if order_id:
                        break
                    elif retry < max_retries:
                        logger.warning(f"下单失败，订单ID为空，重试 ({retry + 1}/{max_retries})")
                        await asyncio.sleep(retry_delay * (retry + 1))
                except Exception as e:
                    logger.error(f"下单异常: {e}")
                    import traceback
                    logger.error(f"详细错误: {traceback.format_exc()}")
                    if retry < max_retries:
                        logger.warning(f"异常重试 ({retry + 1}/{max_retries})")
                        await asyncio.sleep(retry_delay * (retry + 1))
                    else:
                        return {"success": False, "error": f"下单异常: {str(e)}"}
            
            if order_id:
                self._order_count += 1
                # 记录订单创建时间
                import time
                self._order_creation_times[order_id] = time.time()
                logger.info(f"下单成功: {order_id}")
                
                # 构建交易结果
                trade_result = {
                    "success": True,
                    "order_id": order_id,
                    "side": side,
                    "inst_id": inst_id,
                    "price": float(params.get("px", 0) or 0),
                    "size": params.get("sz", "0")
                }
                
                # 自动同步账户数据
                try:
                    from core.utils.account_sync import account_sync_manager
                    if account_sync_manager:
                        await account_sync_manager.sync_after_trade(trade_result)
                except Exception as e:
                    logger.warning(f"交易后自动同步失败: {e}")
                
                # 交易完成后发送邮件
                try:
                    from core.utils.email_utils import get_email_sender
                    email_sender = get_email_sender()
                    if email_sender:
                        subject = f"交易完成通知: {side.upper()} {inst_id}"
                        body = f"交易详情:\n\n"
                        body += f"交易类型: {'买入' if side == 'buy' else '卖出'}\n"
                        body += f"交易对: {inst_id}\n"
                        body += f"交易价格: {float(params.get('px', 0) or 0)}\n"
                        body += f"交易数量: {params.get('sz', '0')}\n"
                        body += f"订单ID: {order_id}\n"
                        body += f"交易时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n"
                        
                        await email_sender.send_email(
                            "528329818@qq.com",
                            subject,
                            body
                        )
                except Exception as e:
                    logger.warning(f"交易后发送邮件失败: {e}")
                
                return {"success": True, "order_id": order_id}
            else:
                return {"success": False, "error": "下单失败"}

        except Exception as e:
            logger.error(f"下单失败: {e}")
            return {"success": False, "error": str(e)}
    
    def _calculate_expected_return(self, params: Dict) -> float:
        """计算预期收益率
        
        Args:
            params: 订单参数
            
        Returns:
            float: 预期收益率
        """
        try:
            # 获取参数中的价格信息
            current_price = params.get('current_price', 0)
            avg_price = params.get('avg_price', 0)
            is_short = params.get('is_short', False)
            
            # 计算飘逸值影响因子
            drift_factor = 0.001  # 0.1%的飘逸值影响
            
            # 计算未来收益价格：现价 + 飘逸值的影响因子
            if is_short:
                # 做空时，价格下跌预期
                future_price = current_price * (1 - drift_factor)
            else:
                # 做多时，价格上涨预期
                future_price = current_price * (1 + drift_factor)
            
            # 考虑手续费影响（买入手续费0.1%，卖出手续费0.1%，总共0.2%）
            fee_rate = 0.002
            
            # 计算预期收益率
            if avg_price > 0:
                if is_short:
                    # 做空收益 = (开仓价格 - 未来收益价格) / 开仓价格 - 手续费率
                    expected_return = (avg_price - future_price) / avg_price - fee_rate
                else:
                    # 做多收益 = (未来收益价格 - 开仓价格) / 开仓价格 - 手续费率
                    expected_return = (future_price - avg_price) / avg_price - fee_rate
            else:
                # 基础预期收益率
                expected_return = 0.005 - fee_rate
            
            # 确保收益率为正
            if expected_return < 0:
                expected_return = 0.001
            
            return expected_return
            
        except Exception as e:
            logger.error(f"计算预期收益率失败: {e}")
            return 0.005
    
    async def _publish_low_return_event(self, params: Dict, expected_return: float, reason: str):
        """发布低收益率事件"""
        try:
            from core.events.event_bus import Event, EventType
            
            # 发布低收益率事件
            await self.event_bus.publish_async(
                Event(
                    type=EventType.LOW_RETURN_EVENT,
                    source=self.agent_id,
                    data={
                        "params": params,
                        "expected_return": expected_return,
                        "reason": reason
                    },
                )
            )
            logger.info(f"发布低收益率事件: {reason}")
        except Exception as e:
            logger.error(f"发布低收益率事件失败: {e}")

    async def cancel_order(self, params: Dict) -> Dict:
        """
        撤单

        Args:
            params: 撤单参数

        Returns:
            Dict: 撤单结果
        """
        if not self.trader and not self.rest_client:
            return {"success": False, "error": "交易器和REST客户端均未初始化"}

        try:
            # 优先使用交易器撤单
            if self.trader:
                success = await self.trader.cancel_order(
                    inst_id=params.get("inst_id", "BTC-USDT"),
                    ord_id=params.get("order_id", ""),
                    cl_ord_id=params.get("cl_ord_id", ""),
                )
            else:
                success = await self.rest_client.cancel_order(
                    inst_id=params.get("inst_id", "BTC-USDT-SWAP"),
                    ord_id=params.get("order_id", ""),
                    cl_ord_id=params.get("cl_ord_id", ""),
                )

            if success:
                logger.info(f"撤单成功: {params.get('order_id')}")
                return {"success": True}
            else:
                return {"success": False, "error": "撤单失败"}

        except Exception as e:
            logger.error(f"撤单失败: {e}")
            return {"success": False, "error": str(e)}

    async def query_order(self, params: Dict) -> Dict:
        """
        查询订单

        Args:
            params: 查询参数

        Returns:
            Dict: 订单信息
        """
        order_id = params.get("order_id")

        # 先从缓存查询
        if order_id in self._orders_cache:
            return {"success": True, "order": self._orders_cache[order_id]}

        # 从API查询
        if self.trader:
            try:
                order = await self.trader.get_order_info(
                    inst_id=params.get("inst_id", "BTC-USDT"), ord_id=order_id
                )
                if order:
                    return {"success": True, "order": order}
            except Exception as e:
                logger.error(f"查询订单失败: {e}")
        elif self.rest_client:
            try:
                order = await self.rest_client.get_order_info(
                    inst_id=params.get("inst_id", "BTC-USDT-SWAP"), ord_id=order_id
                )
                if order:
                    return {"success": True, "order": order}
            except Exception as e:
                logger.error(f"查询订单失败: {e}")

        return {"success": False, "error": "订单不存在"}

    def get_pending_orders(self, inst_id: str = None) -> List[Dict]:
        """获取未成交订单"""
        orders = list(self._pending_orders.values())
        if inst_id:
            orders = [order for order in orders if order.get('inst_id') == inst_id]
        return orders

    def get_trade_history(self, limit: int = 100, inst_id: str = None) -> List[Dict]:
        """获取交易历史"""
        history = self._trade_history[-limit:]
        if inst_id:
            history = [trade for trade in history if trade.get('inst_id') == inst_id]
        return history

    def get_pnl(self) -> Dict[str, float]:
        """获取收益信息"""
        return {"total_pnl": self._total_pnl, "total_fees": self._total_fees}

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        base_status = super().get_status()
        base_status.update(
            {
                "order_count": self._order_count,
                "filled_count": self._filled_count,
                "cancelled_count": self._cancelled_count,
                "pending_count": len(self._pending_orders),
                "trade_count": len(self._trade_history),
                "total_pnl": self._total_pnl,
                "total_fees": self._total_fees,
                "sync_stats": self._sync_stats,
                "account_cache": {
                    'cached': self._account_cache['balance'] is not None,
                    'timestamp': self._account_cache['timestamp'],
                    'btc_balance': self._account_cache.get('btc_balance', 0.0),
                    'usdt_balance': self._account_cache.get('usdt_balance', 0.0)
                }
            }
        )
        return base_status

    async def sync_orders_with_exchange(self):
        """同步OKX账户中的实际订单"""
        await self.sync_account_orders_from_exchange()

    async def sync_account_orders_from_exchange(self):
        """从账户获取订单信息并同步到机器人中
        
        从OKX API获取完整的订单历史，包括现货和杠杆交易
        将API返回的订单信息同步到本地交易记录
        确保本地记录与实际账户一致
        """
        try:
            if not self.trader and not self.rest_client:
                logger.warning("交易器和REST客户端均未初始化，无法同步订单")
                return

            logger.info("🔄 开始从账户获取订单信息并同步到机器人...")

            # 获取OKX账户中的实际订单，包括现货和杠杆交易
            exchange_orders = []
            if self.trader:
                try:
                    # 获取现货交易订单历史
                    spot_orders = await self.trader.get_order_history(
                        'SPOT',  # inst_type
                        'BTC-USDT',  # inst_id
                        200  # 最多获取200条记录
                    )
                    exchange_orders.extend(spot_orders)
                    logger.info(f"获取现货订单历史成功: {len(spot_orders)}条")
                except Exception as e:
                    logger.error(f"获取现货订单历史失败: {e}")
                
                try:
                    # 获取杠杆交易订单历史
                    margin_orders = await self.trader.get_order_history(
                        'MARGIN',  # inst_type
                        'BTC-USDT',  # inst_id
                        200  # 最多获取200条记录
                    )
                    exchange_orders.extend(margin_orders)
                    logger.info(f"获取杠杆订单历史成功: {len(margin_orders)}条")
                except Exception as e:
                    logger.error(f"获取杠杆订单历史失败: {e}")
            else:
                try:
                    # 获取现货交易订单历史
                    spot_orders = await self.rest_client.get_order_history(
                        'SPOT',  # inst_type
                        'BTC-USDT',  # inst_id
                        200  # 最多获取200条记录
                    )
                    exchange_orders.extend(spot_orders)
                    logger.info(f"获取现货订单历史成功: {len(spot_orders)}条")
                except Exception as e:
                    logger.error(f"获取现货订单历史失败: {e}")
                
                try:
                    # 获取杠杆交易订单历史
                    margin_orders = await self.rest_client.get_order_history(
                        'MARGIN',  # inst_type
                        'BTC-USDT',  # inst_id
                        200  # 最多获取200条记录
                    )
                    exchange_orders.extend(margin_orders)
                    logger.info(f"获取杠杆订单历史成功: {len(margin_orders)}条")
                except Exception as e:
                    logger.error(f"获取杠杆订单历史失败: {e}")

            if not exchange_orders:
                logger.warning("无法获取OKX账户订单")
                return

            logger.info(f"总共获取到 {len(exchange_orders)} 条订单记录")

            # 处理OKX返回的订单数据，确保格式一致
            processed_orders = []
            for order in exchange_orders:
                # 确保订单数据格式一致
                if isinstance(order, dict):
                    # 标准化订单数据
                    processed_order = {
                        'ordId': order.get('ordId'),
                        'side': order.get('side'),
                        'state': order.get('state'),
                        'fillSz': order.get('fillSz', '0'),
                        'avgPx': order.get('avgPx', order.get('px', '0')),
                        'cTime': order.get('cTime'),
                        'fillTime': order.get('fillTime'),
                        'ordType': order.get('ordType', 'market'),
                        'sz': order.get('sz', '0'),
                        'fee': order.get('fee', '0'),
                        'instId': order.get('instId', 'BTC-USDT'),
                        'tdMode': order.get('tdMode', 'cash')
                    }
                    processed_orders.append(processed_order)

            # 统计实际账户中的订单
            exchange_buy_orders = [o for o in processed_orders if o.get('side') == 'buy' and o.get('state') == 'filled']
            exchange_sell_orders = [o for o in processed_orders if o.get('side') == 'sell' and o.get('state') == 'filled']

            logger.info(f"OKX账户 - 买入订单: {len(exchange_buy_orders)}, 卖出订单: {len(exchange_sell_orders)}")

            # 计算未卖出订单数量
            exchange_unsold = len(exchange_buy_orders) - len(exchange_sell_orders)
            logger.info(f"未卖出订单 - OKX账户: {exchange_unsold}")

            # 同步API订单到本地交易记录
            new_trades = 0
            updated_trades = 0
            
            for order in processed_orders:
                ord_id = order.get('ordId')
                state = order.get('state')
                filled_size = order.get('fillSz', '0')
                
                # 只处理已成交的订单
                if state == 'filled' and float(filled_size) > 0:
                    # 检查是否已经存在该订单
                    existing_trade = None
                    for trade in self._trade_history:
                        if trade.get('trade_id') == ord_id:
                            existing_trade = trade
                            break
                    
                    if not existing_trade:
                        # 创建新的交易记录
                        trade_record = {
                            "trade_id": ord_id,
                            "inst_id": order.get('instId', 'BTC-USDT'),
                            "side": order.get('side'),
                            "ord_type": order.get('ordType', 'market'),
                            "price": float(order.get('avgPx', order.get('px', '0'))),
                            "size": float(order.get('sz', filled_size)),
                            "filled_size": float(filled_size),
                            "fee": float(order.get('fee', '0')),
                            "state": state,
                            "timestamp": order.get('cTime'),
                            "fill_time": order.get('fillTime'),
                            "td_mode": order.get('tdMode', 'cash'),
                            "source": "API"
                        }
                        
                        # 添加到交易历史
                        self._trade_history.append(trade_record)
                        new_trades += 1
                        logger.info(f"✅ 新增API交易订单记录: {ord_id} ({order.get('side')} {filled_size} BTC @ {order.get('avgPx', order.get('px', '0'))} USDT)")
                    else:
                        # 更新现有订单状态
                        existing_trade['state'] = state
                        existing_trade['filled_size'] = float(filled_size)
                        existing_trade['price'] = float(order.get('avgPx', order.get('px', '0')))
                        existing_trade['size'] = float(order.get('sz', filled_size))
                        existing_trade['fee'] = float(order.get('fee', '0'))
                        existing_trade['timestamp'] = order.get('cTime')
                        existing_trade['fill_time'] = order.get('fillTime')
                        existing_trade['td_mode'] = order.get('tdMode', 'cash')
                        existing_trade['source'] = "API"
                        updated_trades += 1
                        logger.info(f"✅ 更新API交易订单状态: {ord_id} - {state}")

            logger.info(f"✅ 订单同步完成: 新增 {new_trades} 条，更新 {updated_trades} 条")

            # 清理本地交易记录，只保留最近的200条记录
            if len(self._trade_history) > 200:
                self._trade_history = self._trade_history[-200:]
                logger.info(f"✅ 清理交易历史，只保留最近的200条记录，当前交易历史长度: {len(self._trade_history)}")

            # 保存状态
            self._save_state()
            logger.info("✅ 订单同步完成并保存状态")

        except Exception as e:
            logger.error(f"同步订单失败: {e}")
