"""
现货交易器 - 实现现货交易功能
"""

from decimal import Decimal
from typing import Optional, List
import logging

from .base_trader import (
    BaseTrader, TradeMode, TradeSide, OrderType, PositionSide,
    TradeResult, PositionInfo, AccountInfo, RiskInfo
)
from core.config.env_manager import env_manager

logger = logging.getLogger(__name__)


class SpotTrader(BaseTrader):
    """
    现货交易器
    
    实现现货交易功能，包括买入、卖出、查询持仓等
    """

    def __init__(self, rest_client, config: dict = None, use_env_config: bool = False):
        super().__init__(rest_client, config)
        self.trade_mode = TradeMode.SPOT
        self.name = "SpotTrader"
        
        # 从环境配置获取参数
        if use_env_config:
            trading_config = env_manager.get_trading_config()
            self.min_order_amount = Decimal(str(trading_config.get('min_order_amount', 1)))
            self.simulate_trading = trading_config.get('simulate_trading', False)
            self.simulate_balance = Decimal(str(trading_config.get('simulate_balance', 10000)))
            logger.info("从环境配置获取交易参数")
        else:
            self.min_order_amount = Decimal('1')  # 最小订单金额 1 USDT
            self.simulate_trading = False
            self.simulate_balance = Decimal('10000')  # 默认模拟账户余额
        
        # 模拟交易相关属性
        self.simulate_positions = {}
        self.simulate_orders = []

    async def buy(self, inst_id: str, size: Decimal, price: Optional[Decimal] = None,
                  order_type: OrderType = OrderType.MARKET, **kwargs) -> TradeResult:
        """
        现货买入
        
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

            # 模拟交易
            if self.simulate_trading:
                import uuid
                order_id = str(uuid.uuid4())
                base_ccy = inst_id.split('-')[0]
                
                # 计算购买数量
                if not price:
                    # 市价单，使用当前价格
                    ticker = await self.rest_client.get_ticker(inst_id)
                    if ticker and isinstance(ticker, dict):
                        price = Decimal(str(ticker.get('last', '0')))
                    else:
                        price = Decimal('10000')  # 默认价格
                
                # 按USDT金额计算购买数量
                buy_size = size / price
                
                # 更新模拟账户余额
                self.simulate_balance -= size
                
                # 更新模拟持仓
                if base_ccy in self.simulate_positions:
                    self.simulate_positions[base_ccy]['size'] += buy_size
                    # 计算新的平均价格
                    old_size = self.simulate_positions[base_ccy]['size'] - buy_size
                    old_avg_price = self.simulate_positions[base_ccy]['avg_price']
                    new_avg_price = (old_size * old_avg_price + size) / self.simulate_positions[base_ccy]['size']
                    self.simulate_positions[base_ccy]['avg_price'] = new_avg_price
                else:
                    self.simulate_positions[base_ccy] = {
                        'size': buy_size,
                        'avg_price': price
                    }
                
                # 记录模拟订单
                self.simulate_orders.append({
                    'order_id': order_id,
                    'inst_id': inst_id,
                    'side': 'buy',
                    'size': size,
                    'price': price,
                    'order_type': order_type.value,
                    'status': 'filled',
                    'timestamp': kwargs.get('timestamp', '2026-04-16T00:00:00')
                })
                
                logger.info(f"模拟现货买入: {inst_id}, 数量: {size}, 价格: {price}, 订单ID: {order_id}")
                
                return TradeResult(
                    success=True,
                    order_id=order_id,
                    raw_response={'order_id': order_id}
                )

            # 构建订单
            order = self._build_order_request(
                inst_id, TradeSide.BUY, size, price, order_type,
                tgtCcy=kwargs.get('tgtCcy', 'quote_ccy'),  # 默认按USDT金额下单
                **{k: v for k, v in kwargs.items() if k != 'tgtCcy'}
            )

            logger.info(f"现货买入: {inst_id}, 数量: {size}, 类型: {order_type.value}")

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
            order_id = await self.rest_client.place_order(**order_params)

            if order_id:
                return TradeResult(
                    success=True,
                    order_id=order_id,
                    raw_response={'order_id': order_id}
                )
            else:
                return TradeResult(
                    success=False,
                    error_message='下单失败: 未返回订单ID',
                    raw_response={}
                )

        except Exception as e:
            logger.error(f"现货买入失败: {e}")
            return TradeResult(success=False, error_message=str(e))

    async def sell(self, inst_id: str, size: Decimal, price: Optional[Decimal] = None,
                   order_type: OrderType = OrderType.MARKET, **kwargs) -> TradeResult:
        """
        现货卖出
        
        Args:
            inst_id: 产品ID，如 "BTC-USDT"
            size: 数量（BTC数量）
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

            # 检查是否为做空操作
            is_short_sell = kwargs.get('is_short_sell', False)
            if not is_short_sell:
                # 检查持仓是否足够
                position = await self.get_position(inst_id)
                if not position or position.size < size:
                    return TradeResult(
                        success=False,
                        error_message=f"持仓不足: 可用 {position.size if position else 0}, 需要 {size}"
                    )
            else:
                logger.info("做空操作：跳过持仓检查，直接执行卖出")

            # 构建订单
            order = self._build_order_request(
                inst_id, TradeSide.SELL, size, price, order_type,
                tgtCcy=kwargs.get('tgtCcy', 'base_ccy'),  # 默认按BTC数量下单
                **{k: v for k, v in kwargs.items() if k != 'tgtCcy'}
            )

            logger.info(f"现货卖出: {inst_id}, 数量: {size}, 类型: {order_type.value}")

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
            order_id = await self.rest_client.place_order(**order_params)

            if order_id:
                return TradeResult(
                    success=True,
                    order_id=order_id,
                    raw_response={'order_id': order_id}
                )
            else:
                return TradeResult(
                    success=False,
                    error_message='下单失败: 未返回订单ID',
                    raw_response={}
                )

        except Exception as e:
            logger.error(f"现货卖出失败: {e}")
            return TradeResult(success=False, error_message=str(e))

    async def validate_trade_types(self) -> dict:
        """
        验证各种交易类型

        Returns:
            dict: 验证结果
        """
        try:
            logger.info("开始验证各种交易类型...")
            results = {}
            
            # 验证现货买入 - 市价单
            logger.info("验证现货买入 - 市价单")
            buy_market_result = await self.buy(
                inst_id="BTC-USDT",
                size=Decimal('1'),  # 1 USDT
                order_type=OrderType.MARKET
            )
            results['buy_market'] = buy_market_result.__dict__
            
            # 验证现货买入 - 限价单
            logger.info("验证现货买入 - 限价单")
            # 获取当前价格
            ticker = await self.rest_client.get_ticker("BTC-USDT")
            if ticker and isinstance(ticker, dict):
                current_price = Decimal(str(ticker.get('last', '0')))
                if current_price > 0:
                    # 设置限价为当前价格的95%，确保订单不会立即成交
                    limit_price = current_price * Decimal('0.95')
                    buy_limit_result = await self.buy(
                        inst_id="BTC-USDT",
                        size=Decimal('1'),  # 1 USDT
                        price=limit_price,
                        order_type=OrderType.LIMIT
                    )
                    results['buy_limit'] = buy_limit_result.__dict__
                else:
                    results['buy_limit'] = {"success": False, "error_message": "无法获取当前价格"}
            else:
                results['buy_limit'] = {"success": False, "error_message": "无法获取当前价格"}
            
            # 验证现货卖出 - 市价单
            logger.info("验证现货卖出 - 市价单")
            # 先获取BTC余额
            account_info = await self.get_account_info()
            btc_balance = Decimal('0')
            if account_info and hasattr(account_info, 'currencies'):
                btc_balance = account_info.currencies.get('BTC', {}).get('available', Decimal('0'))
            
            if btc_balance > Decimal('0'):
                # 卖出所有可用BTC
                sell_market_result = await self.sell(
                    inst_id="BTC-USDT",
                    size=btc_balance,
                    order_type=OrderType.MARKET
                )
                results['sell_market'] = sell_market_result.__dict__
            else:
                results['sell_market'] = {"success": False, "error_message": "BTC余额不足"}
            
            # 验证其他交易对 - ETH-USDT
            logger.info("验证其他交易对 - ETH-USDT")
            eth_buy_result = await self.buy(
                inst_id="ETH-USDT",
                size=Decimal('1'),  # 1 USDT
                order_type=OrderType.MARKET
            )
            results['eth_buy'] = eth_buy_result.__dict__
            
            logger.info("交易类型验证完成")
            return results
        except Exception as e:
            logger.error(f"验证交易类型失败: {e}")
            return {"error": str(e)}

    async def get_account_info(self) -> AccountInfo:
        """
        获取现货账户信息

        Returns:
            AccountInfo: 账户信息
        """
        try:
            response = await self.rest_client.get_account_balance()
            # 处理不同的响应格式
            if isinstance(response, dict):
                if 'code' in response and response.get('code') == '0':
                    # 标准API响应格式
                    data = response.get('data', [{}])[0]
                    return self._parse_balance_response(data)
                elif 'details' in response:
                    # 已经是解析后的数据格式
                    return self._parse_balance_response(response)
                else:
                    logger.error(f"获取账户信息失败: {response}")
                    return AccountInfo(
                        total_equity=Decimal('0'),
                        available_balance=Decimal('0'),
                        margin_balance=Decimal('0'),
                        unrealized_pnl=Decimal('0'),
                        realized_pnl=Decimal('0')
                    )
            else:
                logger.error(f"获取账户信息失败: 无效的响应格式")
                return AccountInfo(
                    total_equity=Decimal('0'),
                    available_balance=Decimal('0'),
                    margin_balance=Decimal('0'),
                    unrealized_pnl=Decimal('0'),
                    realized_pnl=Decimal('0')
                )
        except Exception as e:
            logger.error(f"获取账户信息失败: {e}")
            return AccountInfo(
                total_equity=Decimal('0'),
                available_balance=Decimal('0'),
                margin_balance=Decimal('0'),
                unrealized_pnl=Decimal('0'),
                realized_pnl=Decimal('0')
            )

    async def get_position(self, inst_id: str, pos_side: Optional[PositionSide] = None) -> Optional[PositionInfo]:
        """
        获取现货持仓信息
        
        Args:
            inst_id: 产品ID
            pos_side: 持仓方向（现货不需要）
            
        Returns:
            Optional[PositionInfo]: 持仓信息
        """
        try:
            # 从账户余额中获取持仓
            account_info = await self.get_account_info()
            
            # 解析币种（如 BTC-USDT 中的 BTC）
            base_ccy = inst_id.split('-')[0]
            
            ccy_info = account_info.currencies.get(base_ccy, {})
            size = ccy_info.get('available', Decimal('0'))
            
            if size > 0:
                return PositionInfo(
                    inst_id=inst_id,
                    pos_side=PositionSide.NET,
                    size=size,
                    avg_price=Decimal('0'),  # 现货没有平均价格
                    margin_mode='cash'
                )
            return None

        except Exception as e:
            logger.error(f"获取持仓失败: {e}")
            return None

    async def get_all_positions(self) -> List[PositionInfo]:
        """
        获取所有现货持仓
        
        Returns:
            List[PositionInfo]: 持仓列表
        """
        try:
            account_info = await self.get_account_info()
            positions = []
            
            for ccy, info in account_info.currencies.items():
                size = info.get('available', Decimal('0'))
                if size > 0 and ccy not in ['USDT', 'USDC']:  # 排除稳定币
                    positions.append(PositionInfo(
                        inst_id=f"{ccy}-USDT",
                        pos_side=PositionSide.NET,
                        size=size,
                        avg_price=Decimal('0'),
                        margin_mode='cash'
                    ))
            
            return positions

        except Exception as e:
            logger.error(f"获取所有持仓失败: {e}")
            return []

    async def get_risk_info(self) -> RiskInfo:
        """
        获取现货风险信息
        
        现货交易风险较低，主要检查余额是否充足
        
        Returns:
            RiskInfo: 风险信息
        """
        try:
            account_info = await self.get_account_info()
            
            # 现货没有保证金率概念，用余额充足度作为风险指标
            usdt_balance = account_info.currencies.get('USDT', {}).get('available', Decimal('0'))
            btc_balance = account_info.currencies.get('BTC', {}).get('available', Decimal('0'))
            
            # 简单的风险等级判断 - 只要有足够的BTC或USDT就认为是安全的
            # 对于卖出操作，只要有BTC持仓就允许
            # 对于买入操作，只要有足够的USDT就允许
            if usdt_balance < self.min_order_amount and btc_balance < Decimal('0.00001'):
                # 既没有USDT也没有BTC，才是危险状态
                risk_level = "danger"
            elif usdt_balance < self.min_order_amount * 2 and btc_balance < Decimal('0.00005'):
                risk_level = "warning"
            else:
                risk_level = "safe"
            
            return RiskInfo(
                margin_ratio=Decimal('1'),  # 现货没有保证金率，设为100%
                maintenance_margin_ratio=Decimal('0'),
                risk_level=risk_level
            )

        except Exception as e:
            logger.error(f"获取风险信息失败: {e}")
            return RiskInfo(
                margin_ratio=Decimal('0'),
                maintenance_margin_ratio=Decimal('0'),
                risk_level="danger"
            )

    async def get_available_balance(self, ccy: str = 'USDT') -> Decimal:
        """
        获取可用余额
        
        Args:
            ccy: 币种
            
        Returns:
            Decimal: 可用余额
        """
        try:
            account_info = await self.get_account_info()
            return account_info.currencies.get(ccy, {}).get('available', Decimal('0'))
        except Exception as e:
            logger.error(f"获取可用余额失败: {e}")
            return Decimal('0')

    async def set_take_profit(self, inst_id: str, size: Decimal, price: Decimal,
                              pos_side: Optional[PositionSide] = None, **kwargs) -> TradeResult:
        """
        设置现货止盈单
        
        Args:
            inst_id: 产品ID
            size: 数量
            price: 止盈价格
            pos_side: 持仓方向（现货不需要）
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
            
            logger.info(f"设置现货止盈: {inst_id}, 数量: {size}, 价格: {price}")
            
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
            logger.error(f"设置止盈失败: {e}")
            return TradeResult(success=False, error_message=str(e))

    async def set_stop_loss(self, inst_id: str, size: Decimal, price: Decimal,
                            pos_side: Optional[PositionSide] = None, **kwargs) -> TradeResult:
        """
        设置现货止损单
        
        Args:
            inst_id: 产品ID
            size: 数量
            price: 止损价格
            pos_side: 持仓方向（现货不需要）
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
            
            logger.info(f"设置现货止损: {inst_id}, 数量: {size}, 价格: {price}")
            
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
            logger.error(f"设置止损失败: {e}")
            return TradeResult(success=False, error_message=str(e))
