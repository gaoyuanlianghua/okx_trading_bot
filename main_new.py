"""
OKX交易机器人 - 主程序入口

新的架构实现，基于OKX API指南和策略系统
支持实盘和模拟盘环境切换
"""

import asyncio
import logging
import os
import sys
import argparse
from typing import Dict, Any

# 导入日志配置模块
from core.utils.logger import logger_config, get_logger

# 配置日志系统
logger_config.configure(level=logging.INFO, structured=False)
logger = get_logger(__name__)

# 导入环境管理器
from core.config.env_manager import env_manager

# 导入核心组件
from core import (
    Event,
    EventType,
    BaseAgent,
    AgentConfig,
    MarketDataAgent,
    RiskAgent,
    StrategyAgent,
    CoordinatorAgent,
    OKXRESTClient,
    OKXWebSocketClient,
)

# 导入全局事件总线
from core.events.event_bus import event_bus

# 使用适配器版本的 OrderAgent
from core.agents.order_agent_adapter import OrderAgentAdapter as OrderAgent
from core.agents.account_sync_agent import AccountSyncAgent

# 导入新功能模块
from core.emotion_analysis.market_sentiment_analyzer import MarketSentimentAnalyzer
from core.notification.smart_notification_system import SmartNotificationSystem

# 导入配置管理
from core.utils.config_manager import get_config, get_full_config, config_manager

# 导入API日志调度器
from scripts.schedule_api_logs import APILogScheduler
from scripts.integrate_trade_logs import TradeLogIntegrator


