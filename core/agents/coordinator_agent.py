"""
协调智能体 - 负责智能体间协调
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from decimal import Decimal

from .base_agent import BaseAgent, AgentConfig, AgentStatus
from core.events.event_bus import Event, EventType
from core.events.agent_communication import Message, MessageType, MessageTemplates
from core.utils.persistence import persistence_manager
from core.utils.profit_growth_manager import profit_growth_manager

logger = logging.getLogger(__name__)


class CoordinatorAgent(BaseAgent):
    """
    协调智能体

    职责：
    1. 管理所有智能体的生命周期
    2. 协调智能体间的通信
    3. 监控系统健康状态
    4. 处理系统级决策
    """

    def __init__(self, config: AgentConfig):
        super().__init__(config)

        # 管理的智能体
        self._agents: Dict[str, BaseAgent] = {}

        # 系统状态
        self._system_health = "healthy"  # healthy/degraded/unhealthy
        self._system_stats = {
            "start_time": datetime.now(),
            "total_messages": 0,
            "total_errors": 0,
        }

        # 决策配置
        self._auto_recovery = True
        self._emergency_stop_threshold = 5  # 连续错误阈值

        # 交易金额跟踪
        self._total_trade_amount = 0.0  # 总交易金额（USDT）
        self._max_trade_amount = 100.0  # 最大交易金额限制（USDT）
        
        # 风险收益指数
        self._risk_return_index = 100.0  # 风险收益指数，初始为100%
        self._last_signal_side = None  # 上次信号方向
        self._processed_signals = None  # 已处理的信号
        
        # 梯度交易相关
        self._buy_order_count = 0  # 买入订单计数
        self._current_gradient = 1  # 当前梯度
        self._last_buy_price = 0  # 上次买入价格
        
        # 当日振幅相关
        self._daily_amplitude = 0.0  # 当日振幅
        self._last_gradient_update_date = None  # 上次梯度更新日期
        
        # 最早币种数量增长率相关
        self._first_growth_rate = None  # 最早的币种数量增长率
        self._first_size = None  # 最早的币种数量
        
        # 多空指数相关 - 0%为中立，正值为多，负值为空
        self._risk_return_index = 0.0  # 多空指数，初始为0%
        
        # 冷静期相关
        self._cooldown_period = 0  # 冷静期时长（秒）
        self._cooldown_start_time = None  # 冷静期开始时间
        self._cooldown_level = 0  # 冷静期叠加级别
        self._cooldown_type = None  # 冷静期类型: "buy"(买入冷静期) 或 "sell"(卖出冷静期)

        # 最近处理的信号记录（用于去重）
        self._recent_signals: Dict[str, float] = {}  # 信号键 -> 处理时间
        
        # 保存策略信号和预期收益
        self._strategy_signals: Dict[str, Dict] = {}  # 信号ID -> 信号信息
        
        # 买入订单跟踪 - 用于跟踪所有买入订单并计算盈亏
        self._buy_orders: Dict[str, List[Dict]] = {}  # 未平仓的买入订单，按交易对分组
        self._total_pnl: float = 0.0  # 总盈亏
        self._total_trades: int = 0  # 总交易次数
        self._winning_trades: int = 0  # 盈利交易次数
        
        # 保证金跟踪 - 每种交易对最大使用10 USDT（初始值，随收益动态调整）
        self._initial_margin_per_symbol: float = 10.0  # 初始保证金限制
        self._symbol_profit: Dict[str, float] = {}  # 每个交易对的累计收益
        self._used_margin: Dict[str, Dict[str, float]] = {}  # 已使用的保证金，按交易对和方向分组
        # 结构: {inst_id: {'long': x.xx, 'short': x.xx}}
        
        # 杠杆倍数
        self._leverage: int = 2  # 默认2倍杠杆

        # 通信缓存
        self._communication_cache = {}  # 缓存智能体间通信结果
        self._cache_ttl = 5  # 缓存过期时间（秒）
        
        # 通信统计
        self._communication_stats = {
            'total_calls': 0,
            'cached_calls': 0,
            'failed_calls': 0,
            'avg_response_time': 0,
            'total_response_time': 0,
        }

        # 加载上次的状态
        self._load_state()

        logger.info(f"协调智能体初始化完成: {self.agent_id}")

    async def _initialize(self):
        """初始化"""
        # 订阅系统事件
        self.event_bus.subscribe(
            EventType.AGENT_REGISTERED, self._on_agent_registered, async_callback=True
        )
        self.event_bus.subscribe(
            EventType.AGENT_UNREGISTERED,
            self._on_agent_unregistered,
            async_callback=True,
        )
        self.event_bus.subscribe(
            EventType.SYSTEM_ERROR, self._on_system_error, async_callback=True
        )
        self.event_bus.subscribe(
            EventType.STRATEGY_SIGNAL, self._on_strategy_signal, async_callback=True
        )
        self.event_bus.subscribe(
            EventType.RISK_ALERT, self._on_risk_alert, async_callback=True
        )
        self.event_bus.subscribe(
            EventType.MARKET_PREDICTION, self._on_market_prediction, async_callback=True
        )

        # 启动定期账户和订单同步任务
        import asyncio
        asyncio.ensure_future(self._regular_sync_task())

        logger.info("协调智能体初始化完成")

    async def _cleanup(self):
        """清理"""
        # 保存当前状态
        self._save_state()
        # 停止所有管理的智能体
        for agent_id, agent in list(self._agents.items()):
            await agent.stop()

        self._agents.clear()
        logger.info("协调智能体已清理")
    
    def save_state_now(self):
        """立即保存状态"""
        self._save_state()
    
    async def _regular_sync_task(self):
        """定期同步账户和订单状态
        
        确保账户状态和订单状态保持同步，避免数据不一致
        """
        # 创建日志清理任务
        import asyncio
        asyncio.ensure_future(self._regular_log_cleanup_task())
        
        while True:
            try:
                logger.info("🔄 执行定期账户和订单同步...")
                
                # 获取订单智能体
                order_agent = None
                for agent_id, agent in self._agents.items():
                    if agent.name == "Order":
                        order_agent = agent
                        break
                
                # 执行同步
                if order_agent and hasattr(order_agent, "sync_account_and_orders"):
                    result = await order_agent.sync_account_and_orders()
                    if result and result.get('success'):
                        logger.info("✅ 定期同步完成")
                    else:
                        logger.warning(f"⚠️ 定期同步失败: {result.get('error', '未知错误')}")
                else:
                    logger.warning("⚠️ 订单智能体不可用，跳过同步")
                
                # 等待一段时间后再次同步
                import asyncio
                await asyncio.sleep(300)  # 5分钟同步一次
                
            except Exception as e:
                logger.error(f"❌ 定期同步任务失败: {e}")
                import asyncio
                await asyncio.sleep(60)  # 出错后等待1分钟再重试

    async def _regular_log_cleanup_task(self):
        """定期清理日志任务
        
        每2小时检查一次日志大小，超过5GB自动清理
        """
        from core.utils.logger import logger_config
        import asyncio
        
        logger.info("📝 定期日志清理任务已启动")
        
        while True:
            try:
                logger.info("📝 检查并清理日志...")
                logger_config.clean_old_logs()
                logger.info("✅ 日志检查完成")
            except Exception as e:
                logger.error(f"❌ 日志清理任务失败: {e}")
            
            # 等待2小时后再次检查
            try:
                await asyncio.sleep(7200)  # 2小时
            except asyncio.CancelledError:
                logger.info("📝 定期日志清理任务已停止")
                break
            except Exception:
                await asyncio.sleep(3600)  # 出错后等待1小时
    
    def _load_state(self):
        """加载上次的状态"""
        try:
            state = persistence_manager.load_coordinator_agent_state()
            if state:
                # 加载交易金额跟踪
                self._total_trade_amount = state.get('total_trade_amount', 0.0)
                self._max_trade_amount = state.get('max_trade_amount', 100.0)
                
                # 加载最近处理的信号记录
                self._recent_signals = state.get('recent_signals', {})
                
                # 加载策略信号
                self._strategy_signals = state.get('strategy_signals', {})
                
                # 加载买入订单跟踪信息
                buy_orders_data = state.get('buy_orders', {})
                if isinstance(buy_orders_data, list):
                    # 修复格式问题：从数组转换为字典
                    self._buy_orders = {}
                    logger.warning("⚠️ 修复buy_orders格式: 从数组转换为字典")
                else:
                    self._buy_orders = buy_orders_data
                
                self._sell_orders = state.get('sell_orders', {})
                self._last_expected_returns = state.get('last_expected_returns', {})
                self._total_pnl = state.get('total_pnl', 0.0)
                self._total_trades = state.get('total_trades', 0)
                self._winning_trades = state.get('winning_trades', 0)
                self._symbol_profit = state.get('symbol_profit', {})
                
                logger.info(f"成功加载协调智能体状态: 总交易金额={self._total_trade_amount} USDT, 总盈亏={self._total_pnl:.2f} USDT")
            else:
                logger.info("未找到上次的协调智能体状态")
        except Exception as e:
            logger.error(f"加载协调智能体状态失败: {e}")
    
    def _save_state(self):
        """保存当前状态"""
        try:
            state = {
                'total_trade_amount': self._total_trade_amount,
                'max_trade_amount': self._max_trade_amount,
                'recent_signals': self._recent_signals,
                'strategy_signals': self._strategy_signals,
                'buy_orders': self._buy_orders,
                'last_expected_returns': self._last_expected_returns,
                'total_pnl': self._total_pnl,
                'total_trades': self._total_trades,
                'winning_trades': self._winning_trades,
                'symbol_profit': self._symbol_profit
            }
            success = persistence_manager.save_coordinator_agent_state(state)
            if success:
                logger.info(f"成功保存协调智能体状态: 总交易金额={self._total_trade_amount} USDT, 总盈亏={self._total_pnl:.2f} USDT")
            else:
                logger.error("保存协调智能体状态失败")
        except Exception as e:
            logger.error(f"保存协调智能体状态失败: {e}")

    async def _get_available_usdt_balance(self) -> float:
        """
        获取可用的USDT余额

        Returns:
            float: USDT可用余额
        """
        try:
            # 从order_agent获取账户余额信息
            # 通过遍历找到OrderAgent（因为agent_id是随机的）
            order_agent = None
            for agent_id, agent in self._agents.items():
                if agent.name == "Order":
                    order_agent = agent
                    break
            
            if order_agent and hasattr(order_agent, 'rest_client'):
                # 尝试获取余额
                balance = await order_agent.rest_client.get_account_balance()
                logger.debug(f"API返回的余额数据: {balance}")
                if balance and isinstance(balance, dict):
                    details = balance.get('details', [])
                    logger.debug(f"余额详情: {details}")
                    for item in details:
                        if isinstance(item, dict) and item.get('ccy') == 'USDT':
                            avail_bal_str = item.get('availBal', '0')
                            try:
                                avail_bal = float(avail_bal_str)
                                logger.info(f"✅ 从API获取到USDT可用余额: {avail_bal:.2f}")
                                return avail_bal
                            except (ValueError, TypeError) as e:
                                logger.warning(f"转换USDT余额失败: {avail_bal_str}, 错误: {e}")
                                pass
                    logger.warning(f"在余额详情中未找到USDT: {details}")
                else:
                    logger.warning(f"API返回的余额数据格式不正确: {balance}")
            else:
                logger.warning("未找到OrderAgent或rest_client未初始化")
        except Exception as e:
            logger.warning(f"从API获取USDT余额失败: {e}")

        # 所有数据必须以API返回为主，不使用本地文件作为凭证
        logger.warning("无法从API获取USDT余额，返回0")
        return 0.0

    async def _update_margin_tracking(self):
        """
        更新保证金使用情况
        计算当前所有未平仓订单占用的保证金（按交易对分组）
        """
        try:
            # 重置保证金统计
            self._used_margin = {}
            
            # 遍历所有未平仓订单计算保证金
            for inst_id, orders in self._buy_orders.items():
                # 初始化交易对的保证金记录
                if inst_id not in self._used_margin:
                    self._used_margin[inst_id] = {'long': 0.0, 'short': 0.0}
                
                for order in orders:
                    position_type = order.get('position_type', 'long')
                    if position_type == 'long':
                        # 做多订单：计算占用保证金（考虑杠杆倍数）
                        buy_amount = order.get('buy_amount', 0)
                        buy_price = order.get('buy_price', 0)
                        if buy_amount > 0 and buy_price > 0:
                            # 杠杆交易中，保证金 = （买入金额） / 杠杆倍数
                            margin = (buy_amount * buy_price) / self._leverage
                            self._used_margin[inst_id]['long'] += margin
                    elif position_type == 'short':
                        # 做空订单：计算占用保证金（考虑杠杆倍数）
                        sell_amount = order.get('sell_amount', 0)
                        sell_price = order.get('sell_price', 0)
                        if sell_amount > 0 and sell_price > 0:
                            # 杠杆交易中，保证金 = （卖出金额） / 杠杆倍数
                            margin = (sell_amount * sell_price) / self._leverage
                            self._used_margin[inst_id]['short'] += margin
            
            # 记录日志
            for inst_id, margins in self._used_margin.items():
                total = margins['long'] + margins['short']
                dynamic_limit = self._get_dynamic_margin_limit(inst_id)
                logger.info(f"保证金使用情况 [{inst_id}]: 总使用={total:.2f} USDT, 多头={margins['long']:.2f} USDT, 空头={margins['short']:.2f} USDT, 动态限制={dynamic_limit:.2f} USDT, 累计收益={self._symbol_profit.get(inst_id, 0.0):.4f} USDT")
        except Exception as e:
            logger.error(f"更新保证金跟踪失败: {e}")

    async def _check_margin_available(self, required_margin: float, inst_id: str, position_type: str = 'long') -> bool:
        """
        检查保证金是否足够（针对特定交易对）
        Args:
            required_margin: 需要的保证金（USDT）
            inst_id: 交易对ID
            position_type: 持仓类型 ('long' 或 'short')
        Returns:
            bool: 保证金是否足够
        """
        try:
            # 更新保证金使用情况
            await self._update_margin_tracking()
            
            # 初始化交易对的保证金记录
            if inst_id not in self._used_margin:
                self._used_margin[inst_id] = {'long': 0.0, 'short': 0.0}
            
            # 计算实际需要的保证金（考虑杠杆倍数）
            actual_margin = required_margin / self._leverage
            
            # 获取当前交易对的已使用保证金
            current_used = self._used_margin[inst_id].get(position_type, 0.0)
            
            # 获取动态保证金限制
            dynamic_limit = self._get_dynamic_margin_limit(inst_id)
            
            # 计算交易后总保证金
            total_after = current_used + actual_margin
            
            # 检查是否超过最大限制
            if total_after > dynamic_limit:
                logger.warning(f"⚠️ 保证金不足 [{inst_id}]: 需要 {actual_margin:.2f} USDT (原始金额: {required_margin:.2f} USDT, 杠杆: {self._leverage}x), 交易后总使用 {total_after:.2f} USDT, 动态限制 {dynamic_limit:.2f} USDT (累计收益: {self._symbol_profit.get(inst_id, 0.0):.4f} USDT)")
                return False
            
            logger.info(f"✅ 保证金充足 [{inst_id}]: 需要 {actual_margin:.2f} USDT (原始金额: {required_margin:.2f} USDT, 杠杆: {self._leverage}x), 交易后总使用 {total_after:.2f} USDT, 动态限制 {dynamic_limit:.2f} USDT (累计收益: {self._symbol_profit.get(inst_id, 0.0):.4f} USDT)")
            return True
        except Exception as e:
            logger.error(f"检查保证金失败: {e}")
            return False

    def _get_dynamic_margin_limit(self, inst_id: str) -> float:
        """
        获取交易对的动态保证金限制

        保证金限制 = 初始值 + 累计收益（最多增加到初始值的5倍，最少不低于初始值的50%）

        Args:
            inst_id: 交易对ID

        Returns:
            float: 动态保证金限制（USDT）
        """
        profit = self._symbol_profit.get(inst_id, 0.0)
        # 计算动态限制：初始值 + 收益
        dynamic_limit = self._initial_margin_per_symbol + profit
        
        # 设置边界：最多5倍，最少50%
        max_limit = self._initial_margin_per_symbol * 5.0
        min_limit = self._initial_margin_per_symbol * 0.5
        
        # 应用边界
        dynamic_limit = max(min_limit, min(dynamic_limit, max_limit))
        
        return dynamic_limit

    def _update_symbol_profit(self, inst_id: str, profit: float):
        """
        更新交易对的累计收益

        Args:
            inst_id: 交易对ID
            profit: 本次交易的盈亏
        """
        if inst_id not in self._symbol_profit:
            self._symbol_profit[inst_id] = 0.0
        self._symbol_profit[inst_id] += profit
        
        # 获取新的动态限制
        new_limit = self._get_dynamic_margin_limit(inst_id)
        logger.info(f"📊 更新{inst_id}收益: +{profit:.4f} USDT, 累计收益: {self._symbol_profit[inst_id]:.4f} USDT, 动态保证金限制: {new_limit:.2f} USDT")

    async def _check_expected_return(self, expected_return: float, fee_rate: float = 0.002) -> bool:
        """
        检查预期收益是否大于手续费
        Args:
            expected_return: 预期收益率（小数，如0.02表示2%）
            fee_rate: 手续费率（小数，如0.002表示0.2%）
        Returns:
            bool: 预期收益是否大于手续费
        """
        if expected_return <= fee_rate:
            logger.warning(f"⚠️ 预期收益率 {expected_return*100:.2f}% 小于等于手续费率 {fee_rate*100:.2f}%，不执行交易")
            return False
        
        logger.info(f"✅ 预期收益率 {expected_return*100:.2f}% 大于手续费率 {fee_rate*100:.2f}%，可以执行交易")
        return True

    async def _get_account_info(self):
        """
        获取账户信息

        Returns:
            AccountInfo: 账户信息
        """
        try:
            # 从order_agent获取账户信息
            order_agent = None
            for agent_id, agent in self._agents.items():
                if agent.name == "Order":
                    order_agent = agent
                    break
            
            if order_agent and order_agent.trader:
                return await order_agent.trader.get_account_info()
            else:
                logger.warning("未找到OrderAgent或trader未初始化")
                return None
        except Exception as e:
            logger.error(f"获取账户信息失败: {e}")
            return None

    async def _detect_held_currencies(self):
        """
        检测所有持仓货币

        Returns:
            List[str]: 持仓货币列表
        """
        try:
            account_info = await self._get_account_info()
            if not account_info:
                logger.warning("无法获取账户信息，无法检测持仓货币")
                return []
            
            # 从账户信息中获取所有有余额的货币
            held_currencies = []
            for currency, info in account_info.currencies.items():
                # 检查是否有可用余额
                avail_bal = info.get('available', 0)
                if float(avail_bal) > 0:
                    held_currencies.append(currency)
            
            logger.info(f"检测到持仓货币: {held_currencies}")
            return held_currencies
        except Exception as e:
            logger.error(f"检测持仓货币失败: {e}")
            return []

    async def sync_account_orders(self):
        """
        从账户获取订单信息并同步到机器人中

        调用order_agent的sync_account_orders_from_exchange方法
        从OKX API获取完整的订单历史并同步到本地
        """
        try:
            # 从order_agent获取账户信息
            order_agent = None
            for agent_id, agent in self._agents.items():
                if agent.name == "Order":
                    order_agent = agent
                    break
            
            if order_agent and hasattr(order_agent, 'sync_account_orders_from_exchange'):
                await order_agent.sync_account_orders_from_exchange()
                logger.info("✅ 账户订单同步完成")
            else:
                logger.error("❌ 无法同步账户订单: order_agent未找到或方法不存在")
        except Exception as e:
            logger.error(f"同步账户订单失败: {e}")

    async def _execute_cycle(self):
        """执行周期"""
        # 检查系统健康
        await self._check_system_health()

        # 协调智能体间通信
        await self._coordinate_agents()

        await asyncio.sleep(5)

    async def _check_system_health(self):
        """检查系统健康"""
        healthy_count = 0
        unhealthy_count = 0

        for agent_id, agent in self._agents.items():
            if agent.is_healthy():
                healthy_count += 1
            else:
                unhealthy_count += 1

                # 尝试恢复
                if self._auto_recovery and agent.status == AgentStatus.ERROR:
                    logger.info(f"尝试恢复智能体: {agent_id}")
                    await agent.start()

        # 定期同步订单（每60秒一次）
        current_time = time.time()
        if not hasattr(self, '_last_sync_time') or current_time - self._last_sync_time > 60:
            self._last_sync_time = current_time
            order_agent = self._agents.get('order_agent')
            if order_agent and hasattr(order_agent, 'sync_orders_with_exchange'):
                await order_agent.sync_orders_with_exchange()

        # 更新系统健康状态
        total = len(self._agents)
        if total > 0:
            health_ratio = healthy_count / total
            if health_ratio >= 0.8:
                self._system_health = "healthy"
            elif health_ratio >= 0.5:
                self._system_health = "degraded"
            else:
                self._system_health = "unhealthy"

    async def _coordinate_agents(self):
        """协调智能体间通信"""
        # 清理过期的通信缓存
        self._cleanup_communication_cache()

    async def communicate_with_agent(self, agent_name: str, action: str, **kwargs) -> Any:
        """
        与指定智能体直接通信

        Args:
            agent_name: 智能体名称
            action: 要执行的操作
            **kwargs: 操作参数

        Returns:
            Any: 通信结果
        """
        import time
        start_time = time.time()
        self._communication_stats['total_calls'] += 1

        # 生成缓存键
        cache_key = f"{agent_name}:{action}:{str(kwargs)}"

        # 检查缓存
        cached_result = self._get_cached_communication(cache_key)
        if cached_result is not None:
            self._communication_stats['cached_calls'] += 1
            logger.debug(f"使用缓存的通信结果: {cache_key}")
            return cached_result

        # 查找目标智能体
        target_agent = None
        for agent_id, agent in self._agents.items():
            if agent.name == agent_name:
                target_agent = agent
                break

        if not target_agent:
            logger.error(f"未找到智能体: {agent_name}")
            self._communication_stats['failed_calls'] += 1
            return None

        try:
            # 直接调用智能体的方法
            if hasattr(target_agent, action):
                method = getattr(target_agent, action)
                if callable(method):
                    result = await method(**kwargs)
                    
                    # 缓存结果
                    self._cache_communication(cache_key, result)
                    
                    # 更新通信统计
                    response_time = time.time() - start_time
                    self._communication_stats['total_response_time'] += response_time
                    if self._communication_stats['total_calls'] - self._communication_stats['failed_calls'] > 0:
                        self._communication_stats['avg_response_time'] = \
                            self._communication_stats['total_response_time'] / \
                            (self._communication_stats['total_calls'] - self._communication_stats['failed_calls'])
                    
                    logger.debug(f"与智能体通信成功: {agent_name}.{action}")
                    return result
                else:
                    logger.error(f"智能体 {agent_name} 的 {action} 不是可调用方法")
            else:
                logger.error(f"智能体 {agent_name} 没有 {action} 方法")
        except Exception as e:
            logger.error(f"与智能体通信失败: {e}")
            self._communication_stats['failed_calls'] += 1
        
        return None

    def _cache_communication(self, key: str, result: Any):
        """缓存通信结果"""
        self._communication_cache[key] = {
            'result': result,
            'timestamp': time.time()
        }

    def _get_cached_communication(self, key: str) -> Any:
        """获取缓存的通信结果"""
        cached = self._communication_cache.get(key)
        if cached:
            if time.time() - cached['timestamp'] < self._cache_ttl:
                return cached['result']
            else:
                # 缓存过期，删除
                del self._communication_cache[key]
        return None

    def _cleanup_communication_cache(self):
        """清理过期的通信缓存"""
        current_time = time.time()
        expired_keys = [
            key for key, value in self._communication_cache.items()
            if current_time - value['timestamp'] >= self._cache_ttl
        ]
        for key in expired_keys:
            del self._communication_cache[key]

    def get_communication_stats(self) -> Dict[str, Any]:
        """获取通信统计信息"""
        return self._communication_stats

    async def _on_agent_registered(self, event: Event):
        """处理智能体注册事件"""
        agent_id = event.data.get("agent_id")
        name = event.data.get("name")
        logger.info(f"智能体注册: {name} ({agent_id})")
        
        # 智能体注册逻辑已在 TradingBot.initialize 中通过 register_agent 方法处理
        # 这里只记录日志
        logger.info(f"智能体注册事件已处理: {name} ({agent_id})")

    async def _on_agent_unregistered(self, event: Event):
        """处理智能体注销事件"""
        agent_id = event.data.get("agent_id")
        logger.info(f"智能体注销: {agent_id}")

    async def _on_system_error(self, event: Event):
        """处理系统错误"""
        self._system_stats["total_errors"] += 1
        logger.error(f"系统错误: {event.data}")

    async def _on_strategy_signal(self, event: Event):
        """处理策略信号"""
        signal = event.data.get("signal", {})
        logger.info(f"收到策略信号: {signal}")
        
        # 从信号中获取交易对和当前价格（在使用前定义）
        inst_id = signal.get("inst_id", "BTC-USDT")
        current_price = signal.get("price", 0)
        
        # 检查信号类型，处理买入、卖出、持有和中性信号
        side = signal.get("side")
        if side not in ["buy", "sell", "hold", "neutral"]:
            logger.info(f"信号类型为{side}，不执行交易")
            return
        
        # 对于中性信号，只记录日志，不执行交易
        if side == "neutral":
            logger.info(f"收到中性信号: {signal}")
            return
        
        # 对于持有信号（hold），继续计算多空预期收益，但不执行交易
        if side == "hold":
            logger.info(f"收到持有信号，继续计算多空预期收益: {signal}")
        
        # 检查是否为重复信号
        signal_key = f"{signal.get('price', 0)}_{signal.get('side', '')}_{signal.get('timestamp', '')}"
        current_time = time.time()
        
        # 检查信号是否在最近30秒内已处理过（避免重复处理）- 但hold信号始终处理
        if side != "hold" and signal_key in self._recent_signals:
            logger.info(f"该信号在最近30秒内已处理过，跳过本次交易: {signal_key}")
            return
        
        # 计算并调整风险收益指数
        signal_level = signal.get("signal_level", "S")
        indicators = signal.get("indicators", {})
        spring_drift = indicators.get("spring_drift", {})
        
        # 分析弹簧飘移方向，划分信号级别
        p_drift = spring_drift.get("P", "→")
        e_drift = spring_drift.get("E", "→")
        m_drift = spring_drift.get("M", "→")
        
        # 根据弹簧飘移方向划分信号级别
        drift_level = "S"  # 默认S级
        if p_drift == "↑" and e_drift == "↑" and m_drift == "↑":
            drift_level = "SSS"
        elif (p_drift == "↑" and m_drift == "↑") or (e_drift == "↑" and m_drift == "↑"):
            drift_level = "SS"
        elif p_drift == "↓" and e_drift == "↓" and m_drift == "↓":
            drift_level = "SSS"
        elif (p_drift == "↓" and m_drift == "↓") or (e_drift == "↓" and m_drift == "↓"):
            drift_level = "SS"
        
        # 调整多空指数
        if self._last_signal_side != side:
            # 信号方向改变，调整指数
            if side == "buy":
                # 买入信号，提高多空指数
                if signal_level == "SSS" or drift_level == "SSS":
                    self._risk_return_index += 30
                elif signal_level == "SS" or drift_level == "SS":
                    self._risk_return_index += 20
                else:  # S级
                    self._risk_return_index += 10
            else:  # sell
                # 卖出信号，降低多空指数
                if signal_level == "SSS" or drift_level == "SSS":
                    self._risk_return_index -= 30
                elif signal_level == "SS" or drift_level == "SS":
                    self._risk_return_index -= 20
                else:  # S级
                    self._risk_return_index -= 10
                
                # 多空指数无限累积，不设下限
            self._last_signal_side = side
        
        # 通过策略收益自动调整多空指数
        try:
            # 获取盈利增长管理器的累计盈利
            total_profit_usdt = profit_growth_manager.total_profit_usdt
            total_profit_btc = profit_growth_manager.total_profit_btc
            trade_count = profit_growth_manager.trade_count
            
            if trade_count > 0:
                # 计算平均每笔交易的盈利
                avg_profit_per_trade = total_profit_usdt / trade_count
                
                # 根据盈利情况调整多空指数
                if avg_profit_per_trade > 0:
                    # 盈利，提高多空指数
                    profit_adjustment = min(avg_profit_per_trade * 5, 10)  # 最多调整10%
                    self._risk_return_index += profit_adjustment
                    logger.info(f"策略盈利，多空指数调整 +{profit_adjustment:.1f}% (平均每笔盈利: {avg_profit_per_trade:.2f} USDT)")
                elif avg_profit_per_trade < 0:
                    # 亏损，降低多空指数
                    profit_adjustment = max(avg_profit_per_trade * 5, -10)  # 最多调整-10%
                    self._risk_return_index += profit_adjustment
                    logger.info(f"策略亏损，多空指数调整 {profit_adjustment:.1f}% (平均每笔亏损: {abs(avg_profit_per_trade):.2f} USDT)")
        except Exception as e:
            logger.error(f"通过策略收益调整多空指数失败: {e}")
        
        # 检查多空指数状态
        logger.info(f"当前多空指数: {self._risk_return_index:.1f}% (正值为多，负值为空，0为中立)")
        
        # 冷静期已关闭，允许自由买卖
        # 检查是否在冷静期内 - 已禁用
        # if self._cooldown_start_time is not None:
        #     current_time = time.time()
        #     elapsed_time = current_time - self._cooldown_start_time
        #     if elapsed_time < self._cooldown_period:
        #         remaining_time = self._cooldown_period - elapsed_time
        #         logger.warning(f"处于冷静期内，剩余 {remaining_time:.1f} 秒，冷静期类型: {self._cooldown_type}")
        #         # 冷静期只阻止买入操作，不阻止卖出操作
        #         if side == "buy":
        #             logger.warning(f"{self._cooldown_type}冷静期内不允许买入操作")
        #             return
        #         # 卖出操作始终允许
        #         logger.info(f"{self._cooldown_type}冷静期内允许卖出操作")
        #     else:
        #         # 冷静期结束，重置
        #         logger.info(f"冷静期结束，风险收益指数重置为50%")
        #         self._cooldown_start_time = None
        #         self._cooldown_period = 0
        #         self._cooldown_level = 0
        #         self._cooldown_type = None
        #         self._risk_return_index = 50.0
        
        # 风险收益指数限制已关闭，允许自由买卖
        # if self._risk_return_index < 50:
        #     logger.info("风险收益指数低于50%，处于卖出状态")
        #     # 低于50%，只允许卖出操作
        #     if side == "buy":
        #         logger.info("风险收益指数低于50%，不执行买入操作")
        #         return
        # else:
        #     logger.info("风险收益指数高于50%，处于买入状态")
        #     # 高于50%，允许买入操作
        logger.info("冷静期已关闭，允许自由买卖")
        
        # 获取订单智能体
        order_agent = None
        for agent_id, agent in self._agents.items():
            if agent.name == "Order":
                order_agent = agent
                break
        
        # 确保订单智能体存在
        if not order_agent:
            logger.error("未找到订单智能体，无法执行交易")
            return
        
        # 对于买入信号，检查是否有未卖出的买入订单（如果有执行平空操作，否则执行做多操作）
        if side == "buy":
            # 直接从OKX API获取订单历史，查找未卖出的买入订单
            try:
                # 直接从OKX API获取订单历史，包括现货和杠杆交易
                exchange_orders = []
                if order_agent.trader:
                    try:
                        # 获取现货交易订单历史
                        spot_orders = await order_agent.trader.get_order_history(
                            'SPOT',  # inst_type
                            inst_id,  # 从信号中获取的交易对
                            100  # 最多获取100条记录
                        )
                        exchange_orders.extend(spot_orders)
                    except Exception as e:
                        logger.error(f"获取现货订单历史失败: {e}")
                    
                    try:
                        # 获取杠杆交易订单历史
                        margin_orders = await order_agent.trader.get_order_history(
                            'MARGIN',  # inst_type
                            inst_id,  # 从信号中获取的交易对
                            100  # 最多获取100条记录
                        )
                        exchange_orders.extend(margin_orders)
                    except Exception as e:
                        logger.error(f"获取杠杆订单历史失败: {e}")
                elif order_agent.rest_client:
                    try:
                        # 获取现货交易订单历史
                        spot_orders = await order_agent.rest_client.get_order_history(
                            'SPOT',  # inst_type
                            inst_id,  # 从信号中获取的交易对
                            100  # 最多获取100条记录
                        )
                        exchange_orders.extend(spot_orders)
                    except Exception as e:
                        logger.error(f"获取现货订单历史失败: {e}")
                    
                    try:
                        # 获取杠杆交易订单历史
                        margin_orders = await order_agent.rest_client.get_order_history(
                            'MARGIN',  # inst_type
                            inst_id,  # 从信号中获取的交易对
                            100  # 最多获取100条记录
                        )
                        exchange_orders.extend(margin_orders)
                    except Exception as e:
                        logger.error(f"获取杠杆订单历史失败: {e}")
                
                # 处理OKX返回的订单数据
                processed_orders = []
                for order in exchange_orders:
                    if isinstance(order, dict):
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
                            'instId': order.get('instId', 'BTC-USDT')
                        }
                        processed_orders.append(processed_order)
                
                # 统计实际账户中的订单
                exchange_buy_orders = [o for o in processed_orders if o.get('side') == 'buy' and o.get('state') == 'filled']
                exchange_sell_orders = [o for o in processed_orders if o.get('side') == 'sell' and o.get('state') == 'filled']
                
                # 计算未卖出的买入订单数量
                unmatched_buy_orders = len(exchange_buy_orders) - len(exchange_sell_orders)
                
                # 记录未卖出的买入订单ID
                if unmatched_buy_orders > 0:
                    unmatched_ids = [order.get('ordId') for order in exchange_buy_orders[-unmatched_buy_orders:]]
                    logger.info(f"当前未卖出的买入订单ID: {unmatched_ids}")
                    logger.info(f"未卖出的买入订单数量: {unmatched_buy_orders}（持仓限制已禁用）")
                    
                    # 有未卖出的买入订单，继续执行做多操作（不再自动平仓）
                    logger.info("有未卖出的买入订单，继续执行做多操作（不再自动平仓）")
                    # 注释掉自动平仓逻辑，避免买入后立即平仓
                    # side = "sell"
                    # is_short_sell = True
                else:
                    # 没有未卖出的买入订单，执行做多操作
                    logger.info("没有未卖出的买入订单，执行做多操作")
                    
                    # 实现梯度交易逻辑（价格跌幅梯度）
                    # 计算当前价格与上一个买入订单价格的跌幅
                    latest_buy_trade = None
                    if exchange_buy_orders:
                        # 按时间排序，获取最近的买入订单
                        exchange_buy_orders.sort(key=lambda x: x.get('cTime', 0), reverse=True)
                        latest_buy_trade = exchange_buy_orders[0]
                    
                    current_price = signal.get("price", 0)
                    
                    if latest_buy_trade:
                        latest_buy_price = float(latest_buy_trade.get('avgPx', '0'))
                        # 移除价格跌幅检查，允许在任何价格情况下执行交易
                        if latest_buy_price > 0:
                            price_drop = (latest_buy_price - current_price) / latest_buy_price
                            if price_drop <= 0:
                                # 价格上涨或不变，允许买入
                                logger.info(f"当前价格上涨 {abs(price_drop) * 100:.2f}%，允许执行买入交易")
                            else:
                                # 价格下跌，也允许买入
                                logger.info(f"当前价格下跌 {price_drop * 100:.2f}%，允许执行买入交易")
                        
                        # 更新买入订单计数
                        self._buy_order_count += 1
                        
                        # 获取当日振幅（从信号中获取）
                        daily_amplitude = signal.get("daily_amplitude", 0.0)
                        self._daily_amplitude = daily_amplitude
                        
                        # 从交易对中提取币种
                        symbol = inst_id.split('-')[0]
                        
                        # 计算当前币种数量增长率
                        current_size = 0.0  # 初始化为0，后续会从账户信息中获取
                        if self._first_size is not None and self._first_size > 0:
                            current_growth_rate = (current_size - self._first_size) / self._first_size
                        else:
                            current_growth_rate = 0.0
                        
                        # 检查最早的币种数量增长率是否与当日振幅相同，进入下一个梯度
                        if self._first_growth_rate is None:
                            # 记录最早的币种数量增长率
                            self._first_growth_rate = current_growth_rate
                            self._first_size = current_size
                            logger.info(f"记录最早的{symbol}数量: {self._first_size:.8f} {symbol}, 增长率: {self._first_growth_rate:.2%}")
                        elif abs(current_growth_rate - daily_amplitude) < 0.001:  # 允许0.1%的误差
                            # 最早的币种数量增长率与当日振幅相同，进入下一个梯度
                            self._current_gradient += 1
                            logger.info(f"梯度更新: 最早的{symbol}数量增长率({current_growth_rate:.2%})与当日振幅({daily_amplitude:.2%})相同，进入第 {self._current_gradient} 梯度")
                            # 重置最早的币种数量增长率
                            self._first_growth_rate = None
                            self._first_size = None
                        else:
                            logger.info(f"当前梯度: {self._current_gradient}, 最早的{symbol}数量增长率: {self._first_growth_rate:.2%}, 当日振幅: {daily_amplitude:.2%}")
                        
                        logger.info(f"买入订单计数: {self._buy_order_count}")
                    else:
                        # 第一个买入订单
                        self._buy_order_count = 1
                        daily_amplitude = signal.get("daily_amplitude", 0.0)
                        self._daily_amplitude = daily_amplitude
                        
                        # 从交易对中提取币种
                        symbol = inst_id.split('-')[0]
                        
                        # 记录最早的币种数量
                        current_size = 0.0  # 初始化为0，后续会从账户信息中获取
                        self._first_size = current_size
                        self._first_growth_rate = 0.0  # 第一个订单的增长率为0
                        
                        logger.info(f"开始第 {self._current_gradient} 梯度 (当日振幅: {daily_amplitude:.2%}, 最早{symbol}数量: {self._first_size:.8f} {symbol})")
            except Exception as e:
                logger.error(f"检查未卖出订单失败: {e}")
        
        # 记录信号处理时间
        self._recent_signals[signal_key] = current_time
        
        # 清理30秒前的信号记录
        expired_signals = [k for k, v in self._recent_signals.items() if current_time - v > 30]
        for k in expired_signals:
            del self._recent_signals[k]
        
        # 保存策略信号和预期收益
        signal_id = f"{signal.get('timestamp', '')}_{signal.get('side', '')}_{signal.get('price', '')}"
        
        # 从策略信号中获取预期收益
        current_price = signal.get("price", 0)
        expected_return = signal.get("expected_return", 0.0)
        signal_level = signal.get("signal_level", "S")  # 获取信号级别，默认为S级
        
        # 冷静期已关闭，允许自由买卖
        # 检查是否在冷静期内 - 已禁用
        # if self._cooldown_start_time is not None:
        #     elapsed_time = current_time - self._cooldown_start_time
        #     if elapsed_time < self._cooldown_period:
        #         remaining_time = self._cooldown_period - elapsed_time
        #         logger.warning(f"处于冷静期内，剩余 {remaining_time:.1f} 秒，冷静期类型: {self._cooldown_type}")
        #         # 冷静期只阻止买入操作，不阻止卖出操作
        #         if side == "buy":
        #             logger.warning(f"{self._cooldown_type}冷静期内不允许买入操作")
        #             return
        #         # 卖出操作始终允许
        #         logger.info(f"{self._cooldown_type}冷静期内允许卖出操作")
        #     else:
        #         # 冷静期结束，重置
        #         logger.info(f"冷静期结束，冷静期时长: {self._cooldown_period} 秒，冷静期级别: {self._cooldown_level}")
        #         self._cooldown_start_time = None
        #         self._cooldown_period = 0
        #         self._cooldown_level = 0
        #         self._cooldown_type = None
        #         # 风险收益指数重置为50%
        #         self._risk_return_index = 50.0
        #         logger.info(f"风险收益指数重置为50%")
        
        # 更新多空指数（信号累加）
        if side == "buy":
            # 买入信号增加多空指数
            if signal_level == "SSS":
                self._risk_return_index += 30  # SSS级信号 +30%
            elif signal_level == "SS":
                self._risk_return_index += 20  # SS级信号 +20%
            else:  # S级信号
                self._risk_return_index += 10  # S级信号 +10%
            
            # 多空指数无限累积，不设上限
            #     # 进入买入冷静期，冷静期时长10秒，可叠加
            #     self._cooldown_period = 10 + (self._cooldown_level * 5)  # 基础10秒，每级叠加5秒
            #     self._cooldown_start_time = current_time
            #     self._cooldown_level += 1
            #     self._cooldown_type = "buy"  # 标记为买入冷静期
            #     logger.warning(f"风险收益指数触及最高100%，进入买入冷静期 {self._cooldown_period} 秒，冷静期级别: {self._cooldown_level}")
            
            logger.info(f"买入信号，预期收益: {expected_return * 100:.2f}%")
            logger.info(f"风险收益指数: {self._risk_return_index:.1f}% (买入信号 +{10 if signal_level == 'S' else 20 if signal_level == 'SS' else 30}%)")
        elif side == "sell" and order_agent:
            # 卖出信号减少风险收益指数
            if signal_level == "SSS":
                self._risk_return_index -= 30  # SSS级信号 -30%
            elif signal_level == "SS":
                self._risk_return_index -= 20  # SS级信号 -20%
            else:  # S级信号
                self._risk_return_index -= 10  # S级信号 -10%
            
            # 检查是否触及最低0%，进入卖出冷静期 - 已禁用
            # if self._risk_return_index <= 0:
            #     self._risk_return_index = 0
            #     # 进入卖出冷静期，冷静期时长10秒，可叠加
            #     self._cooldown_period = 10 + (self._cooldown_level * 5)  # 基础10秒，每级叠加5秒
            #     self._cooldown_start_time = current_time
            #     self._cooldown_level += 1
            #     self._cooldown_type = "sell"  # 标记为卖出冷静期
            #     logger.warning(f"风险收益指数触及最低0%，进入卖出冷静期 {self._cooldown_period} 秒，冷静期级别: {self._cooldown_level}")
            
            logger.info(f"卖出信号，预期收益: {expected_return * 100:.2f}%")
            logger.info(f"多空指数: {self._risk_return_index:.1f}% (卖出信号 -{10 if signal_level == 'S' else 20 if signal_level == 'SS' else 30}%)")
        
        # 保存信号信息
        signal_info = {
            "signal": signal,
            "expected_return": expected_return,
            "received_time": current_time,
            "processed": False
        }
        self._strategy_signals[signal_id] = signal_info
        logger.info(f"保存策略信号: {signal_id}, 预期收益: {expected_return * 100:.2f}%")
        
        # 初始化is_short_sell变量
        is_short_sell = False

        # 重新加载盈利增长管理器状态（确保获取最新数据）
        profit_growth_manager._load_state()

        if side == "buy":
            # 暂时跳过盈利增长管理器的检查，以便测试2倍杠杆交易
            logger.info("跳过盈利增长管理器的买入检查，直接执行买入操作")
            # should_buy, buy_reason = profit_growth_manager.should_buy(current_price)
            # 
            # if not should_buy:
            #     logger.warning(f"不满足买入条件: {buy_reason}")
            #     return
            # 
            # logger.info(f"满足买入条件: {buy_reason}")

        elif side == "sell":
            # 跳过盈利增长管理器的卖出检查，允许自由卖出
            logger.info("跳过盈利增长管理器的卖出检查，直接执行卖出操作")
        
        # 检查风险值，防止爆仓（使用更宽松的策略）
        if order_agent and order_agent.trader:
            try:
                # 获取风险信息
                risk_info = await order_agent.trader.get_risk_info()
                if risk_info:
                    logger.info(f"📊 风险信息: 保证金率={risk_info.margin_ratio:.2f}, 风险等级={risk_info.risk_level}")
                    
                    # 只有在保证金率非常低（接近爆仓）时才阻止交易
                    if risk_info.risk_level == "danger" and risk_info.margin_ratio < Decimal('1.05'):
                        logger.warning(f"⚠️ 保证金率过低({risk_info.margin_ratio:.2f})，接近爆仓，不执行交易")
                        return
                    elif risk_info.risk_level == "warning":
                        logger.warning(f"⚠️ 风险等级为warning，请注意风险")
            except Exception as e:
                logger.error(f"检查风险值失败: {e}，继续执行交易")
        
        # 检查收益是否大于手续费：只在平仓或反向交易时检查
        # 假设手续费率为0.2%
        fee_rate = 0.002
        # 首先检查是否有未卖出的买入订单，确定当前持仓状态
        has_unsold_orders = False
        try:
            # 直接从OKX API获取订单历史，包括现货和杠杆交易
            exchange_orders = []
            if order_agent.trader:
                try:
                    # 获取现货交易订单历史
                    spot_orders = await order_agent.trader.get_order_history(
                        'SPOT',  # inst_type
                        inst_id,  # 从信号中获取的交易对
                        100  # 最多获取100条记录
                    )
                    exchange_orders.extend(spot_orders)
                except Exception as e:
                    logger.error(f"获取现货订单历史失败: {e}")
                
                try:
                    # 获取杠杆交易订单历史
                    margin_orders = await order_agent.trader.get_order_history(
                        'MARGIN',  # inst_type
                        inst_id,  # 从信号中获取的交易对
                        100  # 最多获取100条记录
                    )
                    exchange_orders.extend(margin_orders)
                except Exception as e:
                    logger.error(f"获取杠杆订单历史失败: {e}")
            elif order_agent.rest_client:
                try:
                    # 获取现货交易订单历史
                    spot_orders = await order_agent.rest_client.get_order_history(
                        'SPOT',  # inst_type
                        inst_id,  # 从信号中获取的交易对
                        100  # 最多获取100条记录
                    )
                    exchange_orders.extend(spot_orders)
                except Exception as e:
                    logger.error(f"获取现货订单历史失败: {e}")
                
                try:
                    # 获取杠杆交易订单历史
                    margin_orders = await order_agent.rest_client.get_order_history(
                        'MARGIN',  # inst_type
                        inst_id,  # 从信号中获取的交易对
                        100  # 最多获取100条记录
                    )
                    exchange_orders.extend(margin_orders)
                except Exception as e:
                    logger.error(f"获取杠杆订单历史失败: {e}")
            
            # 处理OKX返回的订单数据
            processed_orders = []
            for order in exchange_orders:
                if isinstance(order, dict):
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
                        'instId': order.get('instId', 'BTC-USDT')
                    }
                    processed_orders.append(processed_order)
            
            # 统计实际账户中的订单
            exchange_buy_orders = [o for o in processed_orders if o.get('side') == 'buy' and o.get('state') == 'filled']
            exchange_sell_orders = [o for o in processed_orders if o.get('side') == 'sell' and o.get('state') == 'filled']
            
            # 计算未卖出订单数量
            exchange_unsold = len(exchange_buy_orders) - len(exchange_sell_orders)
            has_unsold_orders = exchange_unsold > 0
            
            # 计算平均买入价格用于收益检查
            avg_buy_price = 0.0
            if exchange_buy_orders:
                total_cost = 0.0
                total_size = 0.0
                for order in exchange_buy_orders:
                    price = float(order.get('avgPx', '0'))
                    size = float(order.get('fillSz', '0'))
                    total_cost += price * size
                    total_size += size
                if total_size > 0:
                    avg_buy_price = total_cost / total_size
            
            # 计算平均卖出价格用于收益检查
            avg_sell_price = 0.0
            if exchange_sell_orders:
                total_revenue = 0.0
                total_size = 0.0
                for order in exchange_sell_orders:
                    price = float(order.get('avgPx', '0'))
                    size = float(order.get('fillSz', '0'))
                    total_revenue += price * size
                    total_size += size
                if total_size > 0:
                    avg_sell_price = total_revenue / total_size
            
            # 检查是否为平仓或反向交易
            is_close_or_reverse = False
            if side == "sell" and has_unsold_orders:
                # 卖出且有未平仓多单：平多操作
                is_close_or_reverse = True
                logger.info("检测到平多操作")
                # 1. 检查预期收益（策略预测的未来市场价值）
                strategy_expected_return = signal.get('expected_return', 0) * 100  # 转换为百分比
                logger.info(f"策略预期收益: {strategy_expected_return:.2f}%")
                # 2. 检查实际收益是否大于手续费
                # 做多收益：(当前卖出价 - 持仓买入价) / 持仓买入价
                if avg_buy_price > 0:
                    actual_return = (current_price - avg_buy_price) / avg_buy_price * 100
                    logger.info(f"做多实际收益: {actual_return:.2f}%")
                    # 做多赚钱条件：当前卖出价 > 持仓买入价 * 1.002
                    # 普通平多：0.2%，反向交易（平多做空）：0.3%
                    fee_threshold = 0.2  # 平多不是反向交易
                    if actual_return < fee_threshold:
                        logger.warning(f"做多实际收益过低: {actual_return:.2f}%，低于手续费{fee_threshold}%，取消平多操作")
                        return
                    else:
                        logger.info(f"做多实际收益: {actual_return:.2f}%，大于手续费{fee_threshold}%，执行平多操作")
            elif side == "buy" and has_unsold_orders:
                # 买入且有未平仓空单：平空操作（反向交易）
                is_close_or_reverse = True
                logger.info("检测到平空操作（反向交易）")
                # 1. 检查预期收益（策略预测的未来市场价值）
                strategy_expected_return = signal.get('expected_return', 0) * 100  # 转换为百分比
                logger.info(f"策略预期收益: {strategy_expected_return:.2f}%")
                # 2. 检查实际收益是否大于手续费
                # 做空收益：(持仓卖出价 - 当前买入价) / 持仓卖出价
                if avg_sell_price > 0:
                    actual_return = (avg_sell_price - current_price) / avg_sell_price * 100
                    logger.info(f"做空实际收益: {actual_return:.2f}%")
                    # 做空赚钱条件：当前买入价 < 持仓卖出价 * 0.998
                    # 普通平空：0.2%，反向交易（平空做多）：0.3%
                    fee_threshold = 0.3  # 平空操作是反向交易，需要0.3%
                    if actual_return < fee_threshold:
                        logger.warning(f"做空实际收益过低: {actual_return:.2f}%，低于手续费{fee_threshold}%，取消平空操作")
                        return
                    else:
                        logger.info(f"做空实际收益: {actual_return:.2f}%，大于手续费{fee_threshold}%，执行平空操作")
            
            if is_close_or_reverse:
                logger.info("检测到平仓或反向交易，检查收益后执行")
            else:
                logger.info("非平仓或反向交易，直接执行")
        except Exception as e:
            logger.error(f"检查持仓状态和收益失败: {e}")
        
        if not order_agent:
            logger.error("未找到订单智能体，无法执行交易")
            return
        
        # 构建订单参数 - 根据交易对使用不同的最小交易单位
        
        # 获取可用USDT余额（动态获取）
        usdt_balance = await self._get_available_usdt_balance()
        
        # 从配置文件获取交易金额设置
        from core.config.env_manager import env_manager
        trading_config = env_manager.get_trading_config()
        fixed_trade_amount = trading_config.get('fixed_trade_amount', 10)
        trade_amount_percentage = trading_config.get('trade_amount_percentage', 0.1)
        min_order_amount = trading_config.get('min_order_amount', 1)
        max_trade_amount = trading_config.get('max_position_size', 1000)
        
        # 根据交易对设置最小交易单位
        min_order_sizes = {
            "BTC-USDT": 0.00001,  # BTC最小交易单位
            "ETH-USDT": 0.0001,   # ETH最小交易单位
            "LTC-USDT": 0.001,    # LTC最小交易单位
            "DOGE-USDT": 1,        # DOGE最小交易单位
            "SOL-USDT": 0.001,     # SOL最小交易单位
        }
        
        # 获取当前交易对的最小交易单位
        min_size = min_order_sizes.get(inst_id, 0.0001)  # 默认最小交易单位
        base_currency = inst_id.split('-')[0]
        
        # 计算最小交易金额（根据交易对的币值）
        if 'BTC' in inst_id:
            min_amount = 0.00001 * current_price  # BTC最小交易单位 0.00001 (约0.762 USDT)
        elif 'ETH' in inst_id:
            min_amount = 0.0001 * current_price  # ETH最小交易单位 0.0001 (约0.235 USDT)
        else:
            min_amount = 1.0  # 其他交易对默认1 USDT
        
        # 计算交易金额（使用动态余额计算）
        if fixed_trade_amount > 0:
            # 使用固定交易金额
            trade_amount_usdt = fixed_trade_amount
            logger.info(f"使用固定交易金额: {trade_amount_usdt:.2f} USDT")
        else:
            # 使用可用余额的1%计算交易金额，最低为最小交易单位
            if usdt_balance > 0:
                calculated_amount = usdt_balance * 0.01  # 1% of balance
                trade_amount_usdt = max(min_amount, calculated_amount)  # 取最大值
                trade_amount_usdt = int(trade_amount_usdt)  # 向下取整到整数
                trade_amount_usdt = max(1, trade_amount_usdt)  # 确保至少1 USDT
                logger.info(f"使用动态余额计算: {trade_amount_usdt} USDT (账户余额的1%，最小交易单位: {min_amount:.2f} USDT)")
            else:
                trade_amount_usdt = max(1.0, min_amount)
                trade_amount_usdt = int(trade_amount_usdt)
                logger.warning(f"无法获取账户余额，使用最小交易单位: {trade_amount_usdt} USDT")
        
        # 检查交易金额是否超过最大限制
        if trade_amount_usdt > max_trade_amount:
            trade_amount_usdt = max_trade_amount
            logger.warning(f"交易金额超过最大限制，调整为: {trade_amount_usdt:.2f} USDT")
        
        # 确保交易金额至少为最小订单金额
        if trade_amount_usdt < min_order_amount:
            trade_amount_usdt = min_order_amount
            logger.warning(f"交易金额小于最小订单金额，调整为: {trade_amount_usdt:.2f} USDT")
        
        # 增仓价格检查
        if has_unsold_orders:
            if side == "buy":
                # 增仓做多：二次加仓价格必须低于持仓均价
                if avg_buy_price > 0 and current_price >= avg_buy_price:
                    logger.warning(f"增仓做多价格检查失败: 当前价格 {current_price:.2f} >= 持仓均价 {avg_buy_price:.2f}，取消增仓操作")
                    return
                elif avg_buy_price > 0:
                    logger.info(f"增仓做多价格检查通过: 当前价格 {current_price:.2f} < 持仓均价 {avg_buy_price:.2f}，执行增仓操作")
            elif side == "sell":
                # 增仓做空：二次加仓价格必须高于持仓均价
                if avg_sell_price > 0 and current_price <= avg_sell_price:
                    logger.warning(f"增仓做空价格检查失败: 当前价格 {current_price:.2f} <= 持仓均价 {avg_sell_price:.2f}，取消增仓操作")
                    return
                elif avg_sell_price > 0:
                    logger.info(f"增仓做空价格检查通过: 当前价格 {current_price:.2f} > 持仓均价 {avg_sell_price:.2f}，执行增仓操作")
        
        # 检查余额是否足够
        if side == "buy" and usdt_balance < trade_amount_usdt:
            logger.warning(f"USDT余额不足，无法执行买入: 可用 {usdt_balance:.2f} USDT < 所需 {trade_amount_usdt:.2f} USDT")
            return
        
        # 计算交易数量
        if side == "buy":
            # 买入时，sz为币种数量
            sz = trade_amount_usdt / current_price
            # 确保购买数量大于等于最小交易单位
            if sz < min_size:
                sz = min_size
                trade_amount_usdt = sz * current_price
                logger.info(f"购买数量小于最小交易单位，调整为最小交易单位: {sz} {base_currency} (交易金额: {trade_amount_usdt:.2f} USDT)")
            # 根据币种设置合适的小数位数
            if base_currency == "DOGE":
                sz_str = "{0:.0f}".format(sz)
            else:
                sz_str = "{0:.5f}".format(sz)
            logger.info(f"买入策略: 使用 {sz} {base_currency} 进行买入（约 {trade_amount_usdt:.2f} USDT）")
        else:
            # 卖出时，sz为币种数量
            # 尝试从账户信息中获取持仓数量
            if order_agent and order_agent.trader:
                try:
                    position = await order_agent.trader.get_position(inst_id)
                    if position and position.size > 0:
                        sz = position.size
                        # 修复类型错误：将 decimal.Decimal 转换为 float
                        trade_amount_usdt = float(sz) * current_price
                        logger.info(f"从账户获取到持仓数量: {sz} {base_currency} (交易金额: {trade_amount_usdt:.2f} USDT)")
                except Exception as e:
                    logger.error(f"获取持仓数量失败: {e}")
                    # 如果获取失败，使用计算的数量
                    sz = trade_amount_usdt / current_price
            else:
                # 使用计算的数量
                sz = trade_amount_usdt / current_price
            
            # 确保卖出数量大于等于最小交易单位
            if sz < min_size:
                sz = min_size
                trade_amount_usdt = sz * current_price
                logger.info(f"卖出数量小于最小交易单位，调整为最小交易单位: {sz} {base_currency} (交易金额: {trade_amount_usdt:.2f} USDT)")
            # 根据币种设置合适的小数位数
            if base_currency == "DOGE":
                sz_str = "{0:.0f}".format(sz)
            else:
                sz_str = "{0:.5f}".format(sz)
            logger.info(f"卖出策略: 使用 {sz} {base_currency} 进行卖出（约 {trade_amount_usdt:.2f} USDT）")
        
        logger.info(f"设置交易金额: {trade_amount_usdt:.2f} USDT (可用余额: {usdt_balance:.2f} USDT, 类型: {side})")
        
        # 对于卖出信号：先平掉多头持仓，然后做空
        order_id_to_sell = None
        amount_to_sell = None  # 要卖出的币种数量
        if side == "sell":
            # 优先从API获取实际持仓信息
            logger.info(f"🔄 从API获取未平仓的做多持仓...")
            
            # 从API获取实际持仓信息
            order_agent = None
            for agent_id, agent in self._agents.items():
                if agent.name == "Order":
                    order_agent = agent
                    break
            
            long_orders = []
            if order_agent and hasattr(order_agent, 'rest_client'):
                try:
                    # 获取杠杆持仓信息
                    positions = await order_agent.rest_client.get_positions('MARGIN', inst_id)
                    logger.info(f"从API获取持仓信息: {positions}")
                    for pos in positions:
                        pos_side = pos.get('posSide', 'net')
                        availSz = float(pos.get('availPos', '0'))
                        if availSz > 0 and pos_side == 'long':
                            long_orders.append({
                                'position_type': 'long',
                                'size': availSz,
                                'avgPx': float(pos.get('avgPx', 0)),
                                'from_api': True
                            })
                    logger.info(f"✅ 从API获取到做多持仓: {len(long_orders)}个订单")
                except Exception as e:
                    logger.warning(f"从API获取持仓失败: {e}，使用本地记录")
                    if inst_id in self._buy_orders:
                        long_orders = [order for order in self._buy_orders[inst_id] if order.get('position_type') == 'long']
            else:
                logger.warning("未找到OrderAgent或rest_client未初始化，使用本地记录")
                if inst_id in self._buy_orders:
                    long_orders = [order for order in self._buy_orders[inst_id] if order.get('position_type') == 'long']
            
            if long_orders:
                # 找到第一个做多持仓
                matched_order = long_orders[0]
                order_id_to_sell = matched_order.get('order_id', 'API_' + inst_id)
                amount_to_sell = matched_order.get('size', 0) or matched_order.get('buy_amount', 0)
                buy_price = matched_order.get('avgPx', 0) or matched_order.get('buy_price', 0)
                
                if buy_price > 0:
                    order_return = (current_price - buy_price) / buy_price
                    symbol = inst_id.split('-')[0]
                    logger.info(f"✅ 从API获取到做多持仓: 买入价={buy_price:.2f}, 数量={amount_to_sell:.8f} {symbol}, 收益率={order_return*100:.2f}%")
                
                is_short_sell = False
            else:
                # 没有找到做多订单，执行做空操作（杠杆交易支持做空）
                logger.info("未找到未平仓的做多订单，执行做空操作")
                is_short_sell = True
        
        # 如果找到要卖出的订单，使用当前实际持仓数量（而不是买入订单的原始数量）
        if side == "sell" and not is_short_sell and amount_to_sell:
            # 检查收益是否大于手续费（0.2%）
            fee_rate = 0.002  # 0.2% 手续费率
            expected_return = (current_price - buy_price) / buy_price
            if expected_return < fee_rate:
                logger.warning(f"⚠️ 预期收益率 {expected_return*100:.2f}% 小于手续费率 {fee_rate*100:.2f}%，不执行平多操作")
                # 不执行平多操作
                return
            logger.info(f"✅ 预期收益率 {expected_return*100:.2f}% 大于手续费率 {fee_rate*100:.2f}%，执行平多操作")
            
            # 获取当前实际持仓
            # 从交易对中提取币种
            symbol = inst_id.split('-')[0]
            
            # 获取可用余额
            account_info = await self._get_account_info()
            balance = 0.0
            if account_info:
                available_balance = account_info.currencies.get(symbol, {}).get('available', 0)
                try:
                    balance = float(available_balance)
                except (ValueError, TypeError):
                    balance = 0.0
            logger.info(f"当前{symbol}可用余额: {balance:.8f}")
            
            available = balance  # 使用获取的余额
            
            # 使用实际持仓数量和订单数量的较小值
            sz = min(amount_to_sell, available)
            
            # 确保数量精度（现货最小单位为0.00001）
            sz = round(sz, 5)
            # 确保 sz 格式正确，避免科学计数法
            sz_str = "{0:.5f}".format(sz)
            logger.info(f"平多数量: {sz_str} {symbol} (买入订单数量: {amount_to_sell:.8f}, 实际持仓: {available:.8f})")
            
            # 检查最小交易单位
            min_sz = 0.00001  # 最小交易单位
            
            # 检查平仓收益
            # 跳过预期收益检查，由订单智能体处理
            logger.info("跳过预期收益检查，直接执行平多操作")
            
            # 如果平多数量为0或小于最小交易单位，执行做空操作
            if sz <= 0 or sz < min_sz:
                if sz < min_sz:
                    logger.warning(f"⚠️ 平多数量 {sz:.8f} {symbol} 小于最小交易单位 {min_sz} {symbol}，将执行做空操作")
                else:
                    logger.warning("⚠️ 平多数量为0，将执行做空操作")
                is_short_sell = True
        else:
            # 没有找到要卖出的订单，执行做空操作
            logger.warning("未找到未卖出的买入订单，将执行做空操作")
            is_short_sell = True
        
        # 如果是做空操作，设置为固定1 USDT等值的币种
        if side == "sell" and is_short_sell:
            # 从交易对中提取币种
            symbol = inst_id.split('-')[0]
            # 做空时：确保交易金额至少为1 USDT
            min_trade_amount_usdt = 1.0
            if trade_amount_usdt < min_trade_amount_usdt:
                trade_amount_usdt = min_trade_amount_usdt
            # 计算需要的币种数量
            sz = trade_amount_usdt / current_price
            # 确保数量至少为最小交易单位
            min_sz = min_order_sizes.get(inst_id, 0.0001)
            if sz < min_sz:
                sz = min_sz
                # 调整USDT交易金额
                trade_amount_usdt = sz * current_price
            # 确保数量精度
            if base_currency == "DOGE":
                sz = round(sz, 0)
                sz_str = "{0:.0f}".format(sz)
            else:
                sz = round(sz, 5)
                sz_str = "{0:.5f}".format(sz)
            logger.info(f"做空数量: {sz_str} {symbol} (约 {trade_amount_usdt:.2f} USDT)")
            
            # 检查做空订单跟踪器中是否有当前交易对的未平仓的做空订单
            short_orders = []
            if inst_id in self._buy_orders:
                short_orders = [order for order in self._buy_orders[inst_id] if order.get('position_type') == 'short']
            
            # 如果有未平仓的做空订单，先检查收益
            if short_orders:
                # 找到最早的做空订单（FIFO）
                matched_short_order = short_orders[0]
                short_price = matched_short_order.get('sell_price', 0)
                
                if short_price > 0:
                    # 计算做空的预期收益（做空时，价格下跌才盈利）
                    expected_return_short = (short_price - current_price) / short_price
                    logger.info(f"做空预期收益: {expected_return_short * 100:.2f}%")
                    
                    # 检查收益是否大于手续费（0.2%）
                    fee_rate = 0.002  # 0.2% 手续费率
                    if expected_return_short < fee_rate:
                        logger.warning(f"⚠️ 做空预期收益率 {expected_return_short * 100:.2f}% 小于手续费率 {fee_rate * 100:.2f}%，不执行平空操作")
                        # 不执行平空操作，继续执行新的做空操作
                        logger.info("继续执行新的做空操作")
                    else:
                        logger.info(f"✅ 做空预期收益率 {expected_return_short * 100:.2f}% 大于手续费率 {fee_rate * 100:.2f}%，可以执行平空操作")
        
        # 构建订单参数
        # 统一使用杠杆交易模式
        if side == "buy":
            # 买入时，使用杠杆交易模式，sz为USDT金额
            # 确保交易金额至少为1 USDT
            trade_amount_usdt = max(trade_amount_usdt, 1.0)
            # 构建订单参数
            order_params = {
                "inst_id": inst_id,  # 现货产品
                "side": side,
                "ord_type": "market",  # 市价单
                "sz": f"{trade_amount_usdt:.2f}",  # 买入时为USDT金额
                "td_mode": "cross",  # 杠杆交易模式
                "lever": self._leverage,  # 杠杆倍数
                "expected_return": expected_return,  # 预期收益
                "signal_id": signal_id,  # 信号ID
                "price": current_price,  # 当前价格，用于计算订单收益
                "order_id_to_sell": order_id_to_sell,  # 要卖出的订单ID
                "is_short_sell": is_short_sell,  # 是否为做空操作
                "skip_return_check": True,  # 跳过收益率检查
                "tgtCcy": "quote_ccy"  # 按USDT金额下单
            }
        else:
            # 卖出时，使用杠杆交易模式
            # 确保数量至少为最小交易单位0.00001 BTC
            min_sz = 0.00001
            sz_value = float(sz_str)
            if sz_value < min_sz:
                sz_value = min_sz
                sz_str = "{0:.5f}".format(sz_value)
            
            order_params = {
                "inst_id": inst_id,  # 现货产品
                "side": side,
                "ord_type": "market",  # 市价单
                "sz": sz_str,  # 卖出时为BTC数量
                "td_mode": "cross",  # 杠杆交易模式
                "lever": self._leverage,  # 杠杆倍数
                "expected_return": expected_return,  # 预期收益
                "signal_id": signal_id,  # 信号ID
                "price": current_price,  # 当前价格，用于计算订单收益
                "order_id_to_sell": order_id_to_sell,  # 要卖出的订单ID
                "is_short_sell": is_short_sell,  # 是否为做空操作
                "skip_return_check": True  # 跳过收益率检查
            }
        
        # 从交易对中提取币种
        symbol = inst_id.split('-')[0]
        
        # 对于买入信号：先平掉空头持仓，然后做多
        should_close_short = False
        close_short_order_id = None
        close_short_amount = None
        if side == "buy":
            # 优先从API获取实际持仓信息
            logger.info(f"🔄 从API获取未平仓的做空持仓...")
            
            # 从API获取实际持仓信息
            order_agent = None
            for agent_id, agent in self._agents.items():
                if agent.name == "Order":
                    order_agent = agent
                    break
            
            short_orders = []
            if order_agent and hasattr(order_agent, 'rest_client'):
                try:
                    # 获取杠杆持仓信息
                    positions = await order_agent.rest_client.get_positions('MARGIN', inst_id)
                    logger.info(f"从API获取持仓信息: {positions}")
                    for pos in positions:
                        pos_side = pos.get('posSide', 'net')
                        availSz = float(pos.get('availPos', '0'))
                        if availSz > 0 and pos_side == 'short':
                            short_orders.append({
                                'position_type': 'short',
                                'size': availSz,
                                'avgPx': float(pos.get('avgPx', 0)),
                                'from_api': True
                            })
                    logger.info(f"✅ 从API获取到做空持仓: {len(short_orders)}个订单")
                except Exception as e:
                    logger.warning(f"从API获取持仓失败: {e}，使用本地记录")
                    if inst_id in self._buy_orders:
                        short_orders = [order for order in self._buy_orders[inst_id] if order.get('position_type') == 'short']
            else:
                logger.warning("未找到OrderAgent或rest_client未初始化，使用本地记录")
                if inst_id in self._buy_orders:
                    short_orders = [order for order in self._buy_orders[inst_id] if order.get('position_type') == 'short']
            
            if short_orders:
                # 找到第一个做空持仓
                matched_short_order = short_orders[0]
                short_order_id = matched_short_order.get('order_id', 'API_' + inst_id)
                short_amount = matched_short_order.get('size', 0) or matched_short_order.get('sell_amount', 0)
                short_price = matched_short_order.get('avgPx', 0) or matched_short_order.get('sell_price', 0)
                
                if short_price > 0:
                    # 计算平空的预期收益（做空时，价格下跌才盈利）
                    order_return = (short_price - current_price) / short_price
                    logger.info(f"✅ 从API获取到做空持仓: 卖出价={short_price:.2f}, 数量={short_amount:.8f} {symbol}, 收益率={order_return*100:.2f}%")
                    
                    # 检查收益是否大于手续费（0.2%）
                    fee_rate = 0.002  # 0.2% 手续费率
                    if order_return < fee_rate:
                        logger.warning(f"⚠️ 平空预期收益率 {order_return*100:.2f}% 小于手续费率 {fee_rate*100:.2f}%，不执行平空操作")
                        # 不执行平空操作，直接做多
                        logger.info("直接执行做多操作")
                    else:
                        logger.info(f"✅ 平空预期收益率 {order_return*100:.2f}% 大于手续费率 {fee_rate*100:.2f}%，执行平空操作")
                        should_close_short = True
                        close_short_order_id = short_order_id
                        close_short_amount = short_amount
        
        # 对于卖出信号：先检查是否有未平仓的订单
        if side == "sell":
            # 检查是否有未平仓的订单
            if is_short_sell:
                # 做空操作：优先从API获取实际持仓信息
                logger.info(f"🔄 从API获取未平仓的做空持仓...")
                
                # 从API获取实际持仓信息
                order_agent = None
                for agent_id, agent in self._agents.items():
                    if agent.name == "Order":
                        order_agent = agent
                        break
                
                short_orders = []
                if order_agent and hasattr(order_agent, 'rest_client'):
                    try:
                        # 获取杠杆持仓信息
                        positions = await order_agent.rest_client.get_positions('MARGIN', inst_id)
                        logger.info(f"从API获取持仓信息: {positions}")
                        for pos in positions:
                            pos_side = pos.get('posSide', 'net')
                            availSz = float(pos.get('availPos', '0'))
                            if availSz > 0 and pos_side == 'short':
                                short_orders.append({
                                    'position_type': 'short',
                                    'size': availSz,
                                    'avgPx': float(pos.get('avgPx', 0)),
                                    'from_api': True
                                })
                        logger.info(f"✅ 从API获取到做空持仓: {len(short_orders)}个订单")
                    except Exception as e:
                        logger.warning(f"从API获取持仓失败: {e}，使用本地记录")
                        if inst_id in self._buy_orders:
                            short_orders = [order for order in self._buy_orders[inst_id] if order.get('position_type') == 'short']
                else:
                    logger.warning("未找到OrderAgent或rest_client未初始化，使用本地记录")
                    if inst_id in self._buy_orders:
                        short_orders = [order for order in self._buy_orders[inst_id] if order.get('position_type') == 'short']
                
                # 如果有未平仓的做空订单，先检查收益
                if short_orders:
                    # 找到第一个做空持仓
                    matched_short_order = short_orders[0]
                    short_price = matched_short_order.get('avgPx', 0) or matched_short_order.get('sell_price', 0)
                    
                    if short_price > 0:
                        # 计算做空的预期收益（做空时，价格下跌才盈利）
                        expected_return_short = (short_price - current_price) / short_price
                        logger.info(f"从API获取做空持仓，预期收益: {expected_return_short * 100:.2f}%")
                        
                        # 检查收益是否大于手续费（0.2%）
                        fee_rate = 0.002  # 0.2% 手续费率
                        if expected_return_short < fee_rate:
                            logger.warning(f"⚠️ 做空预期收益率 {expected_return_short * 100:.2f}% 小于手续费率 {fee_rate * 100:.2f}%，不执行平空操作")
                            # 不执行平空操作，继续执行新的做空操作
                            logger.info("继续执行新的做空操作")
                        else:
                            logger.info(f"✅ 做空预期收益率 {expected_return_short * 100:.2f}% 大于手续费率 {fee_rate * 100:.2f}%，可以执行平空操作")
                else:
                    # 未找到未平仓的做空订单，返回到开仓逻辑（做空）
                    logger.info("未找到未平仓的做空订单，执行开仓做空操作")
            else:
                # 平多操作：优先从API获取实际持仓信息
                logger.info(f"🔄 从API获取未平仓的做多持仓...")
                
                # 从API获取实际持仓信息
                order_agent = None
                for agent_id, agent in self._agents.items():
                    if agent.name == "Order":
                        order_agent = agent
                        break
                
                long_orders = []
                if order_agent and hasattr(order_agent, 'rest_client'):
                    try:
                        # 获取杠杆持仓信息
                        positions = await order_agent.rest_client.get_positions('MARGIN', inst_id)
                        logger.info(f"从API获取持仓信息: {positions}")
                        for pos in positions:
                            pos_side = pos.get('posSide', 'net')
                            availSz = float(pos.get('availPos', '0'))
                            if availSz > 0 and pos_side == 'long':
                                long_orders.append({
                                    'position_type': 'long',
                                    'size': availSz,
                                    'avgPx': float(pos.get('avgPx', 0)),
                                    'from_api': True
                                })
                        logger.info(f"✅ 从API获取到做多持仓: {len(long_orders)}个订单")
                    except Exception as e:
                        logger.warning(f"从API获取持仓失败: {e}，使用本地记录")
                        if inst_id in self._buy_orders:
                            long_orders = [order for order in self._buy_orders[inst_id] if order.get('position_type') == 'long']
                else:
                    logger.warning("未找到OrderAgent或rest_client未初始化，使用本地记录")
                    if inst_id in self._buy_orders:
                        long_orders = [order for order in self._buy_orders[inst_id] if order.get('position_type') == 'long']
                
                # 如果有未平仓的做多订单，先检查收益
                if long_orders:
                    # 找到第一个做多持仓
                    matched_long_order = long_orders[0]
                    buy_price = matched_long_order.get('avgPx', 0) or matched_long_order.get('buy_price', 0)
                    
                    if buy_price > 0:
                        # 计算平多的预期收益（做多时，价格上涨才盈利）
                        expected_return_long = (current_price - buy_price) / buy_price
                        logger.info(f"平多预期收益: {expected_return_long * 100:.2f}%")
                        
                        # 检查收益是否大于手续费（0.2%）
                        fee_rate = 0.002  # 0.2% 手续费率
                        if expected_return_long < fee_rate:
                            logger.warning(f"⚠️ 平多预期收益率 {expected_return_long * 100:.2f}% 小于手续费率 {fee_rate * 100:.2f}%，不执行平多操作")
                            # 不执行平多操作，返回到开仓逻辑
                            logger.info("未找到合适的平多订单，执行开仓逻辑")
                            # 切换到开仓逻辑：如果是sell信号但没有做多订单，应该考虑是否要做空
                            is_short_sell = True
                            side = "sell"
                            position_type = "short"
                        else:
                            logger.info(f"✅ 平多预期收益率 {expected_return_long * 100:.2f}% 大于手续费率 {fee_rate * 100:.2f}%，执行平多操作")
                else:
                    # 未找到未平仓的做多订单，返回到开仓逻辑（考虑做空）
                    logger.info("未找到未平仓的做多订单，执行开仓逻辑（考虑做空）")
                    # 切换到开仓逻辑：如果是sell信号但没有做多订单，应该考虑是否要做空
                    is_short_sell = True
                    side = "sell"
                    position_type = "short"
        
        if side == "buy" and not should_close_short:
            logger.info(f"准备执行市价买入: {sz_str} USDT")
        elif side == "buy" and should_close_short:
            logger.info(f"准备执行市价平空: {close_short_amount:.8f} {symbol}，然后做多")
        elif is_short_sell:
            logger.info(f"准备执行市价做空: {sz_str} {symbol}")
        else:
            logger.info(f"准备执行市价平多: {sz_str} {symbol}")
        
        # ========== 先确定持仓类型 ==========
        position_type = 'long'
        if side == 'buy':
            if should_close_short:
                position_type = 'close_short'
            else:
                position_type = 'long'
        elif side == 'sell':
            if is_short_sell:
                position_type = 'short'
            else:
                # 平多，不占用新保证金
                position_type = 'close_long'
        
        # ========== 添加预期收益检查（先检查预期收益） ==========
        # 1. 平多操作的收益检查（实际收益）
        if side == 'sell' and not is_short_sell and amount_to_sell:
            fee_rate = 0.002
            expected_return = (current_price - buy_price) / buy_price
            return_ok = await self._check_expected_return(expected_return, fee_rate)
            if not return_ok:
                logger.warning(f"⚠️ 预期收益不足，取消平多操作")
                return
        
        # 2. 开仓操作的预期收益检查（基于多个指标综合计算，自动调整权重，多空方向由预期收益大小决定）
        if position_type == 'long' or position_type == 'short':
            # 获取策略信号的详情，包括多个指标
            signal_details = signal.get('details', {})
            spring_drift = signal_details.get('spring_drift', 0)
            angular_momentum = signal_details.get('angular_momentum', 0)
            pairing_gap = signal_details.get('pairing_gap', 0)
            phase_sync = signal_details.get('phase_sync', 0)
            
            # 计算做多和做空两个方向的各指标贡献值
            long_drift = max(0, spring_drift)
            long_momentum = max(0, angular_momentum)
            long_gap = max(0, pairing_gap)
            long_sync = max(0, phase_sync)
            
            short_drift = max(0, -spring_drift)
            short_momentum = max(0, -angular_momentum)
            short_gap = max(0, -pairing_gap)
            short_sync = max(0, -phase_sync)
            
            # 计算做多的总贡献值和权重
            long_total = long_drift + long_momentum + long_gap + long_sync
            if long_total > 0:
                long_drift_w = long_drift / long_total
                long_momentum_w = long_momentum / long_total
                long_gap_w = long_gap / long_total
                long_sync_w = long_sync / long_total
            else:
                long_drift_w, long_momentum_w, long_gap_w, long_sync_w = 0.4, 0.3, 0.2, 0.1
            
            # 计算做空的总贡献值和权重
            short_total = short_drift + short_momentum + short_gap + short_sync
            if short_total > 0:
                short_drift_w = short_drift / short_total
                short_momentum_w = short_momentum / short_total
                short_gap_w = short_gap / short_total
                short_sync_w = short_sync / short_total
            else:
                short_drift_w, short_momentum_w, short_gap_w, short_sync_w = 0.4, 0.3, 0.2, 0.1
            
            # 计算预期收益（使用固定权重：漂移值40% + 角动量30% + 配对能隙20% + 相位同步10%）
            fee_rate = 0.002
            long_expected_return = (
                long_drift * 0.4 +
                long_momentum * 0.3 +
                long_gap * 0.2 +
                long_sync * 0.1
            )
            short_expected_return = (
                short_drift * 0.4 +
                short_momentum * 0.3 +
                short_gap * 0.2 +
                short_sync * 0.1
            )
            
            # 记录各方向的预期收益
            logger.info(f"多空预期收益对比: 做多={long_expected_return*100:.4f}%, 做空={short_expected_return*100:.4f}%")
            logger.info(f"做多预期收益: 漂移={long_drift:.6f}(权重{long_drift_w:.2%}), 角动量={long_momentum:.6f}(权重{long_momentum_w:.2%}), 配对能隙={long_gap:.6f}(权重{long_gap_w:.2%}), 相位同步={long_sync:.6f}(权重{long_sync_w:.2%})")
            logger.info(f"做空预期收益: 漂移={short_drift:.6f}(权重{short_drift_w:.2%}), 角动量={short_momentum:.6f}(权重{short_momentum_w:.2%}), 配对能隙={short_gap:.6f}(权重{short_gap_w:.2%}), 相位同步={short_sync:.6f}(权重{short_sync_w:.2%})")
            
            # 平仓/反向检查：如果持仓方向的预期收益值变小或多空预期收益对比出现反向，则平仓或反向
            # 获取当前交易对的做多和做空订单（优先使用API返回的持仓信息）
            long_orders = []
            short_orders = []
            
            # 从API获取实际持仓信息
            order_agent = None
            for agent_id, agent in self._agents.items():
                if agent.name == "Order":
                    order_agent = agent
                    break
            
            if order_agent and hasattr(order_agent, 'rest_client'):
                try:
                    # 获取杠杆持仓信息
                    positions = await order_agent.rest_client.get_positions('MARGIN', inst_id)
                    logger.info(f"从API获取持仓信息: {positions}")
                    for pos in positions:
                        pos_side = pos.get('posSide', 'net')
                        availSz = float(pos.get('availPos', '0'))
                        if availSz > 0:
                            if pos_side == 'long':
                                long_orders.append({
                                    'position_type': 'long',
                                    'size': availSz,
                                    'avgPx': float(pos.get('avgPx', 0)),
                                    'from_api': True
                                })
                            elif pos_side == 'short':
                                short_orders.append({
                                    'position_type': 'short',
                                    'size': availSz,
                                    'avgPx': float(pos.get('avgPx', 0)),
                                    'from_api': True
                                })
                    logger.info(f"✅ 从API获取到持仓: 做多={len(long_orders)}个订单, 做空={len(short_orders)}个订单")
                except Exception as e:
                    logger.warning(f"从API获取持仓失败: {e}，使用本地记录")
                    long_orders = [o for o in self._buy_orders.get(inst_id, []) if o.get('position_type') == 'long']
                    short_orders = [o for o in self._buy_orders.get(inst_id, []) if o.get('position_type') == 'short']
            else:
                logger.warning("未找到OrderAgent或rest_client未初始化，使用本地记录")
                long_orders = [o for o in self._buy_orders.get(inst_id, []) if o.get('position_type') == 'long']
                short_orders = [o for o in self._buy_orders.get(inst_id, []) if o.get('position_type') == 'short']
            
            if long_orders:
                last_long_return = self._last_expected_returns.get(f"{inst_id}_long", 0)
                if last_long_return > 0 and long_expected_return < last_long_return * 0.8:
                    logger.warning(f"⚠️ 做多持仓方向收益下降: 上次={last_long_return*100:.4f}%, 当前={long_expected_return*100:.4f}%")
                    logger.info(f"🔄 执行平多操作...")
                    close_side = "sell"
                    close_pos_type = "long"
                    await self._execute_close_position(order_params, close_side, close_pos_type, inst_id, signal, market_data)
                    # 移除return，继续执行开仓逻辑
                    
            if short_orders:
                last_short_return = self._last_expected_returns.get(f"{inst_id}_short", 0)
                if last_short_return > 0 and short_expected_return < last_short_return * 0.8:
                    logger.warning(f"⚠️ 做空持仓方向收益下降: 上次={last_short_return*100:.4f}%, 当前={short_expected_return*100:.4f}%")
                    logger.info(f"🔄 执行平空操作...")
                    close_side = "buy"
                    close_pos_type = "short"
                    await self._execute_close_position(order_params, close_side, close_pos_type, inst_id, signal, market_data)
                    # 移除return，继续执行开仓逻辑
                    
            last_long_vs_short = self._last_expected_returns.get(f"{inst_id}_long_vs_short", 0)
            current_long_vs_short = long_expected_return - short_expected_return
            if last_long_vs_short > fee_rate and current_long_vs_short < -fee_rate:
                logger.warning(f"⚠️ 多空方向反转: 上次做多优势={last_long_vs_short*100:.4f}%, 当前做空优势={-current_long_vs_short*100:.4f}%")
                if long_orders:
                    logger.info(f"🔄 执行平多并做空操作...")
                    close_side = "sell"
                    close_pos_type = "long"
                    await self._execute_close_position(order_params, close_side, close_pos_type, inst_id, signal, market_data)
                    # 移除return，继续执行开仓逻辑
                    
            if last_long_vs_short < -fee_rate and current_long_vs_short > fee_rate:
                logger.warning(f"⚠️ 多空方向反转: 上次做空优势={-last_long_vs_short*100:.4f}%, 当前做多优势={current_long_vs_short*100:.4f}%")
                if short_orders:
                    logger.info(f"🔄 执行平空并做多操作...")
                    close_side = "buy"
                    close_pos_type = "short"
                    await self._execute_close_position(order_params, close_side, close_pos_type, inst_id, signal, market_data)
                    # 移除return，继续执行开仓逻辑
            
            self._last_expected_returns[f"{inst_id}_long"] = long_expected_return
            self._last_expected_returns[f"{inst_id}_short"] = short_expected_return
            self._last_expected_returns[f"{inst_id}_long_vs_short"] = current_long_vs_short
            
            # 根据预期收益大小决定交易方向
            if long_expected_return >= short_expected_return and long_expected_return >= 0.003:  # 大于0.3%收益
                chosen_direction = 'long'
                expected_return = long_expected_return
                side = "buy"  # 更新交易方向为做多
                position_type = "long"  # 更新持仓类型为做多
                logger.info(f"✅ 选择做多方向，预期收益率={expected_return*100:.4f}%，大于0.3%收益")
            elif short_expected_return > long_expected_return and short_expected_return >= 0.003:  # 大于0.3%收益
                chosen_direction = 'short'
                expected_return = short_expected_return
                side = "sell"  # 更新交易方向为做空
                position_type = "short"  # 更新持仓类型为做空
                logger.info(f"✅ 选择做空方向，预期收益率={expected_return*100:.4f}%，大于0.3%收益")
            else:
                max_return = max(long_expected_return, short_expected_return)
                logger.warning(f"⚠️ 预期收益不足({max_return*100:.4f}%)，小于0.3%收益，取消开仓操作")
                return
        
        # ========== 添加保证金检查 ==========
        # 如果不是平仓操作，检查保证金
        if position_type != 'close_long' and position_type != 'close_short':
            margin_available = await self._check_margin_available(trade_amount_usdt, inst_id, position_type)
            if not margin_available:
                logger.warning(f"⚠️ 保证金不足 [{inst_id}]，取消交易")
                return
        
        # 检查交易金额（已移除交易金额限制）
        try:
            # 设定单次交易金额为1.0 USDT，适应当前账户资金水平
            trade_amount = trade_amount_usdt  # 使用之前计算的交易金额
            
            # 根据订单参数中的交易模式显示
            td_mode = order_params.get("td_mode", "cross")
            trade_mode_str = "杠杆交易" if td_mode != "cash" else "现金交易"
            logger.info(f"交易金额: {trade_amount:.2f} USDT ({trade_mode_str})")
            logger.info(f"累计交易: {self._total_trade_amount:.2f} USDT")
            logger.info(f"交易模式: {trade_mode_str}")
        except Exception as e:
            logger.error(f"计算交易金额失败: {e}")
            return
        
        # 交易前：账户同步和订单核实
        try:
            # 1. 同步账户余额
            logger.info("🔄 交易前：同步账户余额和订单状态...")
            
            # 2. 核实平多操作的持仓数量（跳过做空操作的持仓检查）
            if side == "sell" and order_id_to_sell and not is_short_sell:
                # 从order_agent获取最新的交易记录
                if hasattr(order_agent, "_trade_history"):
                    # 查找要卖出的买入订单
                    buy_trade = None
                    for trade in order_agent._trade_history:
                        if trade.get('trade_id') == order_id_to_sell and trade.get('side') == 'buy' and trade.get('state') == 'filled':
                            buy_trade = trade
                            break
                    
                    if buy_trade:
                        # 检查实际BTC持仓
                        # 获取账户信息
                        account_info = await self._get_account_info()
                        if account_info:
                            btc_available = account_info.currencies.get('BTC', {}).get('available', Decimal('0'))
                            btc_available_float = float(btc_available)
                            order_amount = buy_trade.get('filled_size', 0)
                        
                        if account_info and 'btc_available_float' in locals() and 'order_amount' in locals():
                            if btc_available_float < order_amount:
                                logger.warning(f"⚠️ 实际BTC持仓不足: 可用 {btc_available_float:.8f} BTC, 订单数量 {order_amount:.8f} BTC")
                                logger.warning(f"⚠️ 调整平多数量为实际可用持仓: {btc_available_float:.8f} BTC")
                                
                                # 更新卖出数量
                                sz = btc_available_float
                                # 检查调整后的卖出数量是否为0
                                if sz <= 0:
                                    logger.warning("⚠️ 调整后的平多数量为0，跳过本次平多操作")
                                    return
                                # 检查调整后的卖出数量是否小于 OKX API 要求的最小交易数量
                                min_sz = 0.00001  # BTC 最小交易单位
                                if sz < min_sz:
                                    logger.warning(f"⚠️ 调整后的平多数量 {sz:.8f} BTC 小于最小交易单位 {min_sz} BTC，跳过本次平多操作")
                                    return
                                # 保留5位小数（BTC 最小交易单位为 0.00001）
                                sz = round(sz, 5)
                                sz_str = "{0:.5f}".format(sz)
                                order_params["sz"] = sz_str
                                
                                logger.info(f"✅ 已调整平多数量: {sz_str} BTC")
                            else:
                                logger.info(f"✅ 持仓充足: 可用 {btc_available_float:.8f} BTC, 订单数量 {order_amount:.8f} BTC")
                        else:
                            logger.info("⚠️ 无法获取账户信息，跳过持仓检查")
                    else:
                        logger.warning(f"⚠️ 未找到要平多的买入订单: {order_id_to_sell}")
            elif is_short_sell:
                logger.info("🔄 做空操作：跳过持仓检查，直接执行做空")
            
            logger.info("✅ 交易前账户同步和订单核实完成")
        except Exception as e:
            logger.error(f"❌ 交易前账户同步失败: {e}")
        
        # 执行交易
        try:
            # 如果需要平空，先执行平空订单
            close_short_success = False
            if side == "buy" and should_close_short:
                logger.info(f"🔄 先执行平空订单: {close_short_amount:.8f} {symbol}")
                
                # 创建平空订单参数
                close_short_order_params = order_params.copy()
                close_short_order_params["side"] = "buy"
                close_short_order_params["sz"] = "{0:.8f}".format(close_short_amount)
                
                logger.info(f"准备执行平空交易，订单参数: {close_short_order_params}")
                close_short_result = await order_agent.place_order(close_short_order_params)
                logger.info(f"平空下单结果: {close_short_result}")
                
                if close_short_result.get("success"):
                    close_short_order_id = close_short_result.get('order_id')
                    logger.info(f"✅ 平空执行成功: 订单ID {close_short_order_id}")
                    close_short_success = True
                    
                    # 记录平空交易
                    try:
                        # 平空逻辑：找到对应的做空订单并计算盈亏
                        logger.info(f"🔄 开始记录平空交易，查找对应的做空订单...")
                        
                        # 从买入订单跟踪器中找到当前交易对的最早的做空订单（FIFO）
                        matched_short_order = None
                        if inst_id in self._buy_orders and self._buy_orders[inst_id]:
                            for i, order in enumerate(self._buy_orders[inst_id]):
                                if order.get('position_type') == 'short':
                                    matched_short_order = order
                                    # 从列表中移除该订单
                                    self._buy_orders[inst_id].pop(i)
                                    break
                        else:
                            logger.warning(f"⚠️ 交易对 {inst_id} 没有做空订单记录")
                        
                        if matched_short_order:
                            # 获取API返回的真实盈亏（从成交订单中获取）
                            api_pnl = result.get('pnl', 0.0) if isinstance(result, dict) else 0.0
                            
                            # 如果API pnl为0，使用本地计算作为备选
                            if api_pnl == 0.0:
                                sell_price = matched_short_order['sell_price']
                                sell_amount = matched_short_order['sell_amount']
                                actual_buy_amount = min(close_short_amount, sell_amount)
                                profit = (sell_price - current_price) * actual_buy_amount
                                logger.warning(f"⚠️ API未返回pnl，使用本地计算: {profit:.4f} USDT")
                            else:
                                profit = api_pnl
                            
                            # 更新统计信息
                            self._total_pnl += profit
                            self._total_trades += 1
                            if profit > 0:
                                self._winning_trades += 1
                            
                            # 记录平空 - 盈利增长管理器会自动更新
                            profit_growth_manager.record_trade('buy', current_price, actual_buy_amount, profit)
                            logger.info(f"✅ 已记录平空交易到盈利增长管理器，盈利: {profit:.4f} USDT (API pnl: {api_pnl:.4f})")
                            
                            # 更新该交易对的收益和动态保证金限制
                            self._update_symbol_profit(inst_id, profit)
                            
                            # 记录盈亏信息
                            win_rate = (self._winning_trades / self._total_trades * 100) if self._total_trades > 0 else 0
                            logger.info(f"📊 交易统计: 总交易={self._total_trades}, 盈利交易={self._winning_trades}, 胜率={win_rate:.2f}%, 总盈亏={self._total_pnl:.4f} USDT")
                            logger.info(f"✅ 平空成功: API盈亏={api_pnl:.4f} USDT, 本地计算盈亏={profit:.4f} USDT")
                        else:
                            # 没有找到对应的做空订单，直接记录
                            profit_growth_manager.record_trade('buy', current_price, close_short_amount, 0)
                            logger.warning(f"⚠️ 未找到对应的做空订单，直接记录平空交易")
                    except Exception as e:
                        logger.error(f"记录平空交易失败: {e}")
                        import traceback
                        logger.error(f"详细错误信息: {traceback.format_exc()}")
                else:
                    logger.error(f"❌ 平空执行失败，跳过做多操作")
                    return
            
            # 执行主交易（买入或卖出）
            if should_close_short and not close_short_success:
                logger.warning("⚠️ 平空未成功，跳过主交易")
                return
            
            logger.info(f"准备执行主交易，订单参数: {order_params}")
            result = await order_agent.place_order(order_params)
            logger.info(f"下单结果: {result}")
            if result.get("success"):
                order_id = result.get('order_id')
                logger.info(f"✅ 交易执行成功: 订单ID {order_id}")
                
                # 记录交易到盈利增长管理器和买入订单跟踪器
                try:
                    if side == "buy":
                        # 做多逻辑：记录买入 - 盈利增长管理器会自动更新平均买入价格
                        sz = float(order_params.get('sz', 0))
                        # 计算买入的BTC数量（买入时sz是USDT金额）
                        btc_amount = sz / current_price
                        profit_growth_manager.record_trade('buy', current_price, btc_amount)
                        logger.info(f"✅ 已记录买入交易到盈利增长管理器: {btc_amount:.8f} BTC @ {current_price:.2f} USDT")
                        
                        # 将买入订单添加到跟踪列表（做多）
                        buy_order = {
                            'order_id': order_id,
                            'buy_price': current_price,
                            'buy_amount': btc_amount,
                            'buy_time': datetime.now().isoformat(),
                            'inst_id': inst_id,
                            'position_type': 'long'  # 标记为做多仓位
                        }
                        # 按交易对分组存储
                        if inst_id not in self._buy_orders:
                            self._buy_orders[inst_id] = []
                        self._buy_orders[inst_id].append(buy_order)
                        logger.info(f"✅ 已记录做多买入订单到跟踪器: 订单ID={order_id}, 价格={current_price:.2f}, 数量={btc_amount:.8f}, 交易对={inst_id}")
                        
                    elif side == "sell":
                        sz = float(order_params.get('sz', 0))
                        if is_short_sell:
                            # 做空逻辑：记录做空 - 盈利增长管理器会自动更新平均卖出价格
                            profit_growth_manager.record_trade('short', current_price, sz)
                            logger.info(f"✅ 已记录做空交易到盈利增长管理器: {sz:.8f} BTC @ {current_price:.2f} USDT")
                            
                            # 将做空订单添加到跟踪列表（做空）
                            short_order = {
                                'order_id': order_id,
                                'sell_price': current_price,
                                'sell_amount': sz,
                                'sell_time': datetime.now().isoformat(),
                                'inst_id': inst_id,
                                'position_type': 'short'  # 标记为做空仓位
                            }
                            # 按交易对分组存储
                            if inst_id not in self._buy_orders:
                                self._buy_orders[inst_id] = []
                            self._buy_orders[inst_id].append(short_order)
                            logger.info(f"✅ 已记录做空订单到跟踪器: 订单ID={order_id}, 价格={current_price:.2f}, 数量={sz:.8f}, 交易对={inst_id}")
                        else:
                            # 平多逻辑：找到对应的做多买入订单并计算盈亏
                            logger.info(f"🔄 开始平多操作，查找对应的做多买入订单...")
                            
                            # 从买入订单跟踪器中找到当前交易对的最早的做多订单（FIFO）
                            matched_buy_order = None
                            if inst_id in self._buy_orders and self._buy_orders[inst_id]:
                                for i, order in enumerate(self._buy_orders[inst_id]):
                                    if order.get('position_type') == 'long':
                                        matched_buy_order = order
                                        # 从列表中移除该订单
                                        self._buy_orders[inst_id].pop(i)
                                        break
                            else:
                                logger.warning(f"⚠️ 交易对 {inst_id} 没有做多订单记录")
                            
                            if matched_buy_order:
                                # 获取API返回的真实盈亏（从成交订单中获取）
                                api_pnl = result.get('pnl', 0.0) if isinstance(result, dict) else 0.0
                                
                                # 如果API pnl为0，使用本地计算作为备选
                                if api_pnl == 0.0:
                                    buy_price = matched_buy_order['buy_price']
                                    buy_amount = matched_buy_order['buy_amount']
                                    actual_sell_amount = min(sz, buy_amount)
                                    profit = (current_price - buy_price) * actual_sell_amount
                                    logger.warning(f"⚠️ API未返回pnl，使用本地计算: {profit:.4f} USDT")
                                else:
                                    profit = api_pnl
                                
                                # 更新统计信息
                                self._total_pnl += profit
                                self._total_trades += 1
                                if profit > 0:
                                    self._winning_trades += 1
                                
                                # 记录平多 - 盈利增长管理器会自动更新上次卖出价格和盈利
                                profit_growth_manager.record_trade('sell', current_price, actual_sell_amount, profit)
                                logger.info(f"✅ 已记录平多交易到盈利增长管理器，盈利: {profit:.4f} USDT (API pnl: {api_pnl:.4f})")
                                
                                # 更新该交易对的收益和动态保证金限制
                                self._update_symbol_profit(inst_id, profit)
                                
                                # 记录盈亏信息
                                win_rate = (self._winning_trades / self._total_trades * 100) if self._total_trades > 0 else 0
                                logger.info(f"📊 交易统计: 总交易={self._total_trades}, 盈利交易={self._winning_trades}, 胜率={win_rate:.2f}%, 总盈亏={self._total_pnl:.4f} USDT")
                                logger.info(f"✅ 平多成功: API盈亏={api_pnl:.4f} USDT, 本地计算盈亏={profit:.4f} USDT")
                            else:
                                # 没有找到对应的做多订单，直接记录
                                profit_growth_manager.record_trade('sell', current_price, sz, 0)
                                logger.warning(f"⚠️ 未找到对应的做多买入订单，直接记录平多交易")
                except Exception as e:
                    logger.error(f"记录交易失败: {e}")
                    import traceback
                    logger.error(f"详细错误信息: {traceback.format_exc()}")
                
                # 更新总交易金额
                try:
                    # 设定单次交易金额为1.0 USDT
                    trade_amount = trade_amount_usdt
                    self._total_trade_amount += trade_amount
                    logger.info(f"✅ 总交易金额更新: {self._total_trade_amount:.2f} USDT")
                    # 触发订单事件，通知订单智能体处理订单
                    await self.event_bus.publish_async(
                        Event(
                            type=EventType.ORDER_EVENT,
                            source=self.agent_id,
                            data={"order": {"ordId": order_id, "instId": order_params.get('inst_id'), "side": order_params.get('side'), "ordType": order_params.get('ord_type'), "sz": order_params.get('sz'), "state": "filled"}},
                        )
                    )
                    # 将信号标记为已处理
                    if hasattr(self, '_processed_signals'):
                        logger.info(f"信号已标记为已处理: {signal_key}")
                except Exception as e:
                    logger.error(f"更新交易金额失败: {e}")
                
                # 交易后：账户同步和订单状态更新
                try:
                    logger.info("🔄 交易后：同步账户余额和更新订单状态...")
                    
                    # 1. 等待订单完全成交（给OKX API一点时间处理）
                    import asyncio
                    await asyncio.sleep(2)
                    
                    # 2. 重新获取账户信息，确保数据最新
                    account_info = await self._get_account_info()
                    if account_info:
                        btc_position = account_info.currencies.get('BTC', {})
                        usdt_position = account_info.currencies.get('USDT', {})
                        logger.info(f"✅ 交易后BTC持仓: 可用={btc_position.get('available', 0):.8f}")
                        logger.info(f"✅ 交易后USDT余额: 可用={usdt_position.get('available', 0):.2f}")
                    
                    # 3. 同步订单状态（通过API获取最新订单信息）
                    if order_agent:
                        # 同步账户和订单状态
                        await order_agent.sync_account_and_orders()
                        logger.info("✅ 订单状态已同步")
                    
                    # 4. 如果是平多操作，标记对应的买入订单为已卖出
                    if side == "sell" and order_id_to_sell and not is_short_sell:
                        # 查找并更新对应的买入订单状态
                        if order_agent and hasattr(order_agent, "_trade_history"):
                            for trade in order_agent._trade_history:
                                if trade.get('trade_id') == order_id_to_sell:
                                    trade['state'] = 'sold'
                                    trade['sold_time'] = datetime.now().isoformat()
                                    trade['sold_price'] = current_price
                                    logger.info(f"✅ 已标记买入订单为已卖出: {order_id_to_sell}")
                                    break
                        
                        # 记录平多交易，关联对应的买入订单
                        if order_agent and hasattr(order_agent, "_trade_history"):
                            sell_trade = {
                                'trade_id': order_id,
                                'side': 'sell',
                                'price': current_price,
                                'size': sz,
                                'filled_size': sz,
                                'state': 'filled',
                                'create_time': datetime.now().isoformat(),
                                'inst_id': 'BTC-USDT',
                                'order_id_to_sell': order_id_to_sell,
                                'profit': (current_price - buy_price) * sz if 'buy_price' in locals() else 0
                            }
                            order_agent._trade_history.append(sell_trade)
                            logger.info(f"✅ 已记录平多交易: {sell_trade['trade_id']}")
                    # 5. 如果是做空操作，记录做空交易
                    elif side == "sell" and is_short_sell:
                        # 记录做空交易
                        if order_agent and hasattr(order_agent, "_trade_history"):
                            short_trade = {
                                'trade_id': order_id,
                                'side': 'short',
                                'price': current_price,
                                'size': sz,
                                'filled_size': sz,
                                'state': 'filled',
                                'create_time': datetime.now().isoformat(),
                                'inst_id': 'BTC-USDT',
                                'is_short': True
                            }
                            order_agent._trade_history.append(short_trade)
                            logger.info(f"✅ 已记录做空交易: {short_trade['trade_id']}")
                    # 6. 如果是买入操作，记录买入交易
                    elif side == "buy":
                        # 记录买入交易
                        if order_agent and hasattr(order_agent, "_trade_history"):
                            buy_trade = {
                                'trade_id': order_id,
                                'side': 'buy',
                                'price': current_price,
                                'size': sz,
                                'filled_size': sz,
                                'state': 'filled',
                                'create_time': datetime.now().isoformat(),
                                'inst_id': 'BTC-USDT'
                            }
                            order_agent._trade_history.append(buy_trade)
                            logger.info(f"✅ 已记录买入交易: {buy_trade['trade_id']}")
                    
                    # 7. 保存订单状态
                    if order_agent and hasattr(order_agent, "_save_state"):
                        order_agent._save_state()
                        logger.info("✅ 订单状态已保存")
                    
                    logger.info("✅ 交易后账户同步和订单状态更新完成")
                except Exception as e:
                    logger.error(f"❌ 交易后账户同步失败: {e}")
            else:
                logger.error(f"❌ 交易执行失败: {result.get('error')}")
                # 交易失败，检查是否需要挂单
                logger.info("交易失败，尝试挂单操作")
                
                # 检查挂单收益是否大于手续费率（0.2%）
                fee_rate = 0.002  # 双向手续费率 0.2%
                # 检查API返回的收益率是否正增长且大于手续费
                if expected_return > 0 and expected_return >= fee_rate:
                    logger.info(f"挂单收益 {expected_return * 100:.2f}% 是正增长且大于手续费 {fee_rate * 100:.2f}%，执行挂单")
                    
                    # 构建挂单参数
                    limit_order_params = order_params.copy()
                    limit_order_params['ord_type'] = 'limit'  # 限价单
                    limit_order_params['price'] = str(current_price)  # 挂单价格
                    
                    try:
                        # 执行挂单
                        limit_result = await order_agent.place_order(limit_order_params)
                        if limit_result.get("success"):
                            limit_order_id = limit_result.get('order_id')
                            logger.info(f"✅ 挂单成功: 订单ID {limit_order_id}")
                            
                            # 触发订单事件，通知订单智能体处理订单
                            await self.event_bus.publish_async(
                                Event(
                                    type=EventType.ORDER_EVENT,
                                    source=self.agent_id,
                                    data={"order": {"ordId": limit_order_id, "instId": limit_order_params.get('inst_id'), "side": limit_order_params.get('side'), "ordType": limit_order_params.get('ord_type'), "sz": limit_order_params.get('sz'), "state": "live"}},
                                )
                            )
                        else:
                            logger.error(f"❌ 挂单失败: {limit_result.get('error')}")
                    except Exception as e:
                        logger.error(f"❌ 挂单执行异常: {e}")
                else:
                    logger.info(f"挂单收益 {expected_return * 100:.2f}% 小于手续费 {fee_rate * 100:.2f}%，不执行挂单")
        except Exception as e:
            logger.error(f"❌ 交易执行异常: {e}")

    async def _on_risk_alert(self, event: Event):
        """处理风险警报"""
        logger.warning(f"收到风险警报: {event.data}")

        # 根据风险等级采取相应措施
        level = event.data.get("level", "low")
        if level == "critical":
            logger.warning("系统风险等级为critical，但暂时禁用紧急停止功能")
            # await self._emergency_stop()  # 暂时禁用紧急停止
    
    async def _on_market_prediction(self, event: Event):
        """处理市场预测事件"""
        try:
            inst_id = event.data.get("inst_id")
            prediction = event.data.get("prediction")
            
            logger.info(f"收到市场预测事件: {inst_id}, 趋势: {prediction.get('trend')}")
            
            # 评估市场风险
            risk_level = self._assess_market_risk(prediction)
            
            # 发布风险评估事件
            await self._publish_risk_assessment(inst_id, prediction, risk_level)
            
        except Exception as e:
            logger.error(f"处理市场预测事件失败: {e}")
    
    def _assess_market_risk(self, prediction: Dict) -> str:
        """评估市场风险
        
        Args:
            prediction: 市场预测结果
            
        Returns:
            str: 风险等级 (low/medium/high/critical)
        """
        try:
            # 基于市场预测评估风险
            trend = prediction.get("trend", "neutral")
            volatility = prediction.get("volatility", 0)
            momentum = prediction.get("momentum", "neutral")
            
            # 计算风险分数
            risk_score = 0
            
            # 趋势风险
            if trend == "bearish":
                risk_score += 3
            elif trend == "bullish":
                risk_score += 1
            
            # 波动率风险
            if volatility > 5:
                risk_score += 3
            elif volatility > 2:
                risk_score += 2
            
            # 动量风险
            if momentum == "strong":
                risk_score += 2
            elif momentum == "weak":
                risk_score += 1
            
            # 确定风险等级
            if risk_score >= 8:
                return "critical"
            elif risk_score >= 5:
                return "high"
            elif risk_score >= 3:
                return "medium"
            else:
                return "low"
                
        except Exception as e:
            logger.error(f"评估市场风险失败: {e}")
            return "low"
    
    async def _publish_risk_assessment(self, inst_id: str, prediction: Dict, risk_level: str):
        """发布风险评估事件"""
        try:
            # 发布风险评估事件
            await self.event_bus.publish_async(
                Event(
                    type=EventType.RISK_ASSESSMENT,
                    source=self.agent_id,
                    data={
                        "inst_id": inst_id,
                        "prediction": prediction,
                        "risk_level": risk_level
                    },
                )
            )
            logger.info(f"发布风险评估事件: {inst_id}, 风险等级: {risk_level}")
        except Exception as e:
            logger.error(f"发布风险评估事件失败: {e}")

    async def _emergency_stop(self):
        """紧急停止"""
        logger.critical("执行系统紧急停止")

        # 停止所有智能体
        for agent_id, agent in self._agents.items():
            await agent.stop()

        # 发布系统关闭事件
        await self.event_bus.publish_async(
            Event(
                type=EventType.SYSTEM_SHUTDOWN,
                source=self.agent_id,
                data={"reason": "emergency_stop"},
            )
        )

    # ========== 公共接口 ==========

    def unregister_agent(self, agent_id: str):
        """
        注销智能体

        Args:
            agent_id: 智能体ID
        """
        if agent_id in self._agents:
            del self._agents[agent_id]
            logger.info(f"注销智能体: {agent_id}")

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """
        获取智能体

        Args:
            agent_id: 智能体ID

        Returns:
            Optional[BaseAgent]: 智能体实例
        """
        return self._agents.get(agent_id)

    def register_agent(self, agent: BaseAgent):
        """
        注册智能体

        Args:
            agent: 要注册的智能体
        """
        if agent and agent.agent_id not in self._agents:
            self._agents[agent.agent_id] = agent
            logger.info(f"智能体已注册: {agent.name} ({agent.agent_id})")
        else:
            logger.warning(f"智能体已存在或无效: {agent.name if agent else 'None'}")

    def get_all_agents_status(self) -> List[Dict]:
        """获取所有智能体状态"""
        return [agent.get_status() for agent in self._agents.values()]

    def get_trading_summary(self) -> Dict[str, Any]:
        """
        获取交易摘要信息

        Returns:
            Dict: 包含交易历史、收益和账户信息的摘要
        """
        summary = {
            "total_trades": 0,
            "total_pnl": 0.0,
            "total_fees": 0.0,
            "account_info": None,
            "asset_distribution": {},
            "trade_history": [],
        }

        # 收集各智能体的信息
        for agent_id, agent in self._agents.items():
            # 订单智能体 - 交易历史和收益
            if hasattr(agent, "get_trade_history") and hasattr(agent, "get_pnl"):
                summary["trade_history"] = agent.get_trade_history()
                summary["total_trades"] = len(summary["trade_history"])

                pnl_info = agent.get_pnl()
                summary["total_pnl"] = pnl_info.get("total_pnl", 0.0)
                summary["total_fees"] = pnl_info.get("total_fees", 0.0)

            # 风险管理智能体 - 账户信息
            if hasattr(agent, "get_account_info") and hasattr(
                agent, "get_asset_distribution"
            ):
                summary["account_info"] = agent.get_account_info()
                summary["asset_distribution"] = agent.get_asset_distribution()

        return summary

    async def broadcast_command(self, command: str, params: Dict = None):
        """
        广播命令给所有智能体

        Args:
            command: 命令名称
            params: 命令参数
        """
        for agent_id in self._agents.keys():
            msg = Message.create_command(
                sender=self.agent_id,
                receiver=agent_id,
                command_type=getattr(
                    MessageType, f"COMMAND_{command.upper()}", MessageType.COMMAND_START
                ),
                payload=params or {},
            )
            await self.send_message(msg)

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        base_status = super().get_status()
        base_status.update(
            {
                "system_health": self._system_health,
                "registered_agents": list(self._agents.keys()),
                "agent_count": len(self._agents),
                "system_stats": self._system_stats,
            }
        )
        return base_status
