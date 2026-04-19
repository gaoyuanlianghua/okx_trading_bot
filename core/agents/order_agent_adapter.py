"""
订单智能体适配器 - 将原有OrderAgent适配到新的交易器架构

这个适配器保持原有OrderAgent的接口不变，但内部使用新的交易器执行交易
实现平稳过渡，不影响现有代码
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from decimal import Decimal

from .order_agent import OrderAgent
from core.traders import TraderManager, TradeResult, OrderType, PositionSide
from core.traders.base_trader import TradeSide
from core.events.event_bus import EventType, event_bus
from core.config.env_manager import env_manager

logger = logging.getLogger(__name__)


class OrderAgentAdapter(OrderAgent):
    """
    订单智能体适配器
    
    继承原有OrderAgent，但使用新的交易器架构执行交易
    保持接口兼容，实现平稳过渡
    """

    def __init__(self, config, exchange_name="okx", use_env_config=False, **exchange_kwargs):
        """
        初始化适配器
        
        Args:
            config: 智能体配置
            exchange_name: 交易所名称
            use_env_config: 是否使用环境配置
            **exchange_kwargs: 交易所参数
        """
        # 先调用父类初始化，但传递None作为trader和rest_client
        super().__init__(config, trader=None, rest_client=None, **exchange_kwargs)
        
        # 保存交易所参数
        self.exchange_name = exchange_name
        self.exchange_kwargs = exchange_kwargs
        self.use_env_config = use_env_config
        
        # 初始化交易器管理器
        self._trader_manager: Optional[TraderManager] = None
        self._default_trader_type = 'margin'  # 默认使用杠杆交易器
        
        logger.info("订单智能体适配器初始化完成")

    async def _initialize(self):
        """初始化 - 创建交易器"""
        # 先初始化父类
        await super()._initialize()
        
        # 如果rest_client未初始化，使用交易所参数创建
        if not self.rest_client:
            try:
                from core.api.okx_rest_client import OKXRESTClient
                self.rest_client = OKXRESTClient(
                    api_key=self.exchange_kwargs.get('api_key', ''),
                    api_secret=self.exchange_kwargs.get('api_secret', ''),
                    passphrase=self.exchange_kwargs.get('passphrase', ''),
                    is_test=self.exchange_kwargs.get('is_test', True)
                )
                logger.info("成功创建OKX REST客户端")
            except Exception as e:
                logger.error(f"创建OKX REST客户端失败: {e}")
                return
        
        # 创建交易器管理器
        if self.rest_client:
            self._trader_manager = TraderManager(self.rest_client, use_env_config=self.use_env_config)
            
            # 创建默认的现货交易器
            self._trader_manager.create_trader('spot', 'default_spot', use_env_config=self.use_env_config)
            
            # 创建默认的杠杆交易器
            self._trader_manager.create_trader('margin', 'default_margin', use_env_config=self.use_env_config)
            
            # 设置2倍杠杆（为所有主要交易对）
            await self._trader_manager.set_leverage('BTC-USDT', 2, None, 'default_margin')
            await self._trader_manager.set_leverage('ETH-USDT', 2, None, 'default_margin')
            await self._trader_manager.set_leverage('OKB-USDT', 2, None, 'default_margin')
            
            # 将trader_manager设置为OrderAgent的trader属性
            self.trader = self._trader_manager
            
            # 订阅订单相关事件，实现订单校对
            event_bus.subscribe(EventType.ORDER_NEW, self._handle_order_new, async_callback=True)
            event_bus.subscribe(EventType.ORDER_UPDATE, self._handle_order_update, async_callback=True)
            event_bus.subscribe(EventType.ORDER_FILLED, self._handle_order_filled, async_callback=True)
            event_bus.subscribe(EventType.PENDING_ORDERS_UPDATE, self._handle_pending_orders_update, async_callback=True)
            event_bus.subscribe(EventType.HISTORY_ORDERS_UPDATE, self._handle_history_orders_update, async_callback=True)
            
            logger.info("交易器管理器初始化完成，已创建现货和杠杆交易器，已为BTC-USDT、ETH-USDT、OKB-USDT设置2倍杠杆，已订阅订单校对事件")
    
    def switch_trading_mode(self, mode: str):
        """
        切换交易模式
        
        Args:
            mode: 交易模式 ('cash' 或 'cross')
        """
        if self._trader_manager:
            self._trader_manager.set_default_trading_mode(mode)
            logger.info(f"交易模式已切换为: {mode}")
        else:
            logger.error("交易器管理器未初始化，无法切换交易模式")
    
    def get_trading_mode(self) -> str:
        """
        获取当前交易模式
        
        Returns:
            str: 当前交易模式
        """
        if self._trader_manager:
            return self._trader_manager.get_default_trading_mode()
        else:
            return 'cash'  # 默认返回现货模式

    async def place_order(self, params: Dict) -> Dict:
        """
        下单 - 使用交易器执行
        
        保持原有接口，但内部使用交易器执行交易
        
        Args:
            params: 订单参数
            
        Returns:
            Dict: 下单结果
        """
        if not self._trader_manager:
            # 如果交易器未初始化，回退到父类方法
            logger.warning("交易器未初始化，使用原有方法下单")
            return await super().place_order(params)

        try:
            # 解析参数
            inst_id = params.get("inst_id", "BTC-USDT")
            side = params.get("side", "buy")
            sz = params.get("sz", "0")
            px = params.get("px", "")
            td_mode = params.get("td_mode", self.get_trading_mode())
            
            # 根据交易模式选择交易器
            if td_mode == "cash":
                trader_name = 'default_spot'
            else:
                # 杠杆交易使用margin交易器
                trader_name = 'default_margin'
            
            # 获取交易器
            trader = self._trader_manager.get_trader(trader_name)
            if not trader:
                logger.error(f"未找到交易器: {trader_name}")
                return {"success": False, "error": f"未找到交易器: {trader_name}"}

            # 交易前风险检查
            trade_side = TradeSide.BUY if side == "buy" else TradeSide.SELL
            size_decimal = Decimal(str(sz))
            
            passed, reason = await self._trader_manager.check_risk_before_trade(
                inst_id, trade_side, size_decimal, trader_name, td_mode
            )
            
            if not passed:
                logger.warning(f"风险检查未通过: {reason}")
                return {"success": False, "error": reason}

            # 执行交易
            price_decimal = Decimal(str(px)) if px else None
            
            if side == "buy":
                # 买入时按 USDT 金额下单
                result = await self._trader_manager.buy(
                    inst_id=inst_id,
                    size=size_decimal,
                    price=price_decimal,
                    order_type=OrderType.MARKET if not px else OrderType.LIMIT,
                    trader_name=trader_name,
                    tgtCcy='quote_ccy'
                )
            else:
                # 检查是否为做空操作
                is_short_sell = params.get('is_short_sell', False)
                result = await self._trader_manager.sell(
                    inst_id=inst_id,
                    size=size_decimal,
                    price=price_decimal,
                    order_type=OrderType.MARKET if not px else OrderType.LIMIT,
                    trader_name=trader_name,
                    tgtCcy='base_ccy',
                    is_short_sell=is_short_sell
                )

            # 转换结果为原有格式
            if result.success:
                self._order_count += 1
                
                # 记录订单创建时间（用于超时检查）
                import time
                self._order_creation_times[result.order_id] = time.time()
                
                logger.info(f"通过交易器下单成功: {result.order_id}")
                
                # 构建与原有格式兼容的结果
                return {
                    "success": True,
                    "order_id": result.order_id,
                    "side": side,
                    "inst_id": inst_id,
                    "price": float(px) if px else 0,
                    "size": sz
                }
            else:
                logger.error(f"通过交易器下单失败: {result.error_message}")
                return {"success": False, "error": result.error_message}

        except Exception as e:
            logger.error(f"适配器下单失败: {e}")
            # 出错时回退到父类方法
            return await super().place_order(params)

    async def cancel_order(self, params: Dict) -> Dict:
        """
        撤销订单 - 使用交易器
        
        Args:
            params: 撤单参数
            
        Returns:
            Dict: 撤单结果
        """
        if not self._trader_manager:
            return await super().cancel_order(params)

        try:
            inst_id = params.get("inst_id", "BTC-USDT")
            order_id = params.get("order_id")
            
            if not order_id:
                return {"success": False, "error": "缺少订单ID"}

            # 使用交易器撤销订单
            trader_name = 'default_margin'
            trader = self._trader_manager.get_trader(trader_name)
            
            if trader:
                success = await trader.cancel_order(inst_id, order_id)
                if success:
                    self._cancelled_count += 1
                    self._order_creation_times.pop(order_id, None)
                    return {"success": True, "order_id": order_id}
            
            # 如果交易器撤销失败，回退到父类方法
            return await super().cancel_order(params)

        except Exception as e:
            logger.error(f"适配器撤单失败: {e}")
            return await super().cancel_order(params)

    async def query_order(self, params: Dict) -> Dict:
        """
        查询订单 - 使用交易器
        
        Args:
            params: 查询参数
            
        Returns:
            Dict: 订单信息
        """
        if not self._trader_manager:
            return await super().query_order(params)

        try:
            inst_id = params.get("inst_id", "BTC-USDT")
            order_id = params.get("order_id")
            
            if not order_id:
                return {"success": False, "error": "缺少订单ID"}

            # 使用交易器查询订单
            trader_name = 'default_margin'
            trader = self._trader_manager.get_trader(trader_name)
            
            if trader:
                order_info = await trader.get_order(inst_id, order_id)
                if order_info:
                    return {"success": True, "order": order_info}
            
            # 如果交易器查询失败，回退到父类方法
            return await super().query_order(params)

        except Exception as e:
            logger.error(f"适配器查询订单失败: {e}")
            return await super().query_order(params)

    async def get_account_balance(self) -> Optional[Dict]:
        """
        获取账户余额 - 使用交易器
        
        Returns:
            Optional[Dict]: 账户余额
        """
        if not self._trader_manager:
            # 回退到REST客户端
            try:
                return await self.rest_client.get_account_balance()
            except Exception as e:
                logger.error(f"获取账户余额失败: {e}")
                return None

        try:
            # 使用交易器获取账户信息
            account_info = await self._trader_manager.get_account_info('default_margin')
            
            if account_info:
                # 转换为原有格式
                return {
                    'totalEq': str(account_info.total_equity),
                    'availEq': str(account_info.available_balance),
                    'details': [
                        {
                            'ccy': ccy,
                            'availBal': str(info['available']),
                            'eq': str(info['equity'])
                        }
                        for ccy, info in account_info.currencies.items()
                    ]
                }
            
            return None

        except Exception as e:
            logger.error(f"适配器获取账户余额失败: {e}")
            # 回退到REST客户端
            try:
                return await self.rest_client.get_account_balance()
            except Exception as e2:
                logger.error(f"获取账户余额失败: {e2}")
                return None

    async def get_positions(self, inst_id: Optional[str] = None) -> Optional[list]:
        """
        获取持仓 - 使用交易器
        
        Args:
            inst_id: 产品ID（可选）
            
        Returns:
            Optional[list]: 持仓列表
        """
        if not self._trader_manager:
            # 回退到REST客户端
            try:
                if inst_id:
                    return await self.rest_client.get_positions(instId=inst_id)
                else:
                    return await self.rest_client.get_positions()
            except Exception as e:
                logger.error(f"获取持仓失败: {e}")
                return None

        try:
            # 使用交易器获取持仓
            if inst_id:
                position = await self._trader_manager.get_position(inst_id, None, 'default_margin')
                return [position] if position else []
            else:
                positions = await self._trader_manager.get_all_positions('default_margin')
                return positions

        except Exception as e:
            logger.error(f"适配器获取持仓失败: {e}")
            # 回退到REST客户端
            try:
                if inst_id:
                    return await self.rest_client.get_positions(instId=inst_id)
                else:
                    return await self.rest_client.get_positions()
            except Exception as e2:
                logger.error(f"获取持仓失败: {e2}")
                return None

    def get_trader_manager(self) -> Optional[TraderManager]:
        """
        获取交易器管理器
        
        Returns:
            Optional[TraderManager]: 交易器管理器
        """
        return self._trader_manager

    def create_trader(self, trader_type: str, name: str = None, config: Dict = None):
        """
        创建交易器
        
        Args:
            trader_type: 交易器类型 ('spot', 'margin', 'contract', 'options')
            name: 交易器名称
            config: 配置
            
        Returns:
            交易器实例
        """
        if self._trader_manager:
            return self._trader_manager.create_trader(trader_type, name, config)
        else:
            logger.error("交易器管理器未初始化")
            return None

    async def _handle_order_new(self, event):
        """
        处理新订单事件
        """
        try:
            order = event.data.get('order')
            if order:
                order_id = order.get('ordId')
                if order_id:
                    logger.info(f"收到新订单事件: {order_id}")
                    # 可以在这里更新本地订单记录
        except Exception as e:
            logger.error(f"处理新订单事件失败: {e}")

    async def _handle_order_update(self, event):
        """
        处理订单更新事件
        """
        try:
            order = event.data.get('order')
            if order:
                order_id = order.get('ordId')
                if order_id:
                    logger.info(f"收到订单更新事件: {order_id}, 状态: {order.get('state')}")
                    # 可以在这里更新本地订单状态
        except Exception as e:
            logger.error(f"处理订单更新事件失败: {e}")

    async def _handle_order_filled(self, event):
        """
        处理订单成交事件
        """
        try:
            order = event.data.get('order')
            if order:
                order_id = order.get('ordId')
                if order_id:
                    logger.info(f"收到订单成交事件: {order_id}, 成交数量: {order.get('accFillSz')}")
                    # 可以在这里更新本地订单状态
                    # 从_order_creation_times中移除已成交的订单
                    if order_id in self._order_creation_times:
                        del self._order_creation_times[order_id]
        except Exception as e:
            logger.error(f"处理订单成交事件失败: {e}")

    async def _handle_pending_orders_update(self, event):
        """
        处理未成交订单更新事件
        """
        try:
            pending_orders = event.data.get('pending_orders')
            if pending_orders:
                logger.info(f"收到未成交订单更新，共 {len(pending_orders)} 个未成交订单")
                # 可以在这里更新本地未成交订单记录
        except Exception as e:
            logger.error(f"处理未成交订单更新事件失败: {e}")

    async def _handle_history_orders_update(self, event):
        """
        处理历史订单更新事件
        """
        try:
            history_orders = event.data.get('history_orders')
            if history_orders:
                logger.info(f"收到历史订单更新，共 {len(history_orders)} 个历史订单")
                # 可以在这里更新本地历史订单记录
        except Exception as e:
            logger.error(f"处理历史订单更新事件失败: {e}")