class TradingBot:
    """
    交易机器人主类

    负责：
    1. 初始化所有组件
    2. 管理智能体生命周期
    3. 处理系统启动和关闭
    """

    def __init__(self):
        """初始化交易机器人"""
        # 使用全局的event_bus实例
        from core.events.event_bus import event_bus
        self.event_bus = event_bus
        self.coordinator: CoordinatorAgent = None
        self.market_data_agent: MarketDataAgent = None
        self.order_agent: OrderAgent = None
        self.risk_agent: RiskAgent = None
        self.strategy_agent: StrategyAgent = None

        # API客户端
        self.rest_client: OKXRESTClient = None
        self.ws_client: OKXWebSocketClient = None

        # 新功能模块
        self.sentiment_analyzer: MarketSentimentAnalyzer = None
        self.notification_system: SmartNotificationSystem = None
        self.account_sync_agent: AccountSyncAgent = None

        # API日志调度器
        self.api_log_scheduler: APILogScheduler = None

        # 交易日志集成器
        self.trade_log_integrator: TradeLogIntegrator = None

        # 运行状态
        self._running = False

        logger.info("交易机器人初始化完成")

    async def initialize(self, config: Dict[str, Any] = None):
        """
        初始化所有组件

        Args:
            config: 配置字典
        """
        # 如果提供了配置，则更新配置
        if config:
            from core.utils.config_manager import update_config
            update_config(config)

        # 从环境管理器获取配置
        logger.info("=" * 60)
        logger.info("环境初始化")
        logger.info("=" * 60)
        
        env_info = env_manager.get_env_info()
        logger.info(f"当前环境: {env_info['current_env']}")
        logger.info(f"模拟盘模式: {env_info['is_test']}")
        
        if not env_info['is_test']:
            logger.warning("⚠️  注意：当前不是模拟盘环境，将使用实盘交易！")
        else:
            logger.info("✅ 正在使用模拟盘环境")
        
        # 获取API配置
        api_config = env_manager.get_api_config()
        api_key = api_config['api_key']
        api_secret = api_config['api_secret']
        passphrase = api_config['passphrase']
        is_test = api_config['is_test']
        
        logger.info(f"API Key: {api_key[:8]}...")

        # 创建API客户端，使用环境配置
        self.rest_client = OKXRESTClient(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            is_test=is_test,
            use_env_config=True,
        )

        self.ws_client = OKXWebSocketClient(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            is_test=is_test,
        )
        
        # 获取交易配置
        trading_config = env_manager.get_trading_config()
        default_trading_mode = trading_config.get('default_trading_mode', 'cash')
        fixed_trade_amount = trading_config.get('fixed_trade_amount', 10)
        trade_amount_percentage = trading_config.get('trade_amount_percentage', 0.1)
        logger.info(f"默认交易模式: {default_trading_mode}")
        logger.info(f"固定交易金额: {fixed_trade_amount} USDT")
        logger.info(f"交易金额占可用余额的比例: {trade_amount_percentage * 100:.1f}%")
        
        # 获取策略配置
        strategy_config = env_manager.get_strategy_config()
        default_strategy = strategy_config.get('default_strategy', 'NuclearDynamicsStrategy')
        logger.info(f"默认策略: {default_strategy}")
        
        # 获取市场配置
        market_config = env_manager.get_market_config()
        cryptocurrencies = market_config.get('cryptocurrencies', ['BTC', 'ETH'])
        logger.info(f"监控的加密货币: {cryptocurrencies}")

        # 创建协调智能体
        coordinator_config = AgentConfig(
            name="Coordinator", description="系统协调智能体"
        )
        self.coordinator = CoordinatorAgent(coordinator_config)

        # 创建市场数据智能体
        market_data_config = AgentConfig(
            name="MarketData", description="市场数据智能体"
        )
        self.market_data_agent = MarketDataAgent(
            config=market_data_config,
            exchange_name="okx",
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            is_test=is_test,
        )

        # 创建订单智能体
        order_config = AgentConfig(name="Order", description="订单管理智能体")
        self.order_agent = OrderAgent(
            config=order_config,
            exchange_name="okx",
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            is_test=is_test,
            use_env_config=True,
        )

        # 创建风险管理智能体
        risk_config = AgentConfig(name="Risk", description="风险管理智能体")
        self.risk_agent = RiskAgent(config=risk_config, rest_client=self.market_data_agent.rest_client)

        # 创建策略智能体
        strategy_config = AgentConfig(name="Strategy", description="策略执行智能体")
        self.strategy_agent = StrategyAgent(
            config=strategy_config,
            market_data_agent=self.market_data_agent,
            order_agent=self.order_agent,
            rest_client=self.rest_client,
        )

        # 创建账户同步智能体
        account_sync_config = AgentConfig(name="AccountSync", description="账户同步智能体")
        self.account_sync_agent = AccountSyncAgent(
            config=account_sync_config,
            rest_client=self.rest_client
        )

        # 注册智能体到协调器
        self.coordinator.register_agent(self.market_data_agent)
        self.coordinator.register_agent(self.order_agent)
        self.coordinator.register_agent(self.risk_agent)
        self.coordinator.register_agent(self.strategy_agent)
        self.coordinator.register_agent(self.account_sync_agent)

        # 初始化新功能模块
        self.sentiment_analyzer = MarketSentimentAnalyzer(event_bus=self.event_bus)
        await self.sentiment_analyzer.initialize()

        self.notification_system = SmartNotificationSystem(event_bus=self.event_bus)
        await self.notification_system.start()



        # 启动自动同步OSS服务
        try:
            from auto_sync_oss import start_auto_sync
            if start_auto_sync():
                logger.info("✅ 自动同步OSS服务已启动")
            else:
                logger.warning("⚠️ 自动同步OSS服务启动失败")
        except Exception as e:
            logger.warning(f"⚠️ 自动同步OSS服务启动失败: {e}")

        # 获取交易产品基础信息
        try:
            instruments = await self.market_data_agent.get_instruments()
            logger.info(f"获取到 {len(instruments)} 个可交易产品")
            if instruments:
                logger.info(f"第一个产品: {instruments[0].get('instId')}")
        except Exception as e:
            logger.error(f"获取交易产品基础信息失败: {e}")

        logger.info("所有组件初始化完成")

    async def sync_orders(self):
        """同步交易订单信息"""
        try:
            logger.info("🔄 开始同步交易订单信息...")
            
            # 获取杠杆交易订单
            margin_orders = await self.order_agent.rest_client.get_order_history(
                inst_type="MARGIN",
                inst_id="BTC-USDT",
                limit=50  # 最近50个订单
            )
            
            if margin_orders:
                logger.info(f"获取到 {len(margin_orders)} 个杠杆交易订单")
                # 同步订单到本地
                for order in margin_orders:
                    # 处理订单数据
                    order_id = order.get('ordId')
                    side = order.get('side')
                    price = float(order.get('avgPx', '0'))
                    amount = float(order.get('accFillSz', '0'))
                    fee = float(order.get('fee', '0'))
                    fee_currency = order.get('feeCcy', 'USDT')
                    
                    # 记录交易
                    if side == 'buy' or side == 'sell':
                        # 构建交易记录
                        trade_record = {
                            "trade_id": order_id,
                            "inst_id": "BTC-USDT",
                            "side": side,
                            "ord_type": order.get('ordType', 'market'),
                            "price": price,
                            "size": amount,
                            "filled_size": amount,
                            "fee": fee,
                            "fee_currency": fee_currency,
                            "state": order.get('state', 'filled'),
                            "timestamp": order.get('cTime'),
                            "fill_time": order.get('fillTime'),
                            "td_mode": order.get('tdMode', 'cross'),
                            "source": "API"
                        }
                        
                        # 添加到交易历史
                        self.order_agent._trade_history.append(trade_record)
                        logger.info(f"✅ 同步API交易订单记录: {order_id} ({side} {amount:.8f} BTC @ {price:.2f} USDT, 手续费: {fee:.8f} {fee_currency})")
            else:
                logger.info("暂无杠杆交易订单")
            
            # 获取未成交订单
            open_orders = await self.order_agent.rest_client.get_pending_orders(
                inst_id="BTC-USDT",
                inst_type="MARGIN"
            )
            
            if open_orders:
                logger.info(f"获取到 {len(open_orders)} 个未成交订单")
            else:
                logger.info("暂无未成交订单")
            
            logger.info("✅ 交易订单信息同步完成")
            
        except Exception as e:
            logger.error(f"❌ 同步交易订单信息失败: {e}")
            import traceback
            logger.error(f"详细错误信息:\n{traceback.format_exc()}")

    async def validate_trade_types(self):
        """验证各种交易类型"""
        try:
            logger.info("开始验证各种交易类型...")
            
            # 验证现货买入 - 市价单
            logger.info("验证现货买入 - 市价单")
            if self.order_agent and self.order_agent.trader:
                from decimal import Decimal
                from core.traders.base_trader import OrderType
                buy_market_result = await self.order_agent.trader.buy(
                    inst_id="BTC-USDT",
                    size=Decimal('1'),  # 1 USDT
                    order_type=OrderType.MARKET
                )
                logger.info(f"  结果: 成功={buy_market_result.success}, 订单ID={buy_market_result.order_id}")
            else:
                logger.error("  订单智能体或交易器未初始化")
            
            # 验证现货买入 - 限价单
            logger.info("验证现货买入 - 限价单")
            if self.order_agent and self.order_agent.rest_client:
                # 获取当前价格
                ticker = await self.order_agent.rest_client.get_ticker("BTC-USDT")
                if ticker and isinstance(ticker, dict):
                    from decimal import Decimal
                    current_price = Decimal(str(ticker.get('last', '0')))
                    if current_price > 0:
                        # 设置限价为当前价格的95%，确保订单不会立即成交
                        limit_price = current_price * Decimal('0.95')
                        if self.order_agent and self.order_agent.trader:
                            from core.traders.base_trader import OrderType
                            buy_limit_result = await self.order_agent.trader.buy(
                                inst_id="BTC-USDT",
                                size=Decimal('1'),  # 1 USDT
                                price=limit_price,
                                order_type=OrderType.LIMIT
                            )
                            logger.info(f"  结果: 成功={buy_limit_result.success}, 订单ID={buy_limit_result.order_id}")
                        else:
                            logger.error("  订单智能体或交易器未初始化")
                    else:
                        logger.error("  无法获取当前价格")
                else:
                    logger.error("  无法获取当前价格")
            else:
                logger.error("  订单智能体或REST客户端未初始化")
            
            # 验证现货卖出 - 市价单
            logger.info("验证现货卖出 - 市价单")
            if self.order_agent and self.order_agent.trader:
                # 先获取BTC余额
                account_info = await self.order_agent.trader.get_account_info()
                from decimal import Decimal
                btc_balance = Decimal('0')
                if account_info and hasattr(account_info, 'currencies'):
                    btc_balance = account_info.currencies.get('BTC', {}).get('available', Decimal('0'))
                
                if btc_balance > Decimal('0'):
                    # 卖出所有可用BTC
                    from core.traders.base_trader import OrderType
                    sell_market_result = await self.order_agent.trader.sell(
                        inst_id="BTC-USDT",
                        size=btc_balance,
                        order_type=OrderType.MARKET
                    )
                    logger.info(f"  结果: 成功={sell_market_result.success}, 订单ID={sell_market_result.order_id}")
                else:
                    logger.error("  BTC余额不足")
            else:
                logger.error("  订单智能体或交易器未初始化")
            
            # 验证其他交易对 - ETH-USDT
            logger.info("验证其他交易对 - ETH-USDT")
            if self.order_agent and self.order_agent.trader:
                from decimal import Decimal
                from core.traders.base_trader import OrderType
                eth_buy_result = await self.order_agent.trader.buy(
                    inst_id="ETH-USDT",
                    size=Decimal('1'),  # 1 USDT
                    order_type=OrderType.MARKET
                )
                logger.info(f"  结果: 成功={eth_buy_result.success}, 订单ID={eth_buy_result.order_id}")
            else:
                logger.error("  订单智能体或交易器未初始化")
            
            logger.info("交易类型验证完成")
            
        except Exception as e:
            logger.error(f"验证交易类型失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")

    async def start(self):
        """启动交易机器人"""
        if self._running:
            logger.warning("交易机器人已在运行中")
            return

        self._running = True

        try:
            # 启动事件总线
            logger.info("1️⃣ 启动事件总线...")
            self.event_bus.start()
            logger.info("✅ 事件总线已启动")
            
            # 初始化交易日志集成器
            self.trade_log_integrator = TradeLogIntegrator(event_bus=self.event_bus)
            logger.info("✅ 交易日志集成器已初始化")
            # 检查STRATEGY_SIGNAL事件的订阅者数量
            async_subscribers = self.event_bus._async_subscribers.get(EventType.STRATEGY_SIGNAL, [])
            logger.info(f"STRATEGY_SIGNAL事件的异步订阅者数量: {len(async_subscribers)}")
            for i, callback in enumerate(async_subscribers):
                logger.info(f"订阅者 {i}: {callback.__name__}")

            # 启动协调智能体
            logger.info("2️⃣ 启动协调智能体...")
            await self.coordinator.start()
            logger.info("✅ 协调智能体已启动")

            # 启动其他智能体
            logger.info("3️⃣ 启动市场数据智能体...")
            await self.market_data_agent.start()
            logger.info("✅ 市场数据智能体已启动")
            
            logger.info("4️⃣ 启动订单智能体...")
            await self.order_agent.start()
            logger.info("✅ 订单智能体已启动")
            
            logger.info("5️⃣ 启动风险智能体...")
            await self.risk_agent.start()
            logger.info("✅ 风险智能体已启动")
            
            logger.info("6️⃣ 启动策略智能体...")
            await self.strategy_agent.start()
            logger.info("✅ 策略智能体已启动")
            
            # 打印事件总线统计信息
            stats = self.event_bus.get_stats()
            logger.info(f"事件总线统计信息: {stats}")
            # 检查STRATEGY_SIGNAL事件的订阅者数量
            async_subscribers = self.event_bus._async_subscribers.get(EventType.STRATEGY_SIGNAL, [])
            logger.info(f"STRATEGY_SIGNAL事件的异步订阅者数量: {len(async_subscribers)}")
            
            logger.info("7️⃣ 启动账户同步智能体...")
            await self.account_sync_agent.start()
            logger.info("✅ 账户同步智能体已启动")
            
            # 初始化账户同步管理器
            logger.info("8️⃣ 初始化账户同步管理器...")
            try:
                from core.utils.account_sync import init_account_sync_manager
                init_account_sync_manager(self.order_agent.rest_client)
                logger.info("✅ 账户同步管理器已初始化")
            except Exception as e:
                logger.warning(f"⚠️ 账户同步管理器初始化失败: {e}")

            # 连接WebSocket
            logger.info("9️⃣ 连接WebSocket...")
            await self.ws_client.connect()
            logger.info("✅ WebSocket已连接")

            # 从环境配置获取默认策略，使用NuclearDynamicsStrategy以支持SS和SSS级信号
            logger.info("🔟 准备激活默认策略...")
            strategy_config = env_manager.get_strategy_config()
            default_strategy = strategy_config.get('default_strategy', 'NuclearDynamicsStrategy')
            logger.info(f"默认策略: {default_strategy}")
            logger.info("1️⃣1️⃣ 调用activate_strategy...")
            result = await self.strategy_agent.activate_strategy(default_strategy)
            logger.info(f"activate_strategy返回结果: {result}")
            logger.info("✅ 默认策略激活完成")

            # 初始化邮件发送器
            logger.info("1️⃣2️⃣ 初始化邮件发送器...")
            try:
                from core.utils.email_utils import init_email_sender
                # 使用配置文件中的邮件配置
                smtp_server = get_config("email.smtp_server", "smtp.qq.com")
                smtp_port = get_config("email.smtp_port", 587)
                sender_email = get_config("email.sender_email", "")
                sender_password = get_config("email.sender_password", "")
                
                if sender_email and sender_password and sender_password != "your_email_password":
                    init_email_sender(smtp_server, smtp_port, sender_email, sender_password)
                    logger.info("✅ 邮件发送器初始化完成")
                else:
                    logger.warning("⚠️ 邮件配置未设置或使用默认密码，邮件发送功能将不可用")
            except Exception as e:
                logger.warning(f"⚠️ 邮件发送器初始化失败: {e}")
            
            # 启动市场情绪分析监控
            logger.info("1️⃣3️⃣ 启动市场情绪分析监控...")
            market_config = env_manager.get_market_config()
            cryptocurrencies = market_config.get('cryptocurrencies', ["BTC", "ETH"])
            asyncio.ensure_future(self.sentiment_analyzer.start_monitoring(cryptocurrencies))
            logger.info("✅ 市场情绪分析监控已启动")

            # 启动API日志调度器（暂时禁用，避免事件循环冲突）
            logger.info("1️⃣4️⃣ 暂时禁用API日志调度器...")
            # self.api_log_scheduler = APILogScheduler()
            # import threading
            # api_log_thread = threading.Thread(target=self.api_log_scheduler.run_schedule)
            # api_log_thread.daemon = True
            # api_log_thread.start()
            logger.info("✅ API日志调度器已禁用")

            # 初始同步订单信息（已注释掉，避免显示过多历史订单）
            # logger.info("1️⃣5️⃣ 初始同步交易订单信息...")
            # await self.sync_orders()

            logger.info("交易机器人启动成功")

            # 发布系统启动事件
            logger.info("1️⃣6️⃣ 发布系统启动事件...")
            await self.event_bus.publish_async(
                Event(
                    type=EventType.SYSTEM_STARTUP,
                    source="trading_bot",
                    data={"status": "started"},
                )
            )
            logger.info("✅ 系统启动事件已发布")

            # 验证各种交易类型（已注释掉，避免启动时主动下单）
            # logger.info("1️⃣7️⃣ 验证各种交易类型...")
            # await self.validate_trade_types()
            # logger.info("✅ 交易类型验证完成")

            # 保持运行
            logger.info("🔄 进入主循环...")
            loop_count = 0
            try:
                while self._running:
                    loop_count += 1
                    if loop_count % 30 == 0:  # 每30秒输出一次日志
                        logger.info(f"✅ 主循环运行中... 循环次数: {loop_count}")
                    
                    # 每60秒同步一次订单信息
                    if loop_count % 60 == 0:
                        await self.sync_orders()
                    
                    await asyncio.sleep(1)
            except Exception as e:
                import traceback
                logger.error(f"❌ 主循环错误: {e}")
                logger.error(f"❌ 详细错误信息:\n{traceback.format_exc()}")
                raise
            logger.info("❌ 主循环已退出")

        except Exception as e:
            import traceback
            logger.error(f"❌ 交易机器人运行错误: {e}")
            logger.error(f"❌ 详细错误信息:\n{traceback.format_exc()}")
            logger.error(f"❌ 准备调用stop()方法...")
            await self.stop()

    async def stop(self):
        """停止交易机器人"""
        if not self._running:
            return

        self._running = False
        logger.info("正在停止交易机器人...")

        try:
            # 停止所有智能体
            if self.strategy_agent:
                await self.strategy_agent.stop()
            if self.risk_agent:
                await self.risk_agent.stop()
            if self.order_agent:
                await self.order_agent.stop()
            if self.market_data_agent:
                await self.market_data_agent.stop()
            if self.account_sync_agent:
                await self.account_sync_agent.stop()
            if self.coordinator:
                await self.coordinator.stop()

            # 关闭API客户端
            if self.ws_client:
                await self.ws_client.close()
            if self.rest_client:
                await self.rest_client.close()

            # 停止新功能模块
            if self.sentiment_analyzer:
                self.sentiment_analyzer.stop_monitoring()
                await self.sentiment_analyzer.shutdown()
            if self.notification_system:
                await self.notification_system.stop()

            # 停止事件总线
            self.event_bus.stop()

            logger.info("交易机器人已停止")

        except Exception as e:
            logger.error(f"停止交易机器人时出错: {e}")

    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            "running": self._running,
            "coordinator": self.coordinator.get_status() if self.coordinator else None,
            "agents": (
                self.coordinator.get_all_agents_status() if self.coordinator else []
            ),
            "account_sync": self.account_sync_agent.get_status() if self.account_sync_agent else None,
            "trading_summary": self.get_trading_summary() if self.coordinator else None,
        }

    def get_trading_summary(self) -> Dict[str, Any]:
        """获取交易摘要"""
        if self.coordinator and hasattr(self.coordinator, "get_trading_summary"):
            return self.coordinator.get_trading_summary()
        return {}


