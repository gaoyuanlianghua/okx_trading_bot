"""
交易器基类 - 定义所有交易器的通用接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TradeMode(Enum):
    """交易模式"""
    SPOT = "cash"           # 现货
    MARGIN_CROSS = "cross"  # 全仓杠杆
    MARGIN_ISO = "isolated" # 逐仓杠杆
    CONTRACT_CROSS = "cross"    # 合约全仓
    CONTRACT_ISO = "isolated"   # 合约逐仓
    OPTIONS = "options"     # 期权


class TradeSide(Enum):
    """交易方向"""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"
    POST_ONLY = "post_only"
    FOK = "fok"
    IOC = "ioc"


class PositionSide(Enum):
    """持仓方向（合约/期权）"""
    LONG = "long"
    SHORT = "short"
    NET = "net"  # 净持仓


@dataclass
class TradeResult:
    """交易结果"""
    success: bool
    order_id: Optional[str] = None
    filled_price: Optional[Decimal] = None
    filled_size: Optional[Decimal] = None
    fee: Optional[Decimal] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict] = None

    def __bool__(self):
        return self.success


@dataclass
class PositionInfo:
    """持仓信息"""
    inst_id: str
    pos_side: PositionSide
    size: Decimal
    avg_price: Decimal
    mark_price: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    realized_pnl: Optional[Decimal] = None
    margin_mode: Optional[str] = None
    leverage: Optional[Decimal] = None
    liquidation_price: Optional[Decimal] = None


@dataclass
class AccountInfo:
    """账户信息"""
    total_equity: Decimal
    available_balance: Decimal
    margin_balance: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    margin_ratio: Optional[Decimal] = None
    maintenance_margin: Optional[Decimal] = None
    currencies: Dict[str, Dict[str, Decimal]] = None  # 各币种详情

    def __post_init__(self):
        if self.currencies is None:
            self.currencies = {}


@dataclass
class RiskInfo:
    """风险信息"""
    margin_ratio: Decimal
    maintenance_margin_ratio: Decimal
    liquidation_distance: Optional[Decimal] = None  # 距离爆仓的价格距离
    risk_level: str = "safe"  # safe, warning, danger


class BaseTrader(ABC):
    """
    交易器基类
    
    所有交易器（现货、杠杆、合约、期权）都继承此类
    提供统一的交易接口
    """

    def __init__(self, rest_client, config: Dict[str, Any] = None, use_env_config: bool = False):
        """
        初始化交易器
        
        Args:
            rest_client: OKX REST API 客户端
            config: 交易器配置
            use_env_config: 是否使用环境配置
        """
        self.rest_client = rest_client
        self.config = config or {}
        self.use_env_config = use_env_config
        self.trade_mode: TradeMode = None  # 子类必须设置
        self.name: str = "BaseTrader"
        
        logger.info(f"{self.name} 初始化完成")

    # ==================== 交易接口 ====================

    @abstractmethod
    async def buy(self, inst_id: str, size: Decimal, price: Optional[Decimal] = None,
                  order_type: OrderType = OrderType.MARKET, **kwargs) -> TradeResult:
        """
        买入/做多
        
        Args:
            inst_id: 产品ID
            size: 数量
            price: 价格（限价单必填）
            order_type: 订单类型
            **kwargs: 额外参数
            
        Returns:
            TradeResult: 交易结果
        """
        pass

    @abstractmethod
    async def sell(self, inst_id: str, size: Decimal, price: Optional[Decimal] = None,
                   order_type: OrderType = OrderType.MARKET, **kwargs) -> TradeResult:
        """
        卖出/做空
        
        Args:
            inst_id: 产品ID
            size: 数量
            price: 价格（限价单必填）
            order_type: 订单类型
            **kwargs: 额外参数
            
        Returns:
            TradeResult: 交易结果
        """
        pass

    @abstractmethod
    async def set_take_profit(self, inst_id: str, size: Decimal, price: Decimal,
                              pos_side: Optional[PositionSide] = None, **kwargs) -> TradeResult:
        """
        设置止盈单
        
        Args:
            inst_id: 产品ID
            size: 数量
            price: 止盈价格
            pos_side: 持仓方向（合约/期权需要）
            **kwargs: 额外参数
            
        Returns:
            TradeResult: 交易结果
        """
        pass

    @abstractmethod
    async def set_stop_loss(self, inst_id: str, size: Decimal, price: Decimal,
                            pos_side: Optional[PositionSide] = None, **kwargs) -> TradeResult:
        """
        设置止损单
        
        Args:
            inst_id: 产品ID
            size: 数量
            price: 止损价格
            pos_side: 持仓方向（合约/期权需要）
            **kwargs: 额外参数
            
        Returns:
            TradeResult: 交易结果
        """
        pass

    async def close_position(self, inst_id: str, pos_side: Optional[PositionSide] = None,
                            size: Optional[Decimal] = None) -> TradeResult:
        """
        平仓
        
        Args:
            inst_id: 产品ID
            pos_side: 持仓方向（合约/期权需要）
            size: 平仓数量（None表示全部平仓）
            
        Returns:
            TradeResult: 交易结果
        """
        # 默认实现，子类可以覆盖
        position = await self.get_position(inst_id, pos_side)
        if not position or position.size == 0:
            return TradeResult(success=False, error_message="无持仓可平")
        
        close_size = size if size else position.size
        
        # 根据持仓方向决定买卖
        if position.pos_side == PositionSide.LONG:
            return await self.sell(inst_id, close_size)
        else:
            return await self.buy(inst_id, close_size)

    # ==================== 订单管理 ====================

    async def cancel_order(self, inst_id: str, order_id: str) -> bool:
        """
        撤销订单
        
        Args:
            inst_id: 产品ID
            order_id: 订单ID
            
        Returns:
            bool: 是否成功
        """
        try:
            result = await self.rest_client.cancel_order(inst_id, order_id)
            return result.get('code') == '0'
        except Exception as e:
            logger.error(f"撤销订单失败: {e}")
            return False

    async def get_order(self, inst_id: str, order_id: str) -> Optional[Dict]:
        """
        查询订单
        
        Args:
            inst_id: 产品ID
            order_id: 订单ID
            
        Returns:
            Optional[Dict]: 订单信息
        """
        try:
            return await self.rest_client.get_order(inst_id, order_id)
        except Exception as e:
            logger.error(f"查询订单失败: {e}")
            return None
    
    async def get_order_info(self, inst_id: str, ord_id: str) -> Optional[Dict]:
        """
        查询订单信息
        
        Args:
            inst_id: 产品ID
            ord_id: 订单ID
            
        Returns:
            Optional[Dict]: 订单信息
        """
        try:
            if hasattr(self.rest_client, 'get_order_info'):
                return await self.rest_client.get_order_info(inst_id, ord_id)
            else:
                # 尝试使用get_order方法
                return await self.get_order(inst_id, ord_id)
        except Exception as e:
            logger.error(f"查询订单信息失败: {e}")
            return None

    async def get_open_orders(self, inst_id: Optional[str] = None) -> List[Dict]:
        """
        获取未成交订单
        
        Args:
            inst_id: 产品ID（可选）
            
        Returns:
            List[Dict]: 订单列表
        """
        try:
            return await self.rest_client.get_open_orders(inst_id)
        except Exception as e:
            logger.error(f"获取未成交订单失败: {e}")
            return []

    async def get_order_history(self, inst_type: str = "SPOT", inst_id: str = "", 
                               limit: int = 100) -> List[Dict]:
        """
        获取历史订单
        
        Args:
            inst_type: 产品类型
            inst_id: 产品ID
            limit: 数量限制
            
        Returns:
            List[Dict]: 历史订单列表
        """
        try:
            # 确保limit参数不超过OKX API的限制
            if limit > 100:
                limit = 100
            
            if hasattr(self.rest_client, 'get_order_history'):
                return await self.rest_client.get_order_history(inst_type, inst_id, limit)
            else:
                logger.warning("REST客户端不支持获取历史订单")
                return []
        except Exception as e:
            logger.error(f"获取历史订单失败: {e}")
            return []

    async def cancel_all_orders(self, inst_id: str) -> bool:
        """
        取消所有订单
        
        Args:
            inst_id: 产品ID
            
        Returns:
            bool: 是否成功
        """
        try:
            if hasattr(self.rest_client, 'cancel_all_orders'):
                result = await self.rest_client.cancel_all_orders(inst_id)
                return result.get('code') == '0'
            else:
                # 逐个取消订单
                open_orders = await self.get_open_orders(inst_id)
                for order in open_orders:
                    await self.cancel_order(inst_id, order.get('ordId', ''))
                return True
        except Exception as e:
            logger.error(f"取消所有订单失败: {e}")
            return False

    # ==================== 账户和持仓 ====================

    @abstractmethod
    async def get_account_info(self) -> AccountInfo:
        """
        获取账户信息
        
        Returns:
            AccountInfo: 账户信息
        """
        pass

    @abstractmethod
    async def get_position(self, inst_id: str, pos_side: Optional[PositionSide] = None) -> Optional[PositionInfo]:
        """
        获取持仓信息
        
        Args:
            inst_id: 产品ID
            pos_side: 持仓方向（合约/期权需要）
            
        Returns:
            Optional[PositionInfo]: 持仓信息
        """
        pass

    @abstractmethod
    async def get_all_positions(self) -> List[PositionInfo]:
        """
        获取所有持仓
        
        Returns:
            List[PositionInfo]: 持仓列表
        """
        pass
    
    async def get_ticker(self, inst_id: str) -> Optional[Dict]:
        """
        获取市场行情
        
        Args:
            inst_id: 产品ID
            
        Returns:
            Optional[Dict]: 行情信息
        """
        try:
            if hasattr(self.rest_client, 'get_ticker'):
                return await self.rest_client.get_ticker(inst_id)
            else:
                logger.warning("REST客户端不支持获取市场行情")
                return None
        except Exception as e:
            logger.error(f"获取市场行情失败: {e}")
            return None

    # ==================== 风险管理 ====================

    @abstractmethod
    async def get_risk_info(self) -> RiskInfo:
        """
        获取风险信息
        
        Returns:
            RiskInfo: 风险信息
        """
        pass

    async def check_risk_before_trade(self, inst_id: str, side: TradeSide,
                                     size: Decimal) -> Tuple[bool, str]:
        """
        交易前风险检查
        
        Args:
            inst_id: 产品ID
            side: 交易方向
            size: 交易数量
            
        Returns:
            tuple[bool, str]: (是否通过, 原因)
        """
        try:
            risk_info = await self.get_risk_info()
            
            # 检查风险等级
            if risk_info.risk_level == "danger":
                return False, "风险等级过高，禁止交易"
            
            # 检查保证金率
            if risk_info.margin_ratio < Decimal('0.2'):
                return False, f"保证金率过低: {risk_info.margin_ratio}"
            
            return True, "风险检查通过"
        except Exception as e:
            logger.error(f"风险检查失败: {e}")
            return False, f"风险检查失败: {e}"

    # ==================== 杠杆管理（杠杆/合约/期权） ====================

    async def set_leverage(self, inst_id: str, leverage: int,
                          pos_side: Optional[PositionSide] = None) -> bool:
        """
        设置杠杆倍数
        
        Args:
            inst_id: 产品ID
            leverage: 杠杆倍数
            pos_side: 持仓方向（逐仓模式需要）
            
        Returns:
            bool: 是否成功
        """
        # 默认实现，子类可以覆盖
        logger.warning(f"{self.name} 不支持设置杠杆")
        return False

    async def get_leverage(self, inst_id: str,
                          pos_side: Optional[PositionSide] = None) -> Optional[int]:
        """
        获取杠杆倍数
        
        Args:
            inst_id: 产品ID
            pos_side: 持仓方向
            
        Returns:
            Optional[int]: 杠杆倍数
        """
        return None

    # ==================== 借币还币（杠杆专用） ====================

    async def borrow(self, ccy: str, amt: Decimal) -> bool:
        """
        借入币种（杠杆交易）
        
        Args:
            ccy: 币种
            amt: 金额
            
        Returns:
            bool: 是否成功
        """
        # 默认实现，子类可以覆盖
        logger.warning(f"{self.name} 不支持借币")
        return False

    async def repay(self, ccy: str, amt: Decimal) -> bool:
        """
        归还币种（杠杆交易）
        
        Args:
            ccy: 币种
            amt: 金额
            
        Returns:
            bool: 是否成功
        """
        # 默认实现，子类可以覆盖
        logger.warning(f"{self.name} 不支持还币")
        return False

    # ==================== 高级交易功能 ====================

    async def set_trailing_stop(self, inst_id: str, size: Decimal, distance: Decimal, 
                             pos_side: Optional[PositionSide] = None, **kwargs) -> TradeResult:
        """
        设置移动止盈止损
        
        Args:
            inst_id: 产品ID
            size: 数量
            distance: 距离（百分比）
            pos_side: 持仓方向
            **kwargs: 额外参数
            
        Returns:
            TradeResult: 交易结果
        """
        # 默认实现，子类可以覆盖
        logger.warning(f"{self.name} 不支持移动止盈止损")
        return TradeResult(success=False, error_message="不支持移动止盈止损")

    async def set_trigger_order(self, inst_id: str, side: TradeSide, size: Decimal, 
                               trigger_price: Decimal, order_price: Optional[Decimal] = None, **kwargs) -> TradeResult:
        """
        设置计划委托
        
        Args:
            inst_id: 产品ID
            side: 交易方向
            size: 数量
            trigger_price: 触发价格
            order_price: 订单价格
            **kwargs: 额外参数
            
        Returns:
            TradeResult: 交易结果
        """
        # 默认实现，子类可以覆盖
        logger.warning(f"{self.name} 不支持计划委托")
        return TradeResult(success=False, error_message="不支持计划委托")

    # ==================== 订单管理扩展 ====================

    async def get_order_list(self, inst_type: str, inst_id: str = "", 
                           state: str = "filled", limit: int = 100) -> List[Dict]:
        """
        获取订单列表
        
        Args:
            inst_type: 产品类型
            inst_id: 产品ID
            state: 订单状态
            limit: 数量限制
            
        Returns:
            List[Dict]: 订单列表
        """
        try:
            # 这里需要根据实际API实现
            # 暂时返回历史订单
            return await self.get_order_history(inst_type, inst_id, limit)
        except Exception as e:
            logger.error(f"获取订单列表失败: {e}")
            return []

    async def cancel_batch_orders(self, orders: List[Dict]) -> List[Dict]:
        """
        批量撤单
        
        Args:
            orders: 订单列表
            
        Returns:
            List[Dict]: 撤单结果
        """
        try:
            if hasattr(self.rest_client, 'batch_cancel_orders'):
                return await self.rest_client.batch_cancel_orders(orders)
            else:
                logger.warning("REST客户端不支持批量撤单")
                return []
        except Exception as e:
            logger.error(f"批量撤单失败: {e}")
            return []

    # ==================== 手续费管理 ====================

    async def get_fee_rate(self, inst_id: str) -> Dict[str, Decimal]:
        """
        获取手续费率
        
        Args:
            inst_id: 产品ID
            
        Returns:
            Dict[str, Decimal]: 手续费率
        """
        # 默认实现，返回固定费率
        return {
            'maker': Decimal('0.001'),  # 0.1%
            'taker': Decimal('0.001')   # 0.1%
        }

    async def calculate_trading_fee(self, inst_id: str, side: TradeSide, 
                                 size: Decimal, price: Decimal, is_maker: bool = False) -> Decimal:
        """
        计算交易手续费
        
        Args:
            inst_id: 产品ID
            side: 交易方向
            size: 数量
            price: 价格
            is_maker: 是否为maker
            
        Returns:
            Decimal: 手续费
        """
        fee_rates = await self.get_fee_rate(inst_id)
        fee_rate = fee_rates['maker'] if is_maker else fee_rates['taker']
        total_value = size * price
        return total_value * fee_rate

    # ==================== 辅助方法 ====================

    def _parse_balance_response(self, response: Dict) -> AccountInfo:
        """
        解析余额响应
        
        Args:
            response: API响应
            
        Returns:
            AccountInfo: 账户信息
        """
        try:
            details = response.get('details', [])
            currencies = {}
            total_eq = Decimal('0')
            avail_eq = Decimal('0')
            
            for item in details:
                ccy = item.get('ccy', '')
                if not ccy:
                    continue
                    
                currencies[ccy] = {
                    'available': Decimal(item.get('availBal', '0')),
                    'equity': Decimal(item.get('eq', '0')),
                    'frozen': Decimal(item.get('frozenBal', '0')),
                }
                
                # 计算总额
                eq = Decimal(item.get('eq', '0'))
                avail = Decimal(item.get('availBal', '0'))
                total_eq += eq
                avail_eq += avail
            
            return AccountInfo(
                total_equity=total_eq,
                available_balance=avail_eq,
                margin_balance=total_eq,
                unrealized_pnl=Decimal('0'),
                realized_pnl=Decimal('0'),
                currencies=currencies
            )
        except Exception as e:
            logger.error(f"解析余额响应失败: {e}")
            return AccountInfo(
                total_equity=Decimal('0'),
                available_balance=Decimal('0'),
                margin_balance=Decimal('0'),
                unrealized_pnl=Decimal('0'),
                realized_pnl=Decimal('0')
            )

    def _build_order_request(self, inst_id: str, side: TradeSide,
                            size: Decimal, price: Optional[Decimal] = None,
                            order_type: OrderType = OrderType.MARKET,
                            **kwargs) -> Dict:
        """
        构建订单请求
        
        Args:
            inst_id: 产品ID
            side: 交易方向
            size: 数量
            price: 价格
            order_type: 订单类型
            **kwargs: 额外参数
            
        Returns:
            Dict: 订单请求体
        """
        order = {
            "instId": inst_id,
            "tdMode": self.trade_mode.value if self.trade_mode else "cash",
            "side": side.value,
            "ordType": order_type.value,
            "sz": str(size),
        }
        
        if price and order_type in [OrderType.LIMIT, OrderType.POST_ONLY]:
            order["px"] = str(price)
        
        # 添加额外参数
        order.update(kwargs)
        
        return order
