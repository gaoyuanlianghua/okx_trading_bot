"""
杠杆交易器 - 实现杠杆交易功能
"""

from decimal import Decimal
from typing import Optional, List
import logging

from .base_trader import (
    BaseTrader, TradeMode, TradeSide, OrderType, PositionSide,
    TradeResult, PositionInfo, AccountInfo, RiskInfo
)

logger = logging.getLogger(__name__)


class MarginTrader(BaseTrader):
    """
    杠杆交易器
    
    实现杠杆交易功能，包括全仓杠杆和逐仓杠杆
    """

    def __init__(self, rest_client, config: dict = None, use_env_config: bool = False):
        super().__init__(rest_client, config, use_env_config)
        # 默认使用全仓杠杆
        self.trade_mode = TradeMode.MARGIN_CROSS
        self.name = "MarginTrader"
        self.min_order_amount = Decimal('1')  # 最小订单金额 1 USDT
        self.leverage = Decimal('2')  # 默认 2 倍杠杆

    async def buy(self, inst_id: str, size: Decimal, price: Optional[Decimal] = None,
                  order_type: OrderType = OrderType.MARKET, **kwargs) -> TradeResult:
        """
        杠杆买入（做多）
        
        Args:
            inst_id: 产品ID，如 "BTC-USDT"
            size: 数量（USDT金额或BTC数量）
            price: 价格（限价单必填）
            order_type: 订单类型
            **kwargs: 额外参数，如 tgtCcy="quote_ccy" 表示按USDT金额下单
            
        Returns:
            TradeResult: 交易结果
        """
        try:
            # 风险检查
            passed, reason = await self.check_risk_before_trade(inst_id, TradeSide.BUY, size)
            if not passed:
                return TradeResult(success=False, error_message=reason)

            # 检查最小订单金额
            if size < self.min_order_amount:
                return TradeResult(
                    success=False,
                    error_message=f"订单金额小于最小限制 {self.min_order_amount} USDT"
                )

            # 构建订单
            order = self._build_order_request(
                inst_id, TradeSide.BUY, size, price, order_type,
                tgtCcy=kwargs.get('tgtCcy', 'quote_ccy'),  # 默认按USDT金额下单
                **{k: v for k, v in kwargs.items() if k != 'tgtCcy'}
            )

            logger.info(f"杠杆买入: {inst_id}, 数量: {size}, 类型: {order_type.value}")

            # 发送订单
            order_id = await self.rest_client.place_order(
                inst_id=order.get('instId'),
                side=order.get('side'),
                ord_type=order.get('ordType'),
                sz=order.get('sz'),
                td_mode=order.get('tdMode', 'cross'),
                tgtCcy=order.get('tgtCcy', 'quote_ccy')
            )

            if order_id:
                return TradeResult(
                    success=True,
                    order_id=order_id,
                    raw_response={"orderId": order_id}
                )
            else:
                return TradeResult(
                    success=False,
                    error_message='下单失败: 未返回订单ID',
                    raw_response=None
                )

        except Exception as e:
            logger.error(f"杠杆买入失败: {e}")
            return TradeResult(success=False, error_message=str(e))

    async def sell(self, inst_id: str, size: Decimal, price: Optional[Decimal] = None,
                   order_type: OrderType = OrderType.MARKET, **kwargs) -> TradeResult:
        """
        杠杆卖出（平仓或做空）
        
        Args:
            inst_id: 产品ID，如 "BTC-USDT"
            size: 数量（BTC数量）
            price: 价格（限价单必填）
            order_type: 订单类型
            **kwargs: 额外参数，包括 is_short_sell 表示是否为做空操作
            
        Returns:
            TradeResult: 交易结果
        """
        try:
            # 风险检查
            passed, reason = await self.check_risk_before_trade(inst_id, TradeSide.SELL, size)
            if not passed:
                return TradeResult(success=False, error_message=reason)

            # 检查是否为做空操作
            is_short_sell = kwargs.get('is_short_sell', False)
            
            if not is_short_sell:
                # 不是做空操作，检查持仓数量
                # 直接从REST客户端获取持仓信息，避免杠杆计算错误
                positions = await self.rest_client.get_positions(inst_type="MARGIN", inst_id=inst_id)
                
                actual_size = Decimal('0')
                for position in positions:
                    if position.get('instId') == inst_id:
                        # 获取实际可用持仓数量（未乘以杠杆）
                        avail_pos = position.get('availPos', '0')
                        actual_size = Decimal(avail_pos) if avail_pos else Decimal('0')
                        break

                # 检查持仓是否足够
                if actual_size < size:
                    # 持仓不足，使用实际可用的持仓数量
                    size = actual_size
                    logger.warning(f"持仓不足，调整卖出数量为实际可用持仓: {size}")
                
                # 检查调整后的卖出数量是否为 0
                if size <= 0:
                    return TradeResult(
                        success=False,
                        error_message=f"卖出数量为 0，无法执行交易"
                    )
                
                # 检查调整后的卖出数量是否小于 OKX API 要求的最小交易数量
                min_sz = Decimal('0.00001')  # BTC 最小交易单位
                if size < min_sz:
                    return TradeResult(
                        success=False,
                        error_message=f"卖出数量 {size} BTC 小于最小交易单位 {min_sz} BTC，无法执行交易"
                    )
            else:
                # 是做空操作，跳过持仓检查，直接执行做空
                logger.info("🔄 做空操作：跳过持仓检查，直接执行做空")
                # 检查卖出数量是否小于 OKX API 要求的最小交易数量
                min_sz = Decimal('0.00001')  # BTC 最小交易单位
                if size < min_sz:
                    return TradeResult(
                        success=False,
                        error_message=f"卖出数量 {size} BTC 小于最小交易单位 {min_sz} BTC，无法执行交易"
                    )

            # 构建订单
            order = self._build_order_request(
                inst_id, TradeSide.SELL, size, price, order_type,
                tgtCcy=kwargs.get('tgtCcy', 'base_ccy'),  # 默认按BTC数量下单
                **{k: v for k, v in kwargs.items() if k != 'tgtCcy'}
            )

            logger.info(f"杠杆卖出: {inst_id}, 数量: {size}, 类型: {order_type.value}")

            # 发送订单
            order_id = await self.rest_client.place_order(
                inst_id=order.get('instId'),
                side=order.get('side'),
                ord_type=order.get('ordType'),
                sz=order.get('sz'),
                td_mode=order.get('tdMode', 'cross'),
                tgtCcy=order.get('tgtCcy', 'quote_ccy')
            )

            if order_id:
                return TradeResult(
                    success=True,
                    order_id=order_id,
                    raw_response={"orderId": order_id}
                )
            else:
                return TradeResult(
                    success=False,
                    error_message='下单失败: 未返回订单ID',
                    raw_response=None
                )

        except Exception as e:
            logger.error(f"杠杆卖出失败: {e}")
            return TradeResult(success=False, error_message=str(e))

    async def get_account_info(self) -> AccountInfo:
        """
        获取杠杆账户信息

        Returns:
            AccountInfo: 账户信息
        """
        try:
            response = await self.rest_client.get_margin_account_balance()
            # 处理不同的响应格式
            if isinstance(response, dict):
                # 解析响应获取账户余额数据
                account_info = self._parse_margin_balance_response(response)
                # 考虑杠杆倍数，计算杠杆后的可用余额
                if account_info.available_balance > 0:
                    # 杠杆后的可用余额 = 可用余额 * 杠杆倍数
                    leveraged_available = account_info.available_balance * self.leverage
                    # 更新可用余额为杠杆后的余额
                    account_info.available_balance = leveraged_available
                
                # 注意：currencies 中的可用余额保持原始值，不乘以杠杆倍数
                # 因为这些值将在 get_position 方法中单独处理
                return account_info
            else:
                logger.error(f"获取杠杆账户信息失败: 无效的响应格式")
                return AccountInfo(
                    total_equity=Decimal('0'),
                    available_balance=Decimal('0'),
                    margin_balance=Decimal('0'),
                    unrealized_pnl=Decimal('0'),
                    realized_pnl=Decimal('0')
                )
        except Exception as e:
            logger.error(f"获取杠杆账户信息失败: {e}")
            return AccountInfo(
                total_equity=Decimal('0'),
                available_balance=Decimal('0'),
                margin_balance=Decimal('0'),
                unrealized_pnl=Decimal('0'),
                realized_pnl=Decimal('0')
            )

    async def get_position(self, inst_id: str, pos_side: Optional[PositionSide] = None) -> Optional[PositionInfo]:
        """
        获取杠杆持仓信息
        
        Args:
            inst_id: 产品ID
            pos_side: 持仓方向（杠杆不需要）
            
        Returns:
            Optional[PositionInfo]: 持仓信息
        """
        try:
            # 直接从REST客户端获取持仓信息，避免双重计算杠杆
            positions = await self.rest_client.get_positions(inst_type="MARGIN", inst_id=inst_id)
            
            for position in positions:
                if position.get('instId') == inst_id:
                    # 解析持仓数量
                    size = Decimal(position.get('availPos', '0'))
                    
                    # 考虑杠杆倍数，计算杠杆后的持仓数量
                    if size > 0:
                        # 杠杆后的持仓数量 = 持仓数量 * 杠杆倍数
                        leveraged_size = size * self.leverage
                        logger.info(f"原始持仓: {size} BTC, 杠杆倍数: {self.leverage}, 杠杆后持仓: {leveraged_size} BTC")
                        # 检查avgPx是否为空
                        avg_px = position.get('avgPx', '0')
                        avg_px = '0' if not avg_px else avg_px
                        return PositionInfo(
                            inst_id=inst_id,
                            pos_side=PositionSide.NET,
                            size=leveraged_size,
                            avg_price=Decimal(avg_px),
                            margin_mode=position.get('mgnMode', 'cross')
                        )
            
            # 如果没有持仓，返回None
            return None

        except Exception as e:
            logger.error(f"获取杠杆持仓失败: {e}")
            return None

    async def get_all_positions(self) -> List[PositionInfo]:
        """
        获取所有杠杆持仓
        
        Returns:
            List[PositionInfo]: 持仓列表
        """
        try:
            # 直接从REST客户端获取所有杠杆持仓
            positions = await self.rest_client.get_positions(inst_type="MARGIN")
            result = []
            
            for position in positions:
                inst_id = position.get('instId')
                if not inst_id:
                    continue
                
                # 解析持仓数量
                size = Decimal(position.get('availPos', '0'))
                if size > 0:
                    # 考虑杠杆倍数，计算杠杆后的持仓数量
                    leveraged_size = size * self.leverage
                    # 检查avgPx是否为空
                    avg_px = position.get('avgPx', '0')
                    avg_px = '0' if not avg_px else avg_px
                    result.append(PositionInfo(
                        inst_id=inst_id,
                        pos_side=PositionSide.NET,
                        size=leveraged_size,
                        avg_price=Decimal(avg_px),
                        margin_mode=position.get('mgnMode', 'cross')
                    ))
            return result

        except Exception as e:
            logger.error(f"获取所有杠杆持仓失败: {e}")
            return []

    async def get_risk_info(self) -> RiskInfo:
        """
        获取杠杆风险信息

        Returns:
            RiskInfo: 风险信息
        """
        try:
            account_info = await self.get_account_info()
            
            # 计算保证金率
            total_equity = account_info.total_equity
            margin_balance = account_info.margin_balance
            
            if margin_balance > 0:
                margin_ratio = total_equity / margin_balance
            else:
                # 当没有持仓时，margin_balance 为 0，这是正常情况，设置为安全状态
                margin_ratio = Decimal('100')  # 一个很大的值，表示安全
            
            # 计算维持保证金率
            # 维持保证金率 = 1 / 杠杆倍数
            maintenance_margin_ratio = Decimal('1') / self.leverage
            
            # 风险等级判断
            if margin_ratio < maintenance_margin_ratio * Decimal('1.1'):
                risk_level = "danger"
            elif margin_ratio < maintenance_margin_ratio * Decimal('1.5'):
                risk_level = "warning"
            else:
                risk_level = "safe"
            
            # 检查是否接近强制平仓
            if margin_ratio < maintenance_margin_ratio:
                logger.warning(f"⚠️ 保证金率 {margin_ratio:.2f} 低于维持保证金率 {maintenance_margin_ratio:.2f}，可能会强制平仓")
            
            return RiskInfo(
                margin_ratio=margin_ratio,
                maintenance_margin_ratio=maintenance_margin_ratio,
                risk_level=risk_level
            )

        except Exception as e:
            logger.error(f"获取杠杆风险信息失败: {e}")
            return RiskInfo(
                margin_ratio=Decimal('0'),
                maintenance_margin_ratio=Decimal('0'),
                risk_level="danger"
            )

    async def set_take_profit(self, inst_id: str, size: Decimal, price: Decimal,
                              pos_side: Optional[PositionSide] = None, **kwargs) -> TradeResult:
        """
        设置杠杆止盈单
        
        Args:
            inst_id: 产品ID
            size: 数量
            price: 止盈价格
            pos_side: 持仓方向（杠杆不需要）
            **kwargs: 额外参数
            
        Returns:
            TradeResult: 交易结果
        """
        try:
            # 构建止盈单
            order = {
                "instId": inst_id,
                "tdMode": self.trade_mode.value,
                "side": "sell",  # 止盈是卖出
                "ordType": "conditional",
                "sz": str(size),
                "px": str(price),
                "triggerPx": str(price),
                "triggerDir": "1",  # 价格上涨触发
                "tgtCcy": kwargs.get('tgtCcy', 'base_ccy')
            }
            
            logger.info(f"设置杠杆止盈: {inst_id}, 数量: {size}, 价格: {price}")
            
            response = await self.rest_client.place_order(order)
            
            if response.get('code') == '0':
                data = response.get('data', [{}])[0]
                return TradeResult(
                    success=True,
                    order_id=data.get('ordId'),
                    raw_response=response
                )
            else:
                return TradeResult(
                    success=False,
                    error_message=response.get('msg', '设置止盈失败'),
                    raw_response=response
                )
        except Exception as e:
            logger.error(f"设置杠杆止盈失败: {e}")
            return TradeResult(success=False, error_message=str(e))

    async def set_stop_loss(self, inst_id: str, size: Decimal, price: Decimal,
                            pos_side: Optional[PositionSide] = None, **kwargs) -> TradeResult:
        """
        设置杠杆止损单
        
        Args:
            inst_id: 产品ID
            size: 数量
            price: 止损价格
            pos_side: 持仓方向（杠杆不需要）
            **kwargs: 额外参数
            
        Returns:
            TradeResult: 交易结果
        """
        try:
            # 构建止损单
            order = {
                "instId": inst_id,
                "tdMode": self.trade_mode.value,
                "side": "sell",  # 止损是卖出
                "ordType": "conditional",
                "sz": str(size),
                "px": str(price),
                "triggerPx": str(price),
                "triggerDir": "2",  # 价格下跌触发
                "tgtCcy": kwargs.get('tgtCcy', 'base_ccy')
            }
            
            logger.info(f"设置杠杆止损: {inst_id}, 数量: {size}, 价格: {price}")
            
            response = await self.rest_client.place_order(order)
            
            if response.get('code') == '0':
                data = response.get('data', [{}])[0]
                return TradeResult(
                    success=True,
                    order_id=data.get('ordId'),
                    raw_response=response
                )
            else:
                return TradeResult(
                    success=False,
                    error_message=response.get('msg', '设置止损失败'),
                    raw_response=response
                )
        except Exception as e:
            logger.error(f"设置杠杆止损失败: {e}")
            return TradeResult(success=False, error_message=str(e))

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
        try:
            # 调用设置杠杆方法
            response = await self.rest_client.set_leverage(
                inst_id=inst_id,
                lever=str(leverage),
                mgn_mode=self.trade_mode.value
            )
            
            # 检查 response 是否为列表（OKX API 返回的是列表）
            if isinstance(response, list) and len(response) > 0:
                logger.info(f"设置杠杆倍数成功: {inst_id}, 杠杆: {leverage}x")
                return True
            else:
                logger.error(f"设置杠杆倍数失败: 响应格式错误, 响应: {response}")
                return False
        except Exception as e:
            logger.error(f"设置杠杆倍数失败: {e}")
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
        try:
            # 从账户信息中获取杠杆倍数
            # 这里需要根据实际API实现
            # 暂时返回默认值
            return 20  # 默认20倍杠杆
        except Exception as e:
            logger.error(f"获取杠杆倍数失败: {e}")
            return None

    async def borrow(self, ccy: str, amt: Decimal) -> bool:
        """
        借入币种（杠杆交易）
        
        Args:
            ccy: 币种
            amt: 金额
            
        Returns:
            bool: 是否成功
        """
        try:
            # 构建借币请求
            request = {
                "ccy": ccy,
                "amt": str(amt),
                "side": "borrow"
            }
            
            response = await self.rest_client.margin_borrow_repay(**request)
            
            if response.get('code') == '0':
                logger.info(f"借币成功: {amt} {ccy}")
                return True
            else:
                logger.error(f"借币失败: {response.get('msg', '未知错误')}")
                return False
        except Exception as e:
            logger.error(f"借币失败: {e}")
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
        try:
            # 构建还币请求
            request = {
                "ccy": ccy,
                "amt": str(amt),
                "side": "repay"
            }
            
            response = await self.rest_client.margin_borrow_repay(**request)
            
            if response.get('code') == '0':
                logger.info(f"还币成功: {amt} {ccy}")
                return True
            else:
                logger.error(f"还币失败: {response.get('msg', '未知错误')}")
                return False
        except Exception as e:
            logger.error(f"还币失败: {e}")
            return False

    def _parse_margin_balance_response(self, response: dict) -> AccountInfo:
        """
        解析杠杆余额响应
        
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
            margin_balance = Decimal('0')
            unrealized_pnl = Decimal('0')
            realized_pnl = Decimal('0')
            
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
            
            # 计算保证金和盈亏
            if 'totalEq' in response:
                total_eq_value = response.get('totalEq', '0')
                if total_eq_value:
                    total_eq = Decimal(total_eq_value)
            if 'availEq' in response:
                avail_eq_value = response.get('availEq', '0')
                if avail_eq_value:
                    avail_eq = Decimal(avail_eq_value)
            if 'adjEq' in response:
                adj_eq_value = response.get('adjEq', '0')
                if adj_eq_value:
                    margin_balance = Decimal(adj_eq_value)
            if 'unrealizedPnl' in response:
                unrealized_pnl_value = response.get('unrealizedPnl', '0')
                if unrealized_pnl_value:
                    unrealized_pnl = Decimal(unrealized_pnl_value)
            if 'realizedPnl' in response:
                realized_pnl_value = response.get('realizedPnl', '0')
                if realized_pnl_value:
                    realized_pnl = Decimal(realized_pnl_value)
            
            return AccountInfo(
                total_equity=total_eq,
                available_balance=avail_eq,
                margin_balance=margin_balance,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=realized_pnl,
                currencies=currencies
            )
        except Exception as e:
            logger.error(f"解析杠杆余额响应失败: {e}")
            return AccountInfo(
                total_equity=Decimal('0'),
                available_balance=Decimal('0'),
                margin_balance=Decimal('0'),
                unrealized_pnl=Decimal('0'),
                realized_pnl=Decimal('0')
            )
