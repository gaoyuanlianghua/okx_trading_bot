"""
账户同步智能体 - 实时更新账户信息和订单校对

负责：
1. 定期从OKX API获取账户信息
2. 定期从OKX API获取订单信息
3. 与本地记录进行校对
4. 发布账户更新事件
5. 发布订单校对事件
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal

from .base_agent import BaseAgent
from core.events.event_bus import Event, EventType, event_bus
from core.api.okx_rest_client import OKXRESTClient

logger = logging.getLogger(__name__)


class AccountSyncAgent(BaseAgent):
    """
    账户同步智能体
    
    实时更新账户信息和订单校对
    """

    def __init__(self, config, rest_client: OKXRESTClient):
        """
        初始化账户同步智能体
        
        Args:
            config: 智能体配置
            rest_client: OKX REST API客户端
        """
        super().__init__(config)
        self.rest_client = rest_client
        self.name = "AccountSync"
        self.update_interval = 5  # 每5秒更新一次
        self.last_update_time = 0
        self.account_info = None
        self.orders_info = None
        self.pending_orders = None
        self.history_orders = None
        self.positions_info = None
        self.positions_history_info = None
        self.risk_info = None
        self.bills_info = None
        self.bills_archive_info = None
        self.bill_types_info = None
        self.account_config_info = None
        self.interest_accrued_info = None
        self.interest_rate_info = None
        self.greeks_info = None
        
        # 本地订单记录，用于校对
        self.local_orders = {}
        
        # 使用全局事件总线
        self.event_bus = event_bus
        
        # 订阅ACCOUNT_UPDATE事件（来自WebSocket）
        self.event_bus.subscribe(EventType.ACCOUNT_UPDATE, self._handle_account_update, async_callback=True)
        # 订阅POSITIONS_UPDATE事件（来自WebSocket）
        self.event_bus.subscribe(EventType.POSITIONS_UPDATE, self._handle_positions_update, async_callback=True)
        # 订阅RISK_ALERT事件（来自WebSocket的强平预警）
        self.event_bus.subscribe(EventType.RISK_ALERT, self._handle_liquidation_warning, async_callback=True)
        
        logger.info("账户同步智能体初始化完成")

    async def _initialize(self):
        """
        初始化智能体
        """
        await super()._initialize()
        logger.info("账户同步智能体初始化完成")

    async def start(self):
        """
        启动智能体
        """
        if self._running:
            return
        
        self._running = True
        logger.info("账户同步智能体启动")
        
        # 启动更新任务
        asyncio.ensure_future(self._update_loop())

    async def stop(self):
        """
        停止智能体
        """
        if not self._running:
            return
        
        self._running = False
        logger.info("账户同步智能体停止")

    async def _update_loop(self):
        """
        定期更新账户信息和订单信息
        """
        while self._running:
            try:
                # 更新账户信息
                await self._update_account_info()
                
                # 更新订单信息
                await self._update_orders_info()
                
                # 订单校对
                await self._check_orders()
                
                # 等待下一次更新
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"账户同步更新失败: {e}")
                # 出错后等待一段时间再重试
                await asyncio.sleep(10)

    async def _update_account_info(self):
        """
        更新账户信息
        """
        try:
            # 获取账户余额
            balance = await self.rest_client.get_account_balance()
            if balance:
                # 保存账户信息
                self.account_info = balance
                
                # 发布账户更新事件
                await self.event_bus.publish_async(
                    Event(
                        type=EventType.ACCOUNT_UPDATE,
                        source=self.name,
                        data={
                            "account_info": balance,
                            "timestamp": asyncio.get_event_loop().time()
                        }
                    )
                )
                
                logger.debug("账户信息更新成功")
            
            # 获取持仓信息
            positions = await self.rest_client.get_positions()
            if positions:
                # 保存持仓信息
                self.positions_info = positions
                
                # 提取风险状态信息
                risk_info = []
                for position in positions:
                    risk_item = {
                        "instId": position.get("instId"),
                        "pos": position.get("pos"),
                        "mgnRatio": position.get("mgnRatio"),
                        "mmr": position.get("mmr"),
                        "liqPx": position.get("liqPx"),
                        "lever": position.get("lever"),
                        "mgnMode": position.get("mgnMode")
                    }
                    risk_info.append(risk_item)
                
                # 保存风险状态信息
                self.risk_info = risk_info
                
                # 发布持仓更新事件
                await self.event_bus.publish_async(
                    Event(
                        type=EventType.POSITIONS_UPDATE,
                        source=self.name,
                        data={
                            "positions": positions,
                            "risk_info": risk_info,
                            "timestamp": asyncio.get_event_loop().time()
                        }
                    )
                )
                
                logger.debug("持仓信息更新成功")
            
            # 获取历史持仓信息
            positions_history = await self.rest_client.get_positions_history()
            if positions_history:
                # 保存历史持仓信息
                self.positions_history_info = positions_history
                
                # 发布历史持仓更新事件
                await self.event_bus.publish_async(
                    Event(
                        type=EventType.POSITIONS_UPDATE,
                        source=self.name,
                        data={
                            "positions_history": positions_history,
                            "timestamp": asyncio.get_event_loop().time()
                        }
                    )
                )
                
                logger.debug("历史持仓信息更新成功")
            
            # 获取账户账单详情
            bills = await self.rest_client.get_account_bills()
            if bills:
                # 保存账单信息
                self.bills_info = bills
                
                # 发布账单更新事件
                await self.event_bus.publish_async(
                    Event(
                        type=EventType.ACCOUNT_UPDATE,
                        source=self.name,
                        data={
                            "bills_info": bills,
                            "timestamp": asyncio.get_event_loop().time()
                        }
                    )
                )
                
                logger.debug("账户账单信息更新成功")
            
            # 获取近三个月内账户账单详情
            bills_archive = await self.rest_client.get_account_bills_archive()
            if bills_archive:
                # 保存近三个月账单信息
                self.bills_archive_info = bills_archive
                
                # 发布近三个月账单更新事件
                await self.event_bus.publish_async(
                    Event(
                        type=EventType.ACCOUNT_UPDATE,
                        source=self.name,
                        data={
                            "bills_archive_info": bills_archive,
                            "timestamp": asyncio.get_event_loop().time()
                        }
                    )
                )
                
                logger.debug("近三个月账户账单信息更新成功")
            
            # 获取账单类型
            bill_types = await self.rest_client.get_bill_types()
            if bill_types:
                # 保存账单类型信息
                self.bill_types_info = bill_types
                
                # 发布账单类型更新事件
                await self.event_bus.publish_async(
                    Event(
                        type=EventType.ACCOUNT_UPDATE,
                        source=self.name,
                        data={
                            "bill_types_info": bill_types,
                            "timestamp": asyncio.get_event_loop().time()
                        }
                    )
                )
                
                logger.debug("账单类型信息更新成功")
            
            # 获取账户配置
            account_config = await self.rest_client.get_account_config()
            if account_config:
                # 保存账户配置信息
                self.account_config_info = account_config
                
                # 发布账户配置更新事件
                await self.event_bus.publish_async(
                    Event(
                        type=EventType.ACCOUNT_UPDATE,
                        source=self.name,
                        data={
                            "account_config_info": account_config,
                            "timestamp": asyncio.get_event_loop().time()
                        }
                    )
                )
                
                logger.debug("账户配置信息更新成功")
            
            # 获取计息记录
            interest_accrued = await self.rest_client.get_interest_accrued()
            if interest_accrued:
                # 保存计息记录信息
                self.interest_accrued_info = interest_accrued
                
                # 发布计息记录更新事件
                await self.event_bus.publish_async(
                    Event(
                        type=EventType.ACCOUNT_UPDATE,
                        source=self.name,
                        data={
                            "interest_accrued_info": interest_accrued,
                            "timestamp": asyncio.get_event_loop().time()
                        }
                    )
                )
                
                logger.debug("计息记录信息更新成功")
            
            # 获取借币利率
            interest_rate = await self.rest_client.get_interest_rate()
            if interest_rate:
                # 保存借币利率信息
                self.interest_rate_info = interest_rate
                
                # 发布借币利率更新事件
                await self.event_bus.publish_async(
                    Event(
                        type=EventType.ACCOUNT_UPDATE,
                        source=self.name,
                        data={
                            "interest_rate_info": interest_rate,
                            "timestamp": asyncio.get_event_loop().time()
                        }
                    )
                )
                
                logger.debug("借币利率信息更新成功")
                
        except Exception as e:
            logger.error(f"更新账户信息失败: {e}")

    async def _update_orders_info(self):
        """
        更新订单信息
        """
        try:
            # 获取现货未成交订单
            spot_pending_orders = await self.rest_client.get_pending_orders(inst_type="SPOT")
            # 获取杠杆未成交订单
            margin_pending_orders = await self.rest_client.get_pending_orders(inst_type="MARGIN")
            
            # 合并未成交订单
            pending_orders = []
            if spot_pending_orders:
                pending_orders.extend(spot_pending_orders)
            if margin_pending_orders:
                pending_orders.extend(margin_pending_orders)
            
            if pending_orders:
                self.pending_orders = pending_orders
                
                # 发布未成交订单更新事件
                await self.event_bus.publish_async(
                    Event(
                        type=EventType.PENDING_ORDERS_UPDATE,
                        source=self.name,
                        data={
                            "pending_orders": pending_orders,
                            "timestamp": asyncio.get_event_loop().time()
                        }
                    )
                )
            
            # 获取现货历史订单
            spot_history_orders = await self.rest_client.get_order_history(inst_type="SPOT", limit=20)
            # 获取杠杆历史订单
            margin_history_orders = await self.rest_client.get_order_history(inst_type="MARGIN", limit=20)
            
            # 合并历史订单
            history_orders = []
            if spot_history_orders:
                history_orders.extend(spot_history_orders)
            if margin_history_orders:
                history_orders.extend(margin_history_orders)
            
            if history_orders:
                self.history_orders = history_orders
                
                # 发布历史订单更新事件
                await self.event_bus.publish_async(
                    Event(
                        type=EventType.HISTORY_ORDERS_UPDATE,
                        source=self.name,
                        data={
                            "history_orders": history_orders,
                            "timestamp": asyncio.get_event_loop().time()
                        }
                    )
                )
            
            logger.debug("订单信息更新成功")
            
        except Exception as e:
            logger.error(f"更新订单信息失败: {e}")

    async def _check_orders(self):
        """
        订单校对
        """
        try:
            # 检查未成交订单
            if self.pending_orders:
                for order in self.pending_orders:
                    order_id = order.get('ordId')
                    if order_id:
                        # 检查订单状态
                        if order_id not in self.local_orders:
                            # 新订单
                            self.local_orders[order_id] = order
                            await self.event_bus.publish_async(
                                Event(
                                    type=EventType.ORDER_NEW,
                                    source=self.name,
                                    data={"order": order}
                                )
                            )
                        else:
                            # 检查订单状态变化
                            local_order = self.local_orders[order_id]
                            if local_order.get('state') != order.get('state'):
                                # 订单状态变化
                                self.local_orders[order_id] = order
                                await self.event_bus.publish_async(
                                    Event(
                                        type=EventType.ORDER_UPDATE,
                                        source=self.name,
                                        data={"order": order}
                                    )
                                )
            
            # 检查历史订单
            if self.history_orders:
                for order in self.history_orders:
                    order_id = order.get('ordId')
                    if order_id and order_id in self.local_orders:
                        # 订单已完成
                        if self.local_orders[order_id].get('state') != order.get('state'):
                            self.local_orders[order_id] = order
                            await self.event_bus.publish_async(
                                Event(
                                    type=EventType.ORDER_FILLED,
                                    source=self.name,
                                    data={"order": order}
                                )
                            )
            
        except Exception as e:
            logger.error(f"订单校对失败: {e}")

    async def get_account_info(self) -> Optional[Dict]:
        """
        获取账户信息
        
        Returns:
            Optional[Dict]: 账户信息
        """
        return self.account_info

    async def get_pending_orders(self) -> Optional[List[Dict]]:
        """
        获取未成交订单
        
        Returns:
            Optional[List[Dict]]: 未成交订单列表
        """
        return self.pending_orders

    async def get_history_orders(self) -> Optional[List[Dict]]:
        """
        获取历史订单
        
        Returns:
            Optional[List[Dict]]: 历史订单列表
        """
        return self.history_orders

    async def set_position_mode(self, pos_mode: str) -> Dict:
        """
        设置持仓模式
        
        Args:
            pos_mode: 持仓模式 (long_short_mode 或 net_mode)
        
        Returns:
            Dict: 设置结果
        """
        result = await self.rest_client.set_position_mode(pos_mode)
        return result

    async def set_leverage(self, inst_id: str, lever: str, mgn_mode: str) -> Optional[Dict]:
        """
        设置杠杆倍数
        
        Args:
            inst_id: 产品ID
            lever: 杠杆倍数
            mgn_mode: 保证金模式 (cross/isolated)
        
        Returns:
            Optional[Dict]: 设置结果
        """
        result = await self.rest_client.set_leverage(inst_id, lever, mgn_mode)
        return result

    async def get_max_order_size(self, inst_id: str, td_mode: str) -> List[Dict]:
        """
        获取最大可买卖/开仓数量
        
        Args:
            inst_id: 产品ID
            td_mode: 交易模式 (isolated/cross)
        
        Returns:
            List[Dict]: 最大订单大小信息
        """
        result = await self.rest_client.get_max_order_size(inst_id, td_mode)
        return result

    async def get_max_avail_size(self, inst_id: str, td_mode: str) -> List[Dict]:
        """
        获取最大可用数量
        
        Args:
            inst_id: 产品ID
            td_mode: 交易模式 (cash/isolated/cross)
        
        Returns:
            List[Dict]: 最大可用数量信息
        """
        result = await self.rest_client.get_max_avail_size(inst_id, td_mode)
        return result

    async def adjustment_margin(self, inst_id: str, pos_side: str, margin_type: str, amt: str) -> Dict:
        """
        调整保证金
        
        Args:
            inst_id: 产品ID
            pos_side: 持仓方向 (long/short)
            margin_type: 调整类型 (add/reduce)
            amt: 调整金额
        
        Returns:
            Dict: 调整结果
        """
        result = await self.rest_client.adjustment_margin(inst_id, pos_side, margin_type, amt)
        return result

    async def get_leverage(self, inst_id: str, mgn_mode: str) -> List[Dict]:
        """
        获取杠杆倍数
        
        Args:
            inst_id: 产品ID
            mgn_mode: 保证金模式 (cross/isolated)
        
        Returns:
            List[Dict]: 杠杆倍数信息
        """
        result = await self.rest_client.get_leverage(inst_id, mgn_mode)
        return result

    async def get_max_loan(self, inst_id: str, mgn_mode: str, mgn_ccy: str) -> List[Dict]:
        """
        获取币币杠杆最大可借数量
        
        Args:
            inst_id: 产品ID
            mgn_mode: 保证金模式 (cross/isolated)
            mgn_ccy: 保证金币种
        
        Returns:
            List[Dict]: 最大可借数量信息
        """
        result = await self.rest_client.get_max_loan(inst_id, mgn_mode, mgn_ccy)
        return result

    async def get_fee_rates(self, inst_type: str, inst_id: str) -> List[Dict]:
        """
        获取当前账户交易手续费费率
        
        Args:
            inst_type: 产品类型 (SPOT/SWAP/FUTURES/OPTIONS)
            inst_id: 产品ID
        
        Returns:
            List[Dict]: 手续费费率信息
        """
        result = await self.rest_client.get_fee_rates(inst_type, inst_id)
        return result

    async def get_interest_accrued(self, ccy: str = "", after: str = "", before: str = "", limit: int = 100) -> List[Dict]:
        """
        获取计息记录
        
        Args:
            ccy: 币种
            after: 开始时间戳
            before: 结束时间戳
            limit: 数量限制
        
        Returns:
            List[Dict]: 计息记录列表
        """
        result = await self.rest_client.get_interest_accrued(ccy, after, before, limit)
        return result

    async def get_interest_rate(self, ccy: str = "") -> List[Dict]:
        """
        获取用户当前市场借币利率
        
        Args:
            ccy: 币种
        
        Returns:
            List[Dict]: 借币利率列表
        """
        result = await self.rest_client.get_interest_rate(ccy)
        return result

    async def set_greeks(self, greeks_type: str) -> Dict:
        """
        期权greeks的PA/BS切换
        
        Args:
            greeks_type: greeks类型 (PA/BS)
        
        Returns:
            Dict: 设置结果
        """
        result = await self.rest_client.set_greeks(greeks_type)
        return result

    async def set_isolated_mode(self, iso_mode: str, mode_type: str) -> Dict:
        """
        逐仓交易设置
        
        Args:
            iso_mode: 逐仓模式 (automatic)
            mode_type: 交易类型 (MARGIN)
        
        Returns:
            Dict: 设置结果
        """
        result = await self.rest_client.set_isolated_mode(iso_mode, mode_type)
        return result

    async def get_account_position_risk(self, inst_type: str = "", inst_id: str = "") -> List[Dict]:
        """
        查看账户持仓风险（仅适用于PM账户）
        
        Args:
            inst_type: 产品类型
            inst_id: 产品ID
        
        Returns:
            List[Dict]: 持仓风险列表
        """
        result = await self.rest_client.get_account_position_risk(inst_type, inst_id)
        return result

    async def get_interest_limits(self, ccy: str) -> List[Dict]:
        """
        获取借币利率与限额
        
        Args:
            ccy: 币种
        
        Returns:
            List[Dict]: 借币利率与限额列表
        """
        result = await self.rest_client.get_interest_limits(ccy)
        return result

    async def spot_manual_borrow_repay(self, ccy: str, side: str, amt: str) -> Dict:
        """
        现货手动借币/还币（仅适用于现货模式已开通借币的情况）
        
        Args:
            ccy: 币种
            side: 操作方向 (borrow/repay)
            amt: 金额
        
        Returns:
            Dict: 操作结果
        """
        result = await self.rest_client.spot_manual_borrow_repay(ccy, side, amt)
        return result

    async def set_auto_repay(self, auto_repay: bool) -> Dict:
        """
        设置自动还币（仅适用于现货模式已开通借币的情况）
        
        Args:
            auto_repay: 是否开启自动还币 (true/false)
        
        Returns:
            Dict: 设置结果
        """
        result = await self.rest_client.set_auto_repay(auto_repay)
        return result

    async def spot_borrow_repay_history(self, ccy: str = "", type: str = "", after: str = "", before: str = "", limit: int = 100) -> List[Dict]:
        """
        获取现货模式下的借/还币历史
        
        Args:
            ccy: 币种
            type: 类型 (auto_borrow/auto_repay/manual_borrow/manual_repay)
            after: 开始时间戳
            before: 结束时间戳
            limit: 数量限制
        
        Returns:
            List[Dict]: 借/还币历史列表
        """
        result = await self.rest_client.spot_borrow_repay_history(ccy, type, after, before, limit)
        return result

    async def position_builder(self, incl_real_pos_and_eq: bool, sim_pos: List[Dict]) -> Dict:
        """
        构建模拟持仓
        
        Args:
            incl_real_pos_and_eq: 是否包含真实持仓和权益
            sim_pos: 模拟持仓列表
        
        Returns:
            Dict: 构建结果
        """
        result = await self.rest_client.position_builder(incl_real_pos_and_eq, sim_pos)
        return result

    async def get_position_builder_graph(self, incl_real_pos_and_eq: bool, sim_pos: List[Dict]) -> Dict:
        """
        获取持仓构建器图表数据
        
        Args:
            incl_real_pos_and_eq: 是否包含真实持仓和权益
            sim_pos: 模拟持仓列表
        
        Returns:
            Dict: 图表数据
        """
        result = await self.rest_client.get_position_builder_graph(incl_real_pos_and_eq, sim_pos)
        return result

    async def set_risk_offset_amt(self, ccy: str, amt: str, type: str) -> Dict:
        """
        设置风险偏移量
        
        Args:
            ccy: 币种
            amt: 金额
            type: 类型 (add/reduce)
        
        Returns:
            Dict: 设置结果
        """
        result = await self.rest_client.set_risk_offset_amt(ccy, amt, type)
        return result

    async def get_greeks(self, inst_type: str = "", inst_id: str = "") -> List[Dict]:
        """
        获取期权greeks信息
        
        Args:
            inst_type: 产品类型
            inst_id: 产品ID
        
        Returns:
            List[Dict]: greeks信息列表
        """
        result = await self.rest_client.get_greeks(inst_type, inst_id)
        return result

    async def get_position_tiers(self, inst_type: str, inst_id: str, td_mode: str) -> List[Dict]:
        """
        获取持仓档位信息
        
        Args:
            inst_type: 产品类型
            inst_id: 产品ID
            td_mode: 交易模式 (isolated/cross)
        
        Returns:
            List[Dict]: 持仓档位信息列表
        """
        result = await self.rest_client.get_position_tiers(inst_type, inst_id, td_mode)
        return result

    async def activate_option(self) -> Dict:
        """
        激活期权功能
        
        Returns:
            Dict: 激活结果
        """
        result = await self.rest_client.activate_option()
        return result

    async def set_auto_loan(self, auto_loan: bool) -> Dict:
        """
        设置自动借币
        
        Args:
            auto_loan: 是否开启自动借币 (true/false)
        
        Returns:
            Dict: 设置结果
        """
        result = await self.rest_client.set_auto_loan(auto_loan)
        return result

    async def account_level_switch_preset(self, level: str) -> Dict:
        """
        账户等级切换预设
        
        Args:
            level: 账户等级
        
        Returns:
            Dict: 切换结果
        """
        result = await self.rest_client.account_level_switch_preset(level)
        return result

    async def set_account_level(self, level: str) -> Dict:
        """
        设置账户等级
        
        Args:
            level: 账户等级
        
        Returns:
            Dict: 设置结果
        """
        result = await self.rest_client.set_account_level(level)
        return result

    async def set_collateral_assets(self, collateral_assets: List[Dict]) -> Dict:
        """
        设置抵押资产
        
        Args:
            collateral_assets: 抵押资产列表
        
        Returns:
            Dict: 设置结果
        """
        result = await self.rest_client.set_collateral_assets(collateral_assets)
        return result

    async def get_collateral_assets(self) -> List[Dict]:
        """
        获取抵押资产信息
        
        Returns:
            List[Dict]: 抵押资产列表
        """
        result = await self.rest_client.get_collateral_assets()
        return result

    async def mmp_reset(self) -> Dict:
        """
        重置MMP（Market Maker Protection）设置
        
        Returns:
            Dict: 重置结果
        """
        result = await self.rest_client.mmp_reset()
        return result

    async def mmp_config(self, mmp_config: Dict) -> Dict:
        """
        配置MMP（Market Maker Protection）设置
        
        Args:
            mmp_config: MMP配置信息
        
        Returns:
            Dict: 配置结果
        """
        result = await self.rest_client.mmp_config(mmp_config)
        return result

    async def get_mmp_config(self) -> List[Dict]:
        """
        获取MMP（Market Maker Protection）配置信息
        
        Returns:
            List[Dict]: MMP配置信息列表
        """
        result = await self.rest_client.get_mmp_config()
        return result

    async def move_positions(self, move_positions: List[Dict]) -> Dict:
        """
        移动持仓
        
        Args:
            move_positions: 移动持仓列表
        
        Returns:
            Dict: 移动结果
        """
        result = await self.rest_client.move_positions(move_positions)
        return result

    async def get_move_positions_history(self, after: str = "", before: str = "", limit: int = 100) -> List[Dict]:
        """
        获取移动持仓历史
        
        Args:
            after: 开始时间戳
            before: 结束时间戳
            limit: 数量限制
        
        Returns:
            List[Dict]: 移动持仓历史列表
        """
        result = await self.rest_client.get_move_positions_history(after, before, limit)
        return result

    async def set_auto_earn(self, auto_earn: bool) -> Dict:
        """
        设置自动收益
        
        Args:
            auto_earn: 是否开启自动收益 (true/false)
        
        Returns:
            Dict: 设置结果
        """
        result = await self.rest_client.set_auto_earn(auto_earn)
        return result

    async def set_settle_currency(self, settle_currency: str) -> Dict:
        """
        设置结算货币
        
        Args:
            settle_currency: 结算货币
        
        Returns:
            Dict: 设置结果
        """
        result = await self.rest_client.set_settle_currency(settle_currency)
        return result

    async def set_trading_config(self, trading_config: Dict) -> Dict:
        """
        设置交易配置
        
        Args:
            trading_config: 交易配置信息
        
        Returns:
            Dict: 设置结果
        """
        result = await self.rest_client.set_trading_config(trading_config)
        return result

    async def precheck_set_delta_neutral(self, inst_id: str, delta: str) -> Dict:
        """
        预检查设置delta中性
        
        Args:
            inst_id: 产品ID
            delta: delta值
        
        Returns:
            Dict: 预检查结果
        """
        result = await self.rest_client.precheck_set_delta_neutral(inst_id, delta)
        return result

    async def order(self, order: Dict) -> Dict:
        """
        下单
        
        Args:
            order: 订单信息，包含instId, side, ordType, sz等字段
        
        Returns:
            Dict: 下单结果
        """
        result = await self.rest_client.order(order)
        return result

    async def batch_orders(self, orders: List[Dict]) -> List[Dict]:
        """
        批量下单
        
        Args:
            orders: 订单列表，每个订单包含instId, side, ordType, sz等字段
        
        Returns:
            List[Dict]: 批量下单结果
        """
        result = await self.rest_client.batch_orders(orders)
        return result

    async def cancel_order(self, order: Dict) -> Dict:
        """
        取消订单
        
        Args:
            order: 订单取消信息，包含ordId和instId等字段
        
        Returns:
            Dict: 取消订单结果
        """
        result = await self.rest_client.cancel_order(order)
        return result

    async def amend_order(self, order: Dict) -> Dict:
        """
        修改订单
        
        Args:
            order: 订单修改信息，包含ordId, newSz, instId等字段
        
        Returns:
            Dict: 修改订单结果
        """
        result = await self.rest_client.amend_order(order)
        return result

    async def amend_batch_orders(self, orders: List[Dict]) -> List[Dict]:
        """
        批量修改订单
        
        Args:
            orders: 订单修改列表，每个订单包含ordId, newSz, instId等字段
        
        Returns:
            List[Dict]: 批量修改订单结果
        """
        result = await self.rest_client.amend_batch_orders(orders)
        return result

    async def close_position(self, position: Dict) -> Dict:
        """
        平仓
        
        Args:
            position: 平仓信息，包含instId, mgnMode等字段
        
        Returns:
            Dict: 平仓结果
        """
        result = await self.rest_client.close_position(position)
        return result

    async def get_order(self, ord_id: str, inst_id: str) -> Dict:
        """
        获取订单信息
        
        Args:
            ord_id: 订单ID
            inst_id: 产品ID
        
        Returns:
            Dict: 订单信息
        """
        result = await self.rest_client.get_order(ord_id, inst_id)
        return result

    async def get_orders_pending(self, ord_type: str = "", inst_type: str = "") -> List[Dict]:
        """
        获取特定类型的挂单
        
        Args:
            ord_type: 订单类型，多个类型用逗号分隔，如 "post_only,fok,ioc"
            inst_type: 产品类型，如 "SPOT"
        
        Returns:
            List[Dict]: 挂单列表
        """
        result = await self.rest_client.get_orders_pending(ord_type, inst_type)
        return result

    async def get_orders_history(self, ord_type: str = "", inst_type: str = "") -> List[Dict]:
        """
        获取特定类型的历史订单
        
        Args:
            ord_type: 订单类型，多个类型用逗号分隔，如 "post_only,fok,ioc"
            inst_type: 产品类型，如 "SPOT"
        
        Returns:
            List[Dict]: 历史订单列表
        """
        result = await self.rest_client.get_orders_history(ord_type, inst_type)
        return result

    async def get_orders_history_archive(self, ord_type: str = "", inst_type: str = "") -> List[Dict]:
        """
        获取特定类型的历史订单归档
        
        Args:
            ord_type: 订单类型，多个类型用逗号分隔，如 "post_only,fok,ioc"
            inst_type: 产品类型，如 "SPOT"
        
        Returns:
            List[Dict]: 历史订单归档列表
        """
        result = await self.rest_client.get_orders_history_archive(ord_type, inst_type)
        return result

    async def get_fills(self, inst_id: str = "", ord_id: str = "") -> List[Dict]:
        """
        获取成交明细
        
        Args:
            inst_id: 产品ID
            ord_id: 订单ID
        
        Returns:
            List[Dict]: 成交明细列表
        """
        result = await self.rest_client.get_fills(inst_id, ord_id)
        return result

    async def get_fills_history(self, inst_type: str = "", inst_id: str = "") -> List[Dict]:
        """
        获取历史成交明细
        
        Args:
            inst_type: 产品类型，如 "SPOT"
            inst_id: 产品ID
        
        Returns:
            List[Dict]: 历史成交明细列表
        """
        result = await self.rest_client.get_fills_history(inst_type, inst_id)
        return result

    def get_status(self) -> Dict[str, Any]:
        """
        获取智能体状态
        
        Returns:
            Dict[str, Any]: 状态信息
        """
        return {
            "name": self.name,
            "running": self._running,
            "update_interval": self.update_interval,
            "last_update_time": self.last_update_time,
            "account_info": self.account_info is not None,
            "positions_info": self.positions_info is not None,
            "positions_history_info": self.positions_history_info is not None,
            "risk_info": self.risk_info is not None,
            "bills_info": self.bills_info is not None,
            "bills_archive_info": self.bills_archive_info is not None,
            "bill_types_info": self.bill_types_info is not None,
            "account_config_info": self.account_config_info is not None,
            "interest_accrued_info": self.interest_accrued_info is not None,
            "interest_rate_info": self.interest_rate_info is not None,
            "greeks_info": self.greeks_info is not None,
            "pending_orders_count": len(self.pending_orders) if self.pending_orders else 0,
            "history_orders_count": len(self.history_orders) if self.history_orders else 0,
            "local_orders_count": len(self.local_orders)
        }

    async def _handle_account_update(self, event: Event):
        """
        处理来自WebSocket的账户更新事件
        
        Args:
            event: 账户更新事件
        """
        try:
            data = event.data
            channel = data.get("channel", "")
            update_data = data.get("data", [])
            
            if update_data:
                # 检查是否是balance_and_position频道的数据
                if channel == "balance_and_position":
                    # balance_and_position频道同时包含账户和持仓信息
                    for item in update_data:
                        # 处理余额数据
                        bal_data = item.get("balData", [])
                        if bal_data:
                            # 构建账户信息
                            self.account_info = {
                                "details": bal_data,
                                "uTime": item.get("pTime", "")
                            }
                            logger.info(f"收到WebSocket账户余额更新: 共{len(bal_data)}个币种")
                        
                        # 处理持仓数据
                        pos_data = item.get("posData", [])
                        if pos_data:
                            self.positions_info = pos_data
                            position_count = len(self.positions_info)
                            logger.info(f"收到WebSocket持仓更新: 共{position_count}个持仓")
                        
                        # 处理交易数据
                        trades_data = item.get("trades", [])
                        if trades_data:
                            # 可以在这里处理交易数据
                            trade_count = len(trades_data)
                            logger.info(f"收到WebSocket交易更新: 共{trade_count}笔交易")
                elif channel == "account-greeks":
                    # 处理账户greeks信息
                    self.greeks_info = update_data
                    greeks_count = len(update_data)
                    logger.info(f"收到WebSocket账户Greeks更新: 共{greeks_count}个产品")
                else:
                    # 普通的account频道数据
                    self.account_info = update_data[0]
                    logger.info(f"收到WebSocket账户更新: 总权益={self.account_info.get('totalEq', 'N/A')} USDT")
                
                # 更新时间戳
                self.last_update_time = asyncio.get_event_loop().time()
                
                # 可以在这里添加更多的处理逻辑，比如：
                # 1. 检查账户余额变化
                # 2. 检查可用资金变化
                # 3. 检查持仓变化
                # 4. 触发相关的风险评估
                
        except Exception as e:
            logger.error(f"处理账户更新事件错误: {e}")

    async def _handle_positions_update(self, event: Event):
        """
        处理来自WebSocket的持仓更新事件
        
        Args:
            event: 持仓更新事件
        """
        try:
            data = event.data
            positions_data = data.get("data", [])
            
            if positions_data:
                # 更新持仓信息
                self.positions_info = positions_data
                self.last_update_time = asyncio.get_event_loop().time()
                
                # 记录持仓更新日志
                position_count = len(positions_data)
                logger.info(f"收到WebSocket持仓更新: 共{position_count}个持仓")
                
                # 可以在这里添加更多的处理逻辑，比如：
                # 1. 检查持仓变化
                # 2. 检查保证金水平
                # 3. 触发相关的风险评估
                # 4. 检查是否需要平仓
                
        except Exception as e:
            logger.error(f"处理持仓更新事件错误: {e}")

    async def _handle_liquidation_warning(self, event: Event):
        """
        处理来自WebSocket的强平预警事件
        
        Args:
            event: 强平预警事件
        """
        try:
            data = event.data
            warning_data = data.get("data", [])
            
            if warning_data:
                # 记录强平预警日志
                warning_count = len(warning_data)
                logger.warning(f"收到强平预警: 共{warning_count}个持仓面临强平风险")
                
                # 处理每个强平预警
                for warning in warning_data:
                    inst_id = warning.get("instId", "Unknown")
                    pos_side = warning.get("posSide", "Unknown")
                    mgn_ratio = warning.get("mgnRatio", "Unknown")
                    liq_px = warning.get("liqPx", "Unknown")
                    
                    logger.warning(f"强平预警: 产品={inst_id}, 方向={pos_side}, 保证金率={mgn_ratio}, 强平价格={liq_px}")
                
                # 可以在这里添加更多的处理逻辑，比如：
                # 1. 发送强平预警通知
                # 2. 触发自动平仓策略
                # 3. 调整保证金水平
                # 4. 暂停新的开仓操作
                
        except Exception as e:
            logger.error(f"处理强平预警事件错误: {e}")

    async def _cleanup(self):
        """
        清理资源
        """
        logger.info("账户同步智能体清理中")
        # 清理资源，例如关闭连接等
        pass

    async def _execute_cycle(self):
        """
        执行周期
        """
        # 由于我们已经在_update_loop中实现了定期更新逻辑，这里可以留空
        # 主循环会定期调用此方法，但我们的更新逻辑在单独的任务中运行
        await asyncio.sleep(1)
