"""
策略智能体 - 负责策略执行
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
import sys
import os

# 添加策略目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from .base_agent import BaseAgent, AgentConfig
from core.events.event_bus import Event, EventType
from core.events.agent_communication import Message, MessageType, MessageTemplates

from core.utils.logger import get_logger

# 导入数据收集器
from data_collector import DataCollector

# 导入策略基类
from strategies.base_strategy import BaseStrategy

logger = get_logger(__name__)


class StrategyAgent(BaseAgent):
    """
    策略智能体

    职责：
    1. 加载和管理策略
    2. 执行策略信号生成
    3. 协调策略与订单执行
    """

    def __init__(self, config: AgentConfig, market_data_agent=None, order_agent=None, rest_client=None, exchange_name: str = "okx"):
        super().__init__(config)

        # 交易所配置
        self.exchange_name = exchange_name
        
        # 依赖的智能体
        self.market_data_agent = market_data_agent
        self.order_agent = order_agent
        
        # REST客户端
        self.rest_client = rest_client

        # 策略管理
        self._strategies: Dict[str, BaseStrategy] = {}
        self._active_strategies: List[str] = []  # 支持多个策略同时运行

        # 信号缓存
        self._signals: List[Dict] = []
        
        # 信号批处理
        self._signal_batch: List[Dict] = []
        self._batch_size = 1  # 批处理大小（改为1，立即处理）
        self._batch_interval = 0.01  # 批处理间隔（秒）
        self._last_batch_time = 0  # 上次批处理时间
        
        # 信号去重
        self._signal_cache: Dict[str, float] = {}  # 信号键 -> 处理时间
        self._signal_ttl = 1  # 信号有效期（秒）

        # 数据收集器
        self.data_collector = DataCollector()

        # 交易对配置
        from core.utils.config_manager import get_config
        self._subscribed_instruments = get_config("market.subscribed_instruments", ["BTC-USDT", "ETH-USDT"])
        self._default_inst_id = "BTC-USDT"  # 使用现货交易对

        # 信号处理统计
        self._signal_stats = {
            'total_signals': 0,
            'processed_signals': 0,
            'filtered_signals': 0,
            'duplicate_signals': 0,
            'avg_processing_time': 0,
            'total_processing_time': 0,
        }

        logger.info(f"策略智能体初始化完成: {self.agent_id}")

    async def _initialize(self):
        """初始化"""
        self.register_message_handler(
            MessageType.COMMAND_START, self._handle_strategy_command
        )

        # 订阅市场数据事件
        self.event_bus.subscribe(
            EventType.MARKET_DATA_TICKER, self._on_market_data, async_callback=True
        )
        
        # 订阅交易事件
        self.event_bus.subscribe(
            EventType.TRADE_EVENT, self._on_trade_event, async_callback=True
        )
        
        # 订阅交易指标事件
        self.event_bus.subscribe(
            EventType.TRADE_METRICS, self._on_trade_metrics, async_callback=True
        )
        
        # 订阅低收益率事件
        self.event_bus.subscribe(
            EventType.LOW_RETURN_EVENT, self._on_low_return_event, async_callback=True
        )
        
        # 订阅风险评估事件
        self.event_bus.subscribe(
            EventType.RISK_ASSESSMENT, self._on_risk_assessment, async_callback=True
        )

        # 加载默认策略
        await self._load_default_strategies()

        logger.info("策略智能体初始化完成")

    async def _cleanup(self):
        """清理"""
        # 停止所有策略
        for strategy in self._strategies.values():
            strategy.stop()

        self._strategies.clear()
        self._signals.clear()

        logger.info("策略智能体已清理")

    async def _execute_cycle(self):
        """执行周期"""
        # 执行所有活跃策略
        for strategy_name in self._active_strategies:
            logger.debug(f"执行策略: {strategy_name}")
            await self._execute_strategy_cycle(strategy_name)

        # 处理信号批
        await self._process_signal_batch()

        await asyncio.sleep(0.1)

    async def _load_default_strategies(self):
        """加载默认策略"""
        try:
            logger.info("开始加载默认策略...")
            
            # 尝试导入策略类
            strategies_to_load = [
                ("DynamicsStrategy", "strategies.dynamics_strategy", "DynamicsStrategy"),
                ("NuclearDynamicsStrategy", "strategies.nuclear_dynamics_strategy", "NuclearDynamicsStrategy"),
                ("PassivbotStrategy", "strategies.passivbot_integrator", "PassivbotIntegrator"),
                ("MachineLearningStrategy", "strategies.machine_learning_strategy", "MachineLearningStrategy"),
                ("ArbitrageStrategy", "strategies.arbitrage_strategy", "ArbitrageStrategy"),
                ("CrossMarketArbitrageStrategy", "strategies.cross_market_arbitrage_strategy", "CrossMarketArbitrageStrategy"),
                ("CombinedStrategy", "strategies.combined_strategy", "CombinedStrategy"),
            ]
            
            loaded_strategies = {}
            
            # 先加载基础策略
            try:
                from strategies.base_strategy import BaseStrategy
                logger.info("导入基础策略类成功")
            except Exception as e:
                logger.error(f"导入基础策略类失败: {e}")
                return
            
            # 加载各个策略
            for strategy_name, module_name, class_name in strategies_to_load:
                try:
                    logger.info(f"导入{strategy_name}...")
                    module = __import__(module_name, fromlist=[class_name])
                    strategy_class = getattr(module, class_name)
                    
                    # 根据策略类型创建配置
                    if strategy_name == "DynamicsStrategy":
                        config = {
                            "dynamics": {
                                "ε": 0.85,
                                "G_eff": 1.2e-3,
                                "n": 3,
                                "η": 0.75,
                                "γ": 0.1,
                                "κ": 2.5,
                                "λ": 3.0,
                                "t_coll": 0.1,
                            }
                        }
                    elif strategy_name == "PassivbotStrategy":
                        config = {
                            "broker": "okx",
                            "symbol": "BTC-USDT-SWAP",
                            "timeframe": "1h",
                            "strategy": "default",
                        }
                    elif strategy_name == "MachineLearningStrategy":
                        config = {
                            "window_size": 20,
                            "threshold": 0.001,
                            "lookback": 100
                        }
                    elif strategy_name == "ArbitrageStrategy":
                        config = {
                            "arb_pairs": [
                                {
                                    "inst_id1": "BTC-USDT-SWAP",
                                    "inst_id2": "BTC-USDT",
                                    "ratio": 1.0
                                },
                                {
                                    "inst_id1": "ETH-USDT-SWAP",
                                    "inst_id2": "ETH-USDT",
                                    "ratio": 1.0
                                }
                            ],
                            "min_profit": 0.001,
                            "max_trade_amount": 0.01
                        }
                    elif strategy_name == "CrossMarketArbitrageStrategy":
                        config = {
                            "arbitrage_threshold": 0.5,
                            "max_trade_amount": 10000,
                            "min_trade_amount": 100,
                            "exchanges": ["okx", "binance"],
                            "trading_pairs": ["BTC/USDT", "ETH/USDT"],
                            "polling_interval": 1,
                            "max_position": 0.1,
                            "fee_estimate": 0.1,
                            "profit_threshold": 0.1
                        }
                    elif strategy_name == "CombinedStrategy":
                        # 组合策略需要其他策略已经加载
                        if "DynamicsStrategy" in self._strategies and "PassivbotStrategy" in self._strategies and "MachineLearningStrategy" in self._strategies and "ArbitrageStrategy" in self._strategies:
                            config = {
                                "sub_strategies": [
                                    {
                                        "name": "DynamicsStrategy",
                                        "class": loaded_strategies["DynamicsStrategy"],
                                        "config": self._strategies["DynamicsStrategy"].config,
                                        "weight": 0.3,
                                    },
                                    {
                                        "name": "PassivbotStrategy",
                                        "class": loaded_strategies["PassivbotStrategy"],
                                        "config": self._strategies["PassivbotStrategy"].config,
                                        "weight": 0.3,
                                    },
                                    {
                                        "name": "MachineLearningStrategy",
                                        "class": loaded_strategies["MachineLearningStrategy"],
                                        "config": self._strategies["MachineLearningStrategy"].config,
                                        "weight": 0.2,
                                    },
                                    {
                                        "name": "ArbitrageStrategy",
                                        "class": loaded_strategies["ArbitrageStrategy"],
                                        "config": self._strategies["ArbitrageStrategy"].config,
                                        "weight": 0.2,
                                    },
                                ]
                            }
                        else:
                            logger.warning("组合策略依赖的策略未加载，跳过加载")
                            continue
                    else:
                        config = {}
                    
                    # 创建策略实例
                    strategy = strategy_class(config=config)
                    self._strategies[strategy_name] = strategy
                    loaded_strategies[strategy_name] = strategy_class
                    logger.info(f"加载策略成功: {strategy_name}")
                except Exception as e:
                    logger.error(f"加载策略 {strategy_name} 失败: {e}")
                    import traceback
                    logger.error(f"详细错误信息: {traceback.format_exc()}")
                    continue
            
            logger.info(f"所有策略加载完成，共 {len(self._strategies)} 个策略")

            # 自动激活NuclearDynamicsStrategy
            if "NuclearDynamicsStrategy" in self._strategies:
                await self.activate_strategy("NuclearDynamicsStrategy")
                logger.info("已自动激活NuclearDynamicsStrategy策略")

        except Exception as e:
            logger.error(f"加载默认策略失败: {e}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")

    async def _execute_strategy_cycle(self, strategy_name: str):
        """执行策略周期"""
        strategy = self._strategies.get(strategy_name)
        if not strategy:
            logger.warning(f"策略不存在: {strategy_name}")
            return

        try:
            # 先更新订阅的交易对
            await self._update_subscribed_instruments()
            
            logger.info(f"开始执行策略周期: {strategy_name}")
            # 为每个订阅的交易对执行策略
            for inst_id in self._subscribed_instruments:
                logger.debug(f"处理交易对: {inst_id}")
                # 获取市场数据
                market_data = {}
                ticker = None
                
                if self.market_data_agent:
                    # 先尝试从缓存获取
                    ticker = self.market_data_agent.get_ticker(inst_id)
                
                # 如果缓存中没有数据，直接从我们自己的REST API获取
                if not ticker and self.rest_client:
                    try:
                        ticker = await self.rest_client.get_ticker(inst_id)
                        logger.debug(f"直接从REST API获取市场数据 for {inst_id}: {ticker}")
                    except Exception as e:
                        logger.warning(f"从REST API获取市场数据失败 for {inst_id}: {e}")
                        import traceback
                        logger.warning(f"详细错误: {traceback.format_exc()}")
                
                if ticker:
                    # 尝试从ticker中获取价格，支持last和last_price字段
                    price = ticker.get("last") or ticker.get("last_price")
                    market_data = {
                        "inst_id": inst_id,
                        "price": float(price) if price else 0,
                        "timestamp": ticker.get("ts", 0),
                    }
                    logger.debug(f"获取到市场数据 for {inst_id}: 价格={market_data['price']}")
                else:
                    logger.warning(f"没有市场数据 for {inst_id}, ticker={ticker}")

                # 获取本地生成的订单信息作为只读数据
                order_data = {}
                if self.order_agent:
                    try:
                        # 获取交易历史（只读）
                        trade_history = self.order_agent.get_trade_history(limit=200, inst_id=inst_id)
                        # 获取未成交订单（只读）
                        pending_orders = self.order_agent.get_pending_orders(inst_id=inst_id)
                        
                        order_data = {
                            "trade_history": trade_history,
                            "pending_orders": pending_orders,
                            "order_count": len(trade_history),
                            "pending_count": len(pending_orders)
                        }
                        logger.debug(f"获取订单数据 for {inst_id}: 交易历史={len(trade_history)}, 未成交订单={len(pending_orders)}")
                    except Exception as e:
                        logger.error(f"获取订单数据失败 for {inst_id}: {e}")

                # 执行策略，将市场数据传递给策略
                if market_data:
                    logger.debug(f"执行策略 for {inst_id}")
                    
                    signal = strategy.execute(market_data)

                    if signal:
                        logger.info(f"策略生成信号 for {inst_id}: {signal}")
                        # 确保信号包含交易对信息
                        if "inst_id" not in signal:
                            signal["inst_id"] = inst_id
                        await self._process_signal(signal)
                    else:
                        logger.debug(f"策略未生成信号 for {inst_id}")
                else:
                    logger.warning(f"没有市场数据 for {inst_id}")

        except Exception as e:
            logger.error(f"策略执行错误: {e}")
            import traceback
            logger.error(f"详细错误信息:\n{traceback.format_exc()}")

    async def _process_signal(self, signal: Dict):
        """处理交易信号"""
        import time
        start_time = time.time()
        self._signal_stats['total_signals'] += 1

        # 检查信号级别和方向
        signal_level = signal.get("signal_level", "S")
        side = signal.get("side", "neutral")
        inst_id = signal.get("inst_id", "BTC-USDT")
        timestamp = signal.get("timestamp", time.time())
        
        # 生成信号键，用于去重
        signal_key = f"{inst_id}:{side}:{signal_level}:{int(timestamp)}"
        
        # 检查是否为重复信号
        current_time = time.time()
        if signal_key in self._signal_cache:
            if current_time - self._signal_cache[signal_key] < self._signal_ttl:
                self._signal_stats['duplicate_signals'] += 1
                logger.debug(f"重复信号，跳过处理: {signal_key}")
                return
        
        # 更新信号缓存
        self._signal_cache[signal_key] = current_time
        
        # 清理过期的信号缓存
        expired_keys = [k for k, v in self._signal_cache.items() if current_time - v >= self._signal_ttl]
        for k in expired_keys:
            del self._signal_cache[k]
        
        # 允许S、SS、SSS级的信号，包括buy、sell和neutral，支持所有订阅的交易对
        if inst_id in self._subscribed_instruments and side in ["buy", "sell", "neutral"] and signal_level in ["S", "SS", "SSS"]:
            # 添加到批处理队列
            self._signal_batch.append(signal)
            logger.debug(f"添加信号到批处理队列: 级别={signal_level}, 方向={side}, 产品={inst_id}")
        else:
            # 过滤掉不符合条件的信号
            self._signal_stats['filtered_signals'] += 1
            logger.debug(f"过滤信号: 级别={signal_level}, 方向={side}, 产品={inst_id}")
            return

    async def _process_signal_batch(self):
        """处理信号批"""
        import time
        current_time = time.time()
        
        # 检查是否需要处理批
        if (len(self._signal_batch) >= self._batch_size or 
            (current_time - self._last_batch_time >= self._batch_interval and self._signal_batch)):
            
            start_time = time.time()
            batch_size = len(self._signal_batch)
            
            # 处理批中的所有信号
            for signal in self._signal_batch:
                await self._process_single_signal(signal)
            
            # 清空批处理队列
            self._signal_batch.clear()
            self._last_batch_time = current_time
            
            # 更新统计信息
            processing_time = time.time() - start_time
            self._signal_stats['total_processing_time'] += processing_time
            self._signal_stats['processed_signals'] += batch_size
            if self._signal_stats['processed_signals'] > 0:
                self._signal_stats['avg_processing_time'] = \
                    self._signal_stats['total_processing_time'] / self._signal_stats['processed_signals']
            
            logger.debug(f"处理信号批: 数量={batch_size}, 耗时={processing_time:.3f}s")

    async def _process_single_signal(self, signal: Dict):
        """处理单个信号"""
        signal_level = signal.get("signal_level", "S")
        side = signal.get("side", "neutral")
        
        # 缓存信号
        self._signals.append(signal)
        if len(self._signals) > 100:
            self._signals = self._signals[-100:]

        # 收集交易数据
        self.data_collector.add_trade_data(signal)

        # 根据信号方向调整处理逻辑
        if side == "sell":
            # 发布风险警告事件
            await self.event_bus.publish_async(
                Event(
                    type=EventType.RISK_ALERT,
                    source=self.agent_id,
                    data={
                        "level": "medium",
                        "message": f"策略发出卖出信号，提示风险",
                        "signal": signal
                    },
                )
            )
            logger.debug(f"发布风险警告事件: 策略发出卖出信号")
        
        # 发送信号事件
        await self.event_bus.publish_async(
            Event(
                type=EventType.STRATEGY_SIGNAL,
                source=self.agent_id,
                data={"signal": signal},
            )
        )

        # 发送信号通知
        signal_msg = MessageTemplates.strategy_signal(
            sender=self.agent_id,
            strategy_name=signal.get("strategy", "unknown"),
            signal=signal,
        )
        await self.send_message(signal_msg)

    async def _handle_strategy_command(self, message: Message):
        """处理策略命令"""
        payload = message.payload
        action = payload.get("action")

        if action == "activate":
            result = await self.activate_strategy(payload.get("strategy_name"))
        elif action == "deactivate":
            result = await self.deactivate_strategy(payload.get("strategy_name"))
        elif action == "list":
            result = {
                "success": True,
                "strategies": list(self._strategies.keys()),
                "active_strategies": self._active_strategies,
            }
        else:
            result = {"success": False, "error": "未知命令"}

        response = Message.create_response(
            sender=self.agent_id,
            receiver=message.sender,
            request_message=message,
            payload=result,
        )
        await self.send_message(response)

    async def _on_market_data(self, event: Event):
        """处理市场数据更新"""
        self.metrics.update_activity()
    
    async def _on_trade_event(self, event: Event):
        """处理交易事件"""
        try:
            trade_data = event.data.get("trade", {})
            total_fees = event.data.get("total_fees", 0)
            
            logger.info(f"收到交易事件: {trade_data.get('trade_id')}")
            logger.info(f"交易手续费: {trade_data.get('fee', 0)}")
            logger.info(f"累计手续费: {total_fees}")
            
            # 通知所有激活的策略
            for strategy_name in self._active_strategies:
                strategy = self._strategies.get(strategy_name)
                if strategy:
                    # 调用策略的交易处理方法
                    try:
                        await strategy.on_trade_event(trade_data, total_fees)
                    except Exception as e:
                        logger.error(f"策略 {strategy_name} 处理交易事件失败: {e}")
        except Exception as e:
            logger.error(f"处理交易事件失败: {e}")
    
    async def _on_trade_metrics(self, event: Event):
        """处理交易指标事件"""
        try:
            trade_stats = event.data.get("trade_stats", {})
            risk_level = event.data.get("risk_level", "low")
            
            logger.info(f"收到交易指标事件: 胜率={trade_stats.get('win_rate', 0):.2f}, 盈利因子={trade_stats.get('profit_factor', 1):.2f}, 风险等级={risk_level}")
            
            # 通知所有激活的策略
            for strategy_name in self._active_strategies:
                strategy = self._strategies.get(strategy_name)
                if strategy:
                    # 调用策略的交易指标处理方法
                    try:
                        await strategy.on_trade_metrics(trade_stats, risk_level)
                    except Exception as e:
                        logger.error(f"策略 {strategy_name} 处理交易指标事件失败: {e}")
        except Exception as e:
            logger.error(f"处理交易指标事件失败: {e}")
    
    async def _on_low_return_event(self, event: Event):
        """处理低收益率事件"""
        try:
            params = event.data.get("params", {})
            expected_return = event.data.get("expected_return", 0)
            reason = event.data.get("reason", "")
            
            logger.info(f"收到低收益率事件: 预期收益率={expected_return:.4f}, 原因={reason}")
            
            # 获取相关产品ID
            inst_id = params.get("inst_id", self._default_inst_id)
            
            # 获取市场预测数据
            market_prediction = None
            if self.market_data_agent:
                # 这里可以通过事件总线获取最新的市场预测数据
                # 或者直接调用市场数据智能体的方法获取
                pass
            
            # 通知所有激活的策略
            for strategy_name in self._active_strategies:
                strategy = self._strategies.get(strategy_name)
                if strategy:
                    # 调用策略的低收益率处理方法，传入市场预测数据
                    try:
                        await strategy.on_low_return_event(params, expected_return, reason, market_prediction)
                    except Exception as e:
                        logger.error(f"策略 {strategy_name} 处理低收益率事件失败: {e}")
        except Exception as e:
            logger.error(f"处理低收益率事件失败: {e}")
    
    async def _on_risk_assessment(self, event: Event):
        """处理风险评估事件"""
        try:
            inst_id = event.data.get("inst_id")
            prediction = event.data.get("prediction")
            risk_level = event.data.get("risk_level", "low")
            
            logger.info(f"收到风险评估事件: {inst_id}, 风险等级: {risk_level}")
            
            # 通知所有激活的策略
            for strategy_name in self._active_strategies:
                strategy = self._strategies.get(strategy_name)
                if strategy:
                    # 调用策略的风险评估处理方法
                    try:
                        await strategy.on_risk_assessment(inst_id, prediction, risk_level)
                    except Exception as e:
                        logger.error(f"策略 {strategy_name} 处理风险评估事件失败: {e}")
        except Exception as e:
            logger.error(f"处理风险评估事件失败: {e}")

    # ========== 公共接口 ==========

    async def activate_strategy(self, strategy_name: str) -> Dict:
        """
        激活策略

        Args:
            strategy_name: 策略名称

        Returns:
            Dict: 结果
        """
        if strategy_name not in self._strategies:
            return {"success": False, "error": f"策略不存在: {strategy_name}"}

        # 检查策略是否已经激活
        if strategy_name in self._active_strategies:
            return {"success": False, "error": f"策略已经激活: {strategy_name}"}

        # 启动策略
        strategy = self._strategies[strategy_name]
        strategy.start()
        self._active_strategies.append(strategy_name)

        logger.info(f"策略已激活: {strategy_name}")
        return {"success": True, "strategy": strategy_name}

    async def deactivate_strategy(self, strategy_name: str = None) -> Dict:
        """
        停用策略

        Args:
            strategy_name: 策略名称，None表示停用所有策略

        Returns:
            Dict: 结果
        """
        if not self._active_strategies:
            return {"success": False, "error": "没有激活的策略"}

        if strategy_name:
            # 停用指定策略
            if strategy_name not in self._active_strategies:
                return {"success": False, "error": f"策略未激活: {strategy_name}"}

            # 停止策略
            strategy = self._strategies.get(strategy_name)
            if strategy:
                strategy.stop()

            self._active_strategies.remove(strategy_name)
            logger.info(f"策略已停用: {strategy_name}")
        else:
            # 停用所有策略
            for name in self._active_strategies:
                strategy = self._strategies.get(name)
                if strategy:
                    strategy.stop()

            self._active_strategies.clear()
            logger.info("所有策略已停用")

        return {"success": True}

    def get_active_strategies(self) -> List[str]:
        """获取当前激活的策略列表"""
        return self._active_strategies

    def get_signals(self, limit: int = 10) -> List[Dict]:
        """获取最近信号"""
        return self._signals[-limit:]

    def get_signal_stats(self) -> Dict[str, Any]:
        """获取信号处理统计信息"""
        return self._signal_stats

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        base_status = super().get_status()
        base_status.update(
            {
                "strategies": list(self._strategies.keys()),
                "active_strategies": self._active_strategies,
                "signal_count": len(self._signals),
                "signal_stats": self._signal_stats,
                "batch_size": len(self._signal_batch),
            }
        )
        return base_status

    async def _detect_held_currencies(self):
        """
        检测所有持仓货币

        Returns:
            List[str]: 持仓货币列表
        """
        try:
            # 从order_agent获取账户信息
            if self.order_agent and self.order_agent.trader:
                account_info = await self.order_agent.trader.get_account_info()
                if account_info:
                    # 从账户信息中获取所有有余额的货币
                    held_currencies = []
                    for currency, info in account_info.currencies.items():
                        # 检查是否有可用余额
                        avail_bal = info.get('available', 0)
                        if float(avail_bal) > 0:
                            held_currencies.append(currency)
                    
                    logger.info(f"检测到持仓货币: {held_currencies}")
                    return held_currencies
                else:
                    logger.warning("无法获取账户信息，无法检测持仓货币")
                    return []
            else:
                logger.warning("未找到OrderAgent或trader未初始化")
                return []
        except Exception as e:
            logger.error(f"检测持仓货币失败: {e}")
            return []

    async def _update_subscribed_instruments(self):
        """
        更新订阅的交易对，只包含持仓大于1 USDT的货币
        """
        try:
            # 检测持仓货币
            held_currencies = await self._detect_held_currencies()
            
            # 为每个持仓货币创建交易对，只保留持仓市值大于1 USDT的
            new_instruments = []
            
            # 获取实时价格用于计算市值
            for currency in held_currencies:
                if currency == 'USDT':  # 跳过USDT本身
                    continue
                
                # 尝试获取该货币的实时价格
                try:
                    inst_id = f"{currency}-USDT"
                    
                    # 先尝试从market_data_agent获取价格
                    price = None
                    if self.market_data_agent:
                        ticker = self.market_data_agent.get_ticker(inst_id)
                        if ticker:
                            price = ticker.get("last") or ticker.get("last_price")
                    
                    # 如果没有价格，尝试从rest_client获取
                    if not price and self.rest_client:
                        ticker = await self.rest_client.get_ticker(inst_id)
                        if ticker:
                            price = ticker.get("last") or ticker.get("last_price")
                    
                    # 计算持仓市值
                    if price:
                        price_float = float(price)
                        # 获取该货币的余额
                        if self.order_agent and self.order_agent.trader:
                            account_info = await self.order_agent.trader.get_account_info()
                            if account_info:
                                currency_info = account_info.currencies.get(currency, {})
                                avail_bal = float(currency_info.get('available', 0))
                                market_value = avail_bal * price_float
                                
                                logger.info(f"{currency} 持仓: {avail_bal:.8f} {currency}, 价格: {price_float:.2f} USDT, 市值: {market_value:.2f} USDT")
                                
                                # 只添加市值大于1 USDT的货币
                                if market_value > 1.0:
                                    new_instruments.append(inst_id)
                                    logger.info(f"✅ {currency} 市值 {market_value:.2f} USDT > 1 USDT，添加到交易对")
                                else:
                                    logger.info(f"❌ {currency} 市值 {market_value:.2f} USDT <= 1 USDT，跳过")
                except Exception as e:
                    logger.warning(f"计算 {currency} 市值失败: {e}")
                    continue
            
            # 如果没有符合条件的货币，至少保留BTC-USDT
            if not new_instruments:
                new_instruments.append('BTC-USDT')
                logger.info("没有符合条件的货币，默认添加BTC-USDT")
            
            # 更新订阅的交易对
            if set(new_instruments) != set(self._subscribed_instruments):
                self._subscribed_instruments = new_instruments
                logger.info(f"更新订阅的交易对: {self._subscribed_instruments}")
            else:
                logger.debug(f"订阅的交易对未变化: {self._subscribed_instruments}")
        except Exception as e:
            logger.error(f"更新订阅的交易对失败: {e}")

    async def shutdown(self):
        """关闭智能体"""
        await super().shutdown()
        # 保存数据
        self.data_collector.save_data()
        # 清理旧数据
        self.data_collector.cleanup_old_data()
        logger.info("策略智能体已关闭，数据已保存")
