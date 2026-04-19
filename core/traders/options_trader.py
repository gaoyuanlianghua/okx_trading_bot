"""
期权交易器 - 实现期权交易功能
"""

from decimal import Decimal
from typing import Optional, List
import logging

from .base_trader import (
    BaseTrader, TradeMode, TradeSide, OrderType, PositionSide,
    TradeResult, PositionInfo, AccountInfo, RiskInfo
)

logger = logging.getLogger(__name__)


class OptionsTrader(BaseTrader):
    """
    期权交易器
    
    实现期权交易功能
    """

    def __init__(self, rest_client, config: dict = None, use_env_config: bool = False):
        super().__init__(rest_client, config, use_env_config)
        self.trade_mode = TradeMode.OPTIONS
        self.name = "OptionsTrader"
        self.min_order_amount = Decimal('1')  # 最小订单金额 1 USDT

    async def buy(self, inst_id: str, size: Decimal, price: Optional[Decimal] = None,
                  order_type: OrderType = OrderType.MARKET, **kwargs) -> TradeResult:
        """
        期权买入（看涨期权）
        
        Args:
            inst_id: 产品ID，如 "BTC-210625-90000-C"
            size: 数量（张数）
            price: 价格（限价单必填）
            order_type: 订单类型
            **kwargs: 额外参数
            
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
                **kwargs
            )

            logger.info(f"期权买入: {inst_id}, 数量: {size}, 类型: {order_type.value}")

            # 转换参数名从驼峰到下滑线
            order_params = {
                'inst_id': order.get('instId'),
                'side': order.get('side'),
                'ord_type': order.get('ordType'),
                'sz': order.get('sz'),
                'td_mode': order.get('tdMode', 'cash')
            }
            if 'px' in order:
                order_params['px'] = order.get('px')

            # 发送订单
            response = await self.rest_client.place_order(**order_params)

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
                    error_message=response.get('msg', '下单失败'),
                    raw_response=response
                )

        except Exception as e:
            logger.error(f"期权买入失败: {e}")
            return TradeResult(success=False, error_message=str(e))

    async def sell(self, inst_id: str, size: Decimal, price: Optional[Decimal] = None,
                   order_type: OrderType = OrderType.MARKET, **kwargs) -> TradeResult:
        """
        期权卖出（看跌期权或平仓）
        
        Args:
            inst_id: 产品ID，如 "BTC-210625-90000-P"
            size: 数量（张数）
            price: 价格（限价单必填）
            order_type: 订单类型
            **kwargs: 额外参数
            
        Returns:
            TradeResult: 交易结果
        """
        try:
            # 风险检查
            passed, reason = await self.check_risk_before_trade(inst_id, TradeSide.SELL, size)
            if not passed:
                return TradeResult(success=False, error_message=reason)

            # 检查持仓是否足够
            position = await self.get_position(inst_id)
            if not position or position.size < size:
                return TradeResult(
                    success=False,
                    error_message=f"持仓不足: 可用 {position.size if position else 0}, 需要 {size}"
                )

            # 构建订单
            order = self._build_order_request(
                inst_id, TradeSide.SELL, size, price, order_type,
                **kwargs
            )

            logger.info(f"期权卖出: {inst_id}, 数量: {size}, 类型: {order_type.value}")

            # 转换参数名从驼峰到下滑线
            order_params = {
                'inst_id': order.get('instId'),
                'side': order.get('side'),
                'ord_type': order.get('ordType'),
                'sz': order.get('sz'),
                'td_mode': order.get('tdMode', 'cash')
            }
            if 'px' in order:
                order_params['px'] = order.get('px')

            # 发送订单
            response = await self.rest_client.place_order(**order_params)

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
                    error_message=response.get('msg', '下单失败'),
                    raw_response=response
                )

        except Exception as e:
            logger.error(f"期权卖出失败: {e}")
            return TradeResult(success=False, error_message=str(e))

    async def get_account_info(self) -> AccountInfo:
        """
        获取期权账户信息

        Returns:
            AccountInfo: 账户信息
        """
        try:
            response = await self.rest_client.get_options_account_balance()
            # 处理不同的响应格式
            if isinstance(response, dict):
                if 'code' in response and response.get('code') == '0':
                    # 标准API响应格式
                    data = response.get('data', [{}])[0]
                    return self._parse_options_balance_response(data)
                else:
                    logger.error(f"获取期权账户信息失败: {response}")
                    return AccountInfo(
                        total_equity=Decimal('0'),
                        available_balance=Decimal('0'),
                        margin_balance=Decimal('0'),
                        unrealized_pnl=Decimal('0'),
                        realized_pnl=Decimal('0')
                    )
            else:
                logger.error(f"获取期权账户信息失败: 无效的响应格式")
                return AccountInfo(
                    total_equity=Decimal('0'),
                    available_balance=Decimal('0'),
                    margin_balance=Decimal('0'),
                    unrealized_pnl=Decimal('0'),
                    realized_pnl=Decimal('0')
                )
        except Exception as e:
            logger.error(f"获取期权账户信息失败: {e}")
            return AccountInfo(
                total_equity=Decimal('0'),
                available_balance=Decimal('0'),
                margin_balance=Decimal('0'),
                unrealized_pnl=Decimal('0'),
                realized_pnl=Decimal('0')
            )

    async def get_position(self, inst_id: str, pos_side: Optional[PositionSide] = None) -> Optional[PositionInfo]:
        """
        获取期权持仓信息
        
        Args:
            inst_id: 产品ID
            pos_side: 持仓方向（期权不需要）
            
        Returns:
            Optional[PositionInfo]: 持仓信息
        """
        try:
            # 获取期权持仓
            response = await self.rest_client.get_options_position(inst_id)
            
            if isinstance(response, dict) and response.get('code') == '0':
                data = response.get('data', [])
                
                for pos in data:
                    return PositionInfo(
                        inst_id=inst_id,
                        pos_side=PositionSide.NET,  # 期权使用净持仓
                        size=Decimal(pos.get('pos', '0')),
                        avg_price=Decimal(pos.get('avgPx', '0')),
                        mark_price=Decimal(pos.get('markPx', '0')),
                        unrealized_pnl=Decimal(pos.get('unrealizedPnl', '0')),
                        realized_pnl=Decimal(pos.get('realizedPnl', '0')),
                        margin_mode='cash'  # 期权使用现金模式
                    )
            return None

        except Exception as e:
            logger.error(f"获取期权持仓失败: {e}")
            return None

    async def get_all_positions(self) -> List[PositionInfo]:
        """
        获取所有期权持仓
        
        Returns:
            List[PositionInfo]: 持仓列表
        """
        try:
            response = await self.rest_client.get_options_positions()
            
            if isinstance(response, dict) and response.get('code') == '0':
                data = response.get('data', [])
                positions = []
                
                for pos in data:
                    inst_id = pos.get('instId', '')
                    if not inst_id:
                        continue
                    
                    positions.append(PositionInfo(
                        inst_id=inst_id,
                        pos_side=PositionSide.NET,  # 期权使用净持仓
                        size=Decimal(pos.get('pos', '0')),
                        avg_price=Decimal(pos.get('avgPx', '0')),
                        mark_price=Decimal(pos.get('markPx', '0')),
                        unrealized_pnl=Decimal(pos.get('unrealizedPnl', '0')),
                        realized_pnl=Decimal(pos.get('realizedPnl', '0')),
                        margin_mode='cash'  # 期权使用现金模式
                    ))
                
                return positions
            return []

        except Exception as e:
            logger.error(f"获取所有期权持仓失败: {e}")
            return []

    async def get_risk_info(self) -> RiskInfo:
        """
        获取期权风险信息
        
        Returns:
            RiskInfo: 风险信息
        """
        try:
            account_info = await self.get_account_info()
            
            # 计算期权风险指标
            total_equity = account_info.total_equity
            available_balance = account_info.available_balance
            
            # 风险等级判断
            if available_balance < self.min_order_amount * 2:
                risk_level = "danger"
            elif available_balance < self.min_order_amount * 5:
                risk_level = "warning"
            else:
                risk_level = "safe"
            
            return RiskInfo(
                margin_ratio=Decimal('1'),  # 期权使用现金，没有保证金率
                maintenance_margin_ratio=Decimal('0'),
                risk_level=risk_level
            )

        except Exception as e:
            logger.error(f"获取期权风险信息失败: {e}")
            return RiskInfo(
                margin_ratio=Decimal('0'),
                maintenance_margin_ratio=Decimal('0'),
                risk_level="danger"
            )

    async def set_take_profit(self, inst_id: str, size: Decimal, price: Decimal,
                              pos_side: Optional[PositionSide] = None, **kwargs) -> TradeResult:
        """
        设置期权止盈单
        
        Args:
            inst_id: 产品ID
            size: 数量
            price: 止盈价格
            pos_side: 持仓方向（期权不需要）
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
            }
            
            logger.info(f"设置期权止盈: {inst_id}, 数量: {size}, 价格: {price}")
            
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
            logger.error(f"设置期权止盈失败: {e}")
            return TradeResult(success=False, error_message=str(e))

    async def set_stop_loss(self, inst_id: str, size: Decimal, price: Decimal,
                            pos_side: Optional[PositionSide] = None, **kwargs) -> TradeResult:
        """
        设置期权止损单
        
        Args:
            inst_id: 产品ID
            size: 数量
            price: 止损价格
            pos_side: 持仓方向（期权不需要）
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
            }
            
            logger.info(f"设置期权止损: {inst_id}, 数量: {size}, 价格: {price}")
            
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
            logger.error(f"设置期权止损失败: {e}")
            return TradeResult(success=False, error_message=str(e))

    def _parse_options_balance_response(self, response: dict) -> AccountInfo:
        """
        解析期权余额响应
        
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
                total_eq = Decimal(response.get('totalEq', '0'))
            if 'availEq' in response:
                avail_eq = Decimal(response.get('availEq', '0'))
            if 'unrealizedPnl' in response:
                unrealized_pnl = Decimal(response.get('unrealizedPnl', '0'))
            if 'realizedPnl' in response:
                realized_pnl = Decimal(response.get('realizedPnl', '0'))
            
            return AccountInfo(
                total_equity=total_eq,
                available_balance=avail_eq,
                margin_balance=margin_balance,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=realized_pnl,
                currencies=currencies
            )
        except Exception as e:
            logger.error(f"解析期权余额响应失败: {e}")
            return AccountInfo(
                total_equity=Decimal('0'),
                available_balance=Decimal('0'),
                margin_balance=Decimal('0'),
                unrealized_pnl=Decimal('0'),
                realized_pnl=Decimal('0')
            )