async def main():
    """主函数"""
    # 创建日志目录
    os.makedirs("logs", exist_ok=True)

    # 解析命令行参数
    parser = argparse.ArgumentParser(description="OKX交易机器人")
    parser.add_argument("--trade-amount", type=float, help="固定交易金额(USDT)")
    parser.add_argument("--trade-percentage", type=float, help="交易金额占可用余额的比例")
    parser.add_argument("--trading-mode", help="交易模式: cash(现货), cross(全仓杠杆), isolated(逐仓杠杆)")
    parser.add_argument("--strategy", help="策略名称")
    parser.add_argument("--env", help="环境: live(实盘), test(模拟盘)")
    parser.add_argument("--cryptocurrencies", nargs="+", help="监控的加密货币列表")
    
    args = parser.parse_args()

    # 创建配置字典
    config = {}
    
    # 处理命令行参数
    if args.trade_amount is not None:
        config['trading'] = config.get('trading', {})
        config['trading']['fixed_trade_amount'] = args.trade_amount
    
    if args.trade_percentage is not None:
        config['trading'] = config.get('trading', {})
        config['trading']['trade_amount_percentage'] = args.trade_percentage
    
    if args.trading_mode:
        config['trading'] = config.get('trading', {})
        config['trading']['default_trading_mode'] = args.trading_mode
    
    if args.strategy:
        config['strategy'] = config.get('strategy', {})
        config['strategy']['default_strategy'] = args.strategy
    
    if args.env:
            # 切换环境
            if args.env == 'live':
                env_manager.switch_to_live()
            elif args.env == 'test':
                env_manager.switch_to_test()
    
    if args.cryptocurrencies:
        config['market'] = config.get('market', {})
        config['market']['cryptocurrencies'] = args.cryptocurrencies

    # 创建交易机器人
    bot = TradingBot()

    try:
        # 初始化
        await bot.initialize(config)  # 使用命令行参数和配置文件中的设置

        # 启动
        await bot.start()

    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止...")
        await bot.stop()
    except Exception as e:
        logger.error(f"主程序错误: {e}")
        await bot.stop()


if __name__ == "__main__":
    # 运行主程序
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
