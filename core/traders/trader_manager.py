"""
交易器管理器 - 管理所有交易器，提供统一接口供智能体调用
"""

from typing import Dict, Optional, Type, Any, Tuple, List
from decimal import Decimal
from datetime import datetime
import logging

from .base_trader import BaseTrader, TradeResult, PositionInfo, AccountInfo, RiskInfo, TradeSide, OrderType, PositionSide
from .spot_trader import SpotTrader
from .margin_trader import MarginTrader
from .contract_trader import ContractTrader
from .options_trader import OptionsTrader
from core.config.env_manager import env_manager

logger = logging.getLogger(__name__)


class TraderManager:
    """
    交易器管理器
    
    管理所有交易器的生命周期，提供统一的交易接口
    所有智能体通过此类调用交易功能
    """

    # 交易器类型映射
    TRADER_TYPES = {
        'spot': SpotTrader,
        'margin': MarginTrader,
        'contract': ContractTrader,
        'options': OptionsTrader,
    }

    def __init__(self, rest_client, config: Dict[str, Any] = None, use_env_config: bool = False):
        """
        初始化交易器管理器
        
        Args:
            rest_client: OKX REST API 客户端
            config: 配置信息
            use_env_config: 是否使用环境配置
        """
        self.rest_client = rest_client
        
        # 从环境配置获取参数
        if use_env_config:
            trading_config = env_manager.get_trading_config()
            self.config = {
                **(config or {}),
                'trading': trading_config
            }
            self._default_trading_mode = trading_config.get('default_trading_mode', 'cash')
            logger.info("从环境配置获取交易参数")
        else:
            self.config = config or {}
            self._default_trading_mode = 'cash'  # 默认交易模式: cash (现货), cross (杠杆)
        
        self._traders: Dict[str, BaseTrader] = {}
        self._default_trader_type: str = 'spot'
        
        # 交易器池配置
        self._trader_pool_size = 5  # 每个类型的交易器池大小
        self._trader_pool: Dict[str, List[BaseTrader]] = {}  # 交易器池
        
        # 交易器监控
        self._trader_status: Dict[str, Dict] = {}  # 交易器状态
        self._trader_metrics: Dict[str, Dict] = {}  # 交易器指标
        
        # 负载均衡
        self._trader_load: Dict[str, int] = {}  # 交易器负载

        logger.info("交易器管理器初始化完成")

    def create_trader(self, trader_type: str, name: str = None, config: Dict = None, use_env_config: bool = False) -> BaseTrader:
        """
        创建交易器
        
        Args:
            trader_type: 交易器类型 ('spot', 'margin', 'contract', 'options')
            name: 交易器名称（可选）
            config: 交易器配置（可选）
            use_env_config: 是否使用环境配置
            
        Returns:
            BaseTrader: 交易器实例
            
        Raises:
            ValueError: 如果交易器类型不存在
        """
        if trader_type not in self.TRADER_TYPES:
            raise ValueError(f"未知的交易器类型: {trader_type}，可用类型: {list(self.TRADER_TYPES.keys())}")

        trader_class = self.TRADER_TYPES[trader_type]
        trader_config = {**(self.config.get(trader_type, {})), **(config or {})}
        
        trader = trader_class(self.rest_client, trader_config, use_env_config)
        
        # 使用名称或默认名称
        trader_name = name or f"{trader_type}_trader"
        self._traders[trader_name] = trader
        
        logger.info(f"创建交易器: {trader_name} (类型: {trader_type})")
        return trader

    def get_trader(self, name: str = None, trading_mode: str = None) -> Optional[BaseTrader]:
        """
        获取交易器
        
        Args:
            name: 交易器名称，None则返回默认交易器
            trading_mode: 交易模式，None则使用默认交易模式
            
        Returns:
            Optional[BaseTrader]: 交易器实例
        """
        if name:
            return self._traders.get(name)
        
        # 根据交易模式返回对应交易器
        mode = trading_mode or self._default_trading_mode
        if mode == 'cash':
            # 现货交易
            for name, trader in self._traders.items():
                if isinstance(trader, SpotTrader):
                    return trader
        else:
            # 杠杆交易
            for name, trader in self._traders.items():
                if isinstance(trader, MarginTrader):
                    return trader
        
        # 如果没有找到对应交易器，返回第一个可用的
        if self._traders:
            return next(iter(self._traders.values()))
        
        return None
    
    def set_default_trading_mode(self, mode: str):
        """
        设置默认交易模式
        
        Args:
            mode: 交易模式 ('cash' 或 'cross')
        """
        if mode in ['cash', 'cross']:
            self._default_trading_mode = mode
            logger.info(f"默认交易模式已设置为: {mode}")
        else:
            logger.error(f"无效的交易模式: {mode}，必须是 'cash' 或 'cross'")
    
    def get_default_trading_mode(self) -> str:
        """
        获取默认交易模式
        
        Returns:
            str: 默认交易模式
        """
        return self._default_trading_mode

    def get_or_create_trader(self, trader_type: str, name: str = None, use_env_config: bool = False) -> BaseTrader:
        """
        获取或创建交易器
        
        Args:
            trader_type: 交易器类型
            name: 交易器名称
            use_env_config: 是否使用环境配置
            
        Returns:
            BaseTrader: 交易器实例
        """
        trader_name = name or f"{trader_type}_trader"
        
        if trader_name in self._traders:
            return self._traders[trader_name]
        
        return self.create_trader(trader_type, trader_name, use_env_config=use_env_config)

    def remove_trader(self, name: str) -> bool:
        """
        移除交易器
        
        Args:
            name: 交易器名称
            
        Returns:
            bool: 是否成功
        """
        if name in self._traders:
            del self._traders[name]
            # 从状态和指标中移除
            if name in self._trader_status:
                del self._trader_status[name]
            if name in self._trader_metrics:
                del self._trader_metrics[name]
            if name in self._trader_load:
                del self._trader_load[name]
            logger.info(f"移除交易器: {name}")
            return True
        return False

    def list_traders(self) -> Dict[str, str]:
        """
        列出所有交易器
        
        Returns:
            Dict[str, str]: {名称: 类型}
        """
        return {name: type(trader).__name__ for name, trader in self._traders.items()}
    
    def _init_trader_pool(self, trader_type: str, pool_size: int = None):
        """
        初始化交易器池
        
        Args:
            trader_type: 交易器类型
            pool_size: 池大小
        """
        if trader_type not in self.TRADER_TYPES:
            logger.error(f"未知的交易器类型: {trader_type}")
            return
        
        size = pool_size or self._trader_pool_size
        self._trader_pool[trader_type] = []
        
        for i in range(size):
            trader_name = f"{trader_type}_pool_{i}"
            try:
                trader = self.create_trader(trader_type, trader_name)
                self._trader_pool[trader_type].append(trader)
                # 初始化状态和指标
                self._trader_status[trader_name] = {
                    'status': 'active',
                    'last_used': None,
                    'error_count': 0
                }
                self._trader_metrics[trader_name] = {
                    'total_trades': 0,
                    'successful_trades': 0,
                    'failed_trades': 0,
                    'avg_response_time': 0,
                    'total_response_time': 0
                }
                self._trader_load[trader_name] = 0
            except Exception as e:
                logger.error(f"创建交易器池失败: {e}")
        
        logger.info(f"交易器池初始化完成: {trader_type}, 大小: {len(self._trader_pool[trader_type])}")
    
    def get_trader_from_pool(self, trader_type: str) -> Optional[BaseTrader]:
        """
        从交易器池获取交易器
        
        Args:
            trader_type: 交易器类型
            
        Returns:
            Optional[BaseTrader]: 交易器实例
        """
        # 如果交易器池不存在，初始化
        if trader_type not in self._trader_pool or not self._trader_pool[trader_type]:
            self._init_trader_pool(trader_type)
        
        if trader_type not in self._trader_pool or not self._trader_pool[trader_type]:
            logger.error(f"交易器池为空: {trader_type}")
            return None
        
        # 负载均衡：选择负载最小的交易器
        pool = self._trader_pool[trader_type]
        min_load = float('inf')
        selected_trader = None
        
        for trader in pool:
            trader_name = f"{trader_type}_pool_{pool.index(trader)}"
            load = self._trader_load.get(trader_name, 0)
            if load < min_load:
                min_load = load
                selected_trader = trader
        
        if selected_trader:
            trader_name = f"{trader_type}_pool_{pool.index(selected_trader)}"
            # 更新状态
            self._trader_status[trader_name]['last_used'] = datetime.now().isoformat()
            # 增加负载
            self._trader_load[trader_name] = self._trader_load.get(trader_name, 0) + 1
            logger.debug(f"从交易器池获取交易器: {trader_name}")
        
        return selected_trader
    
    def return_trader_to_pool(self, trader: BaseTrader, success: bool = True, response_time: float = 0):
        """
        将交易器返回交易器池
        
        Args:
            trader: 交易器实例
            success: 是否成功
            response_time: 响应时间
        """
        for trader_type, pool in self._trader_pool.items():
            if trader in pool:
                trader_name = f"{trader_type}_pool_{pool.index(trader)}"
                # 减少负载
                if trader_name in self._trader_load:
                    self._trader_load[trader_name] = max(0, self._trader_load[trader_name] - 1)
                # 更新指标
                if trader_name in self._trader_metrics:
                    metrics = self._trader_metrics[trader_name]
                    metrics['total_trades'] += 1
                    if success:
                        metrics['successful_trades'] += 1
                    else:
                        metrics['failed_trades'] += 1
                    metrics['total_response_time'] += response_time
                    if metrics['total_trades'] > 0:
                        metrics['avg_response_time'] = metrics['total_response_time'] / metrics['total_trades']
                logger.debug(f"交易器返回交易器池: {trader_name}")
                break
    
    def monitor_trader_status(self):
        """
        监控交易器状态
        """
        for trader_name, status in self._trader_status.items():
            # 检查交易器是否长时间未使用
            if status['last_used']:
                last_used = datetime.fromisoformat(status['last_used'])
                if (datetime.now() - last_used).total_seconds() > 3600:  # 1小时
                    status['status'] = 'idle'
            # 检查错误计数
            if status['error_count'] > 10:
                status['status'] = 'error'
                logger.warning(f"交易器 {trader_name} 错误过多，状态设置为 error")
    
    def get_trader_status(self, trader_name: str = None) -> Dict:
        """
        获取交易器状态
        
        Args:
            trader_name: 交易器名称，None则返回所有
            
        Returns:
            Dict: 交易器状态
        """
        if trader_name:
            return self._trader_status.get(trader_name, {})
        return self._trader_status
    
    def get_trader_metrics(self, trader_name: str = None) -> Dict:
        """
        获取交易器指标
        
        Args:
            trader_name: 交易器名称，None则返回所有
            
        Returns:
            Dict: 交易器指标
        """
        if trader_name:
            return self._trader_metrics.get(trader_name, {})
        return self._trader_metrics
    
    def balance_load(self):
        """
        负载均衡
        """
        # 简单的负载均衡算法
        # 可以根据实际情况实现更复杂的算法
        pass

    # ==================== 统一交易接口 ====================

    async def buy(self, inst_id: str, size: Decimal, price: Optional[Decimal] = None,
                  order_type: OrderType = OrderType.MARKET, 
                  trader_name: str = None, trading_mode: str = None, use_pool: bool = True, **kwargs) -> TradeResult:
        """
        买入（使用指定交易器）
        
        Args:
            inst_id: 产品ID
            size: 数量
            price: 价格
            order_type: 订单类型
            trader_name: 交易器名称，None使用默认交易器
            trading_mode: 交易模式，None使用默认交易模式
            use_pool: 是否使用交易器池
            **kwargs: 额外参数
            
        Returns:
            TradeResult: 交易结果
        """
        import time
        start_time = time.time()
        
        if use_pool:
            # 从交易器池获取交易器
            trader_type = 'spot' if trading_mode == 'cash' else 'margin'
            trader = self.get_trader_from_pool(trader_type)
        else:
            # 使用指定或默认交易器
            trader = self.get_trader(trader_name, trading_mode)
        
        if not trader:
            return TradeResult(success=False, error_message="无可用交易器")
        
        try:
            result = await trader.buy(inst_id, size, price, order_type, **kwargs)
            response_time = time.time() - start_time
            # 将交易器返回交易器池
            if use_pool:
                self.return_trader_to_pool(trader, result.success, response_time)
            return result
        except Exception as e:
            response_time = time.time() - start_time
            # 将交易器返回交易器池
            if use_pool:
                self.return_trader_to_pool(trader, False, response_time)
            logger.error(f"买入失败: {e}")
            return TradeResult(success=False, error_message=str(e))

    async def sell(self, inst_id: str, size: Decimal, price: Optional[Decimal] = None,
                   order_type: OrderType = OrderType.MARKET,
                   trader_name: str = None, trading_mode: str = None, use_pool: bool = True, **kwargs) -> TradeResult:
        """
        卖出（使用指定交易器）
        
        Args:
            inst_id: 产品ID
            size: 数量
            price: 价格
            order_type: 订单类型
            trader_name: 交易器名称，None使用默认交易器
            trading_mode: 交易模式，None使用默认交易模式
            use_pool: 是否使用交易器池
            **kwargs: 额外参数
            
        Returns:
            TradeResult: 交易结果
        """
        import time
        start_time = time.time()
        
        if use_pool:
            # 从交易器池获取交易器
            trader_type = 'spot' if trading_mode == 'cash' else 'margin'
            trader = self.get_trader_from_pool(trader_type)
        else:
            # 使用指定或默认交易器
            trader = self.get_trader(trader_name, trading_mode)
        
        if not trader:
            return TradeResult(success=False, error_message="无可用交易器")
        
        try:
            result = await trader.sell(inst_id, size, price, order_type, **kwargs)
            response_time = time.time() - start_time
            # 将交易器返回交易器池
            if use_pool:
                self.return_trader_to_pool(trader, result.success, response_time)
            return result
        except Exception as e:
            response_time = time.time() - start_time
            # 将交易器返回交易器池
            if use_pool:
                self.return_trader_to_pool(trader, False, response_time)
            logger.error(f"卖出失败: {e}")
            return TradeResult(success=False, error_message=str(e))

    async def close_position(self, inst_id: str, pos_side: Optional[PositionSide] = None,
                            size: Optional[Decimal] = None,
                            trader_name: str = None, trading_mode: str = None) -> TradeResult:
        """
        平仓
        
        Args:
            inst_id: 产品ID
            pos_side: 持仓方向，None则平所有方向
            size: 平仓数量，None则平全部
            trader_name: 交易器名称，None使用默认交易器
            trading_mode: 交易模式，None使用默认交易模式
            
        Returns:
            TradeResult: 交易结果
        """
        trader = self.get_trader(trader_name, trading_mode)
        if not trader:
            return TradeResult(success=False, error_message="无可用交易器")
        
        return await trader.close_position(inst_id, pos_side, size)

    async def set_take_profit(self, inst_id: str, size: Decimal, price: Decimal,
                              pos_side: Optional[PositionSide] = None,
                              trader_name: str = None, trading_mode: str = None, **kwargs) -> TradeResult:
        """
        设置止盈单
        
        Args:
            inst_id: 产品ID
            size: 数量
            price: 止盈价格
            pos_side: 持仓方向
            trader_name: 交易器名称
            trading_mode: 交易模式，None使用默认交易模式
            **kwargs: 额外参数
            
        Returns:
            TradeResult: 交易结果
        """
        trader = self.get_trader(trader_name, trading_mode)
        if not trader:
            return TradeResult(success=False, error_message="无可用交易器")
        
        return await trader.set_take_profit(inst_id, size, price, pos_side, **kwargs)

    async def set_stop_loss(self, inst_id: str, size: Decimal, price: Decimal,
                            pos_side: Optional[PositionSide] = None,
                            trader_name: str = None, trading_mode: str = None, **kwargs) -> TradeResult:
        """
        设置止损单
        
        Args:
            inst_id: 产品ID
            size: 数量
            price: 止损价格
            pos_side: 持仓方向
            trader_name: 交易器名称
            trading_mode: 交易模式，None使用默认交易模式
            **kwargs: 额外参数
            
        Returns:
            TradeResult: 交易结果
        """
        trader = self.get_trader(trader_name, trading_mode)
        if not trader:
            return TradeResult(success=False, error_message="无可用交易器")
        
        return await trader.set_stop_loss(inst_id, size, price, pos_side, **kwargs)

    # ==================== 订单管理接口 ====================

    async def cancel_order(self, inst_id: str, order_id: str, trader_name: str = None, trading_mode: str = None) -> bool:
        """
        撤销订单
        
        Args:
            inst_id: 产品ID
            order_id: 订单ID
            trader_name: 交易器名称
            trading_mode: 交易模式，None使用默认交易模式
            
        Returns:
            bool: 是否成功
        """
        trader = self.get_trader(trader_name, trading_mode)
        if not trader:
            return False
        
        return await trader.cancel_order(inst_id, order_id)

    async def cancel_all_orders(self, inst_id: str, trader_name: str = None, trading_mode: str = None) -> bool:
        """
        取消所有订单
        
        Args:
            inst_id: 产品ID
            trader_name: 交易器名称
            trading_mode: 交易模式，None使用默认交易模式
            
        Returns:
            bool: 是否成功
        """
        trader = self.get_trader(trader_name, trading_mode)
        if not trader:
            return False
        
        return await trader.cancel_all_orders(inst_id)

    async def get_order(self, inst_id: str, order_id: str, trader_name: str = None, trading_mode: str = None) -> Optional[Dict]:
        """
        获取订单信息
        
        Args:
            inst_id: 产品ID
            order_id: 订单ID
            trader_name: 交易器名称
            trading_mode: 交易模式，None使用默认交易模式
            
        Returns:
            Optional[Dict]: 订单信息
        """
        trader = self.get_trader(trader_name, trading_mode)
        if not trader:
            return None
        
        return await trader.get_order(inst_id, order_id)

    async def get_open_orders(self, inst_id: str = "", trader_name: str = None, trading_mode: str = None) -> List[Dict]:
        """
        获取未成交订单
        
        Args:
            inst_id: 产品ID
            trader_name: 交易器名称
            trading_mode: 交易模式，None使用默认交易模式
            
        Returns:
            List[Dict]: 未成交订单列表
        """
        trader = self.get_trader(trader_name, trading_mode)
        if not trader:
            return []
        
        return await trader.get_open_orders(inst_id)

    async def get_order_history(self, inst_type: str, inst_id: str = "", 
                               limit: int = 100, trader_name: str = None, trading_mode: str = None) -> List[Dict]:
        """
        获取历史订单
        
        Args:
            inst_type: 产品类型
            inst_id: 产品ID
            limit: 数量限制
            trader_name: 交易器名称
            trading_mode: 交易模式，None使用默认交易模式
            
        Returns:
            List[Dict]: 历史订单列表
        """
        trader = self.get_trader(trader_name, trading_mode)
        if not trader:
            return []
        
        return await trader.get_order_history(inst_type, inst_id, limit)

    # ==================== 账户和持仓接口 ====================

    async def get_account_info(self, trader_name: str = None, trading_mode: str = None) -> AccountInfo:
        """
        获取账户信息
        
        Args:
            trader_name: 交易器名称
            trading_mode: 交易模式，None使用默认交易模式
            
        Returns:
            AccountInfo: 账户信息
        """
        trader = self.get_trader(trader_name, trading_mode)
        if not trader:
            return AccountInfo(
                total_equity=Decimal('0'),
                available_balance=Decimal('0'),
                margin_balance=Decimal('0'),
                unrealized_pnl=Decimal('0'),
                realized_pnl=Decimal('0')
            )
        
        return await trader.get_account_info()

    async def get_position(self, inst_id: str, pos_side: Optional[PositionSide] = None,
                          trader_name: str = None, trading_mode: str = None) -> Optional[PositionInfo]:
        """
        获取持仓信息
        
        Args:
            inst_id: 产品ID
            pos_side: 持仓方向
            trader_name: 交易器名称
            trading_mode: 交易模式，None使用默认交易模式
            
        Returns:
            Optional[PositionInfo]: 持仓信息
        """
        trader = self.get_trader(trader_name, trading_mode)
        if not trader:
            return None
        
        return await trader.get_position(inst_id, pos_side)

    async def get_all_positions(self, trader_name: str = None, trading_mode: str = None) -> List[PositionInfo]:
        """
        获取所有持仓
        
        Args:
            trader_name: 交易器名称
            trading_mode: 交易模式，None使用默认交易模式
            
        Returns:
            List[PositionInfo]: 持仓列表
        """
        trader = self.get_trader(trader_name, trading_mode)
        if not trader:
            return []
        
        return await trader.get_all_positions()

    # ==================== 风险管理接口 ====================

    async def get_risk_info(self, trader_name: str = None, trading_mode: str = None) -> RiskInfo:
        """
        获取风险信息
        
        Args:
            trader_name: 交易器名称
            trading_mode: 交易模式，None使用默认交易模式
            
        Returns:
            RiskInfo: 风险信息
        """
        trader = self.get_trader(trader_name, trading_mode)
        if not trader:
            return RiskInfo(
                margin_ratio=Decimal('0'),
                maintenance_margin_ratio=Decimal('0'),
                risk_level="danger"
            )
        
        return await trader.get_risk_info()

    async def check_risk_before_trade(self, inst_id: str, side: TradeSide, size: Decimal,
                                   trader_name: str = None, trading_mode: str = None) -> Tuple[bool, str]:
        """
        交易前风险检查
        
        Args:
            inst_id: 产品ID
            side: 交易方向
            size: 交易数量
            trader_name: 交易器名称
            trading_mode: 交易模式，None使用默认交易模式
            
        Returns:
            tuple[bool, str]: (是否通过, 原因)
        """
        trader = self.get_trader(trader_name, trading_mode)
        if not trader:
            return False, "无可用交易器"
        
        return await trader.check_risk_before_trade(inst_id, side, size)

    # ==================== 高级交易功能 ====================

    async def set_trailing_stop(self, inst_id: str, size: Decimal, distance: Decimal, 
                             pos_side: Optional[PositionSide] = None, 
                             trader_name: str = None, trading_mode: str = None, **kwargs) -> TradeResult:
        """
        设置移动止盈止损
        
        Args:
            inst_id: 产品ID
            size: 数量
            distance: 距离（百分比）
            pos_side: 持仓方向
            trader_name: 交易器名称
            trading_mode: 交易模式，None使用默认交易模式
            **kwargs: 额外参数
            
        Returns:
            TradeResult: 交易结果
        """
        trader = self.get_trader(trader_name, trading_mode)
        if not trader:
            return TradeResult(success=False, error_message="无可用交易器")
        
        return await trader.set_trailing_stop(inst_id, size, distance, pos_side, **kwargs)

    async def set_trigger_order(self, inst_id: str, side: TradeSide, size: Decimal, 
                               trigger_price: Decimal, order_price: Optional[Decimal] = None,
                               trader_name: str = None, trading_mode: str = None, **kwargs) -> TradeResult:
        """
        设置计划委托
        
        Args:
            inst_id: 产品ID
            side: 交易方向
            size: 数量
            trigger_price: 触发价格
            order_price: 订单价格
            trader_name: 交易器名称
            trading_mode: 交易模式，None使用默认交易模式
            **kwargs: 额外参数
            
        Returns:
            TradeResult: 交易结果
        """
        trader = self.get_trader(trader_name, trading_mode)
        if not trader:
            return TradeResult(success=False, error_message="无可用交易器")
        
        return await trader.set_trigger_order(inst_id, side, size, trigger_price, order_price, **kwargs)

    # ==================== 杠杆管理 ====================

    async def set_leverage(self, inst_id: str, leverage: int, 
                         pos_side: Optional[PositionSide] = None, 
                         trader_name: str = None, trading_mode: str = None) -> bool:
        """
        设置杠杆倍数
        
        Args:
            inst_id: 产品ID
            leverage: 杠杆倍数
            pos_side: 持仓方向
            trader_name: 交易器名称
            trading_mode: 交易模式，None使用默认交易模式
            
        Returns:
            bool: 是否成功
        """
        trader = self.get_trader(trader_name, trading_mode)
        if not trader:
            return False
        
        return await trader.set_leverage(inst_id, leverage, pos_side)

    async def get_leverage(self, inst_id: str, pos_side: Optional[PositionSide] = None,
                         trader_name: str = None) -> Optional[int]:
        """
        获取杠杆倍数
        
        Args:
            inst_id: 产品ID
            pos_side: 持仓方向
            trader_name: 交易器名称
            
        Returns:
            Optional[int]: 杠杆倍数
        """
        trader = self.get_trader(trader_name)
        if not trader:
            return None
        
        return await trader.get_leverage(inst_id, pos_side)

    # ==================== 手续费管理 ====================

    async def calculate_trading_fee(self, inst_id: str, side: TradeSide, 
                                 size: Decimal, price: Decimal, is_maker: bool = False,
                                 trader_name: str = None) -> Decimal:
        """
        计算交易手续费
        
        Args:
            inst_id: 产品ID
            side: 交易方向
            size: 数量
            price: 价格
            is_maker: 是否为maker
            trader_name: 交易器名称
            
        Returns:
            Decimal: 手续费
        """
        trader = self.get_trader(trader_name)
        if not trader:
            return Decimal('0')
        
        return await trader.calculate_trading_fee(inst_id, side, size, price, is_maker)

    # ==================== 工具方法 ====================

    def get_trader_by_type(self, trader_type: str) -> Optional[BaseTrader]:
        """
        根据类型获取交易器
        
        Args:
            trader_type: 交易器类型
            
        Returns:
            Optional[BaseTrader]: 交易器实例
        """
        for trader in self._traders.values():
            if type(trader).__name__.lower().startswith(trader_type):
                return trader
        return None

    # ==================== 便捷方法 ====================

    async def get_all_accounts_summary(self) -> Dict[str, AccountInfo]:
        """
        获取所有交易器的账户摘要
        
        Returns:
            Dict[str, AccountInfo]: {交易器名称: 账户信息}
        """
        summary = {}
        for name, trader in self._traders.items():
            try:
                account_info = await trader.get_account_info()
                if account_info:
                    summary[name] = account_info
            except Exception as e:
                logger.error(f"获取 {name} 账户信息失败: {e}")
        
        return summary

    async def get_all_risks_summary(self) -> Dict[str, RiskInfo]:
        """
        获取所有交易器的风险摘要
        
        Returns:
            Dict[str, RiskInfo]: {交易器名称: 风险信息}
        """
        summary = {}
        for name, trader in self._traders.items():
            try:
                risk_info = await trader.get_risk_info()
                if risk_info:
                    summary[name] = risk_info
            except Exception as e:
                logger.error(f"获取 {name} 风险信息失败: {e}")
        
        return summary

    def get_trader_for_inst_id(self, inst_id: str) -> Optional[BaseTrader]:
        """
        根据产品ID获取合适的交易器
        
        Args:
            inst_id: 产品ID
            
        Returns:
            Optional[BaseTrader]: 交易器实例
        """
        # 根据产品ID后缀判断类型
        if '-SWAP' in inst_id or '-C' in inst_id or '-P' in inst_id:
            # 永续合约或期权
            for trader in self._traders.values():
                if isinstance(trader, (ContractTrader, OptionsTrader)):
                    return trader
        elif inst_id.count('-') == 1:
            # 币币交易对
            for trader in self._traders.values():
                if isinstance(trader, SpotTrader):
                    return trader
        
        # 默认返回第一个
        return self.get_trader()


# 全局交易器管理器实例（可选）
_trader_manager: Optional[TraderManager] = None


def get_trader_manager(rest_client=None, config=None) -> TraderManager:
    """
    获取全局交易器管理器实例
    
    Args:
        rest_client: OKX REST API 客户端
        config: 配置信息
        
    Returns:
        TraderManager: 交易器管理器
    """
    global _trader_manager
    
    if _trader_manager is None and rest_client is not None:
        _trader_manager = TraderManager(rest_client, config)
    
    return _trader_manager


def reset_trader_manager():
    """重置全局交易器管理器"""
    global _trader_manager
    _trader_manager = None
