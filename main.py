import sys
import os
import time

# 禁用Qt样式表警告
os.environ["QT_LOGGING_RULES"] = "qt.qpa.style.warning=false"

# 导入QtCore模块来禁用Qt日志
from PyQt5.QtCore import Qt, QLoggingCategory

# 禁用Qt样式警告
QLoggingCategory.setFilterRules("qt.qpa.style.warning=false")

from PyQt5.QtWidgets import QApplication

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 初始化日志配置
from commons.logger_config import global_logger as logger
logger.info("启动交易机器人...")

# 初始化健康检查器
from commons.health_checker import global_health_checker

# 初始化告警管理器
from commons.alert_manager import global_alert_manager

# 初始化进程监控
from commons.process_monitor import global_process_monitor

from commons.agent_registry import global_agent_registry
from commons.event_bus import global_event_bus

# 导入所有智能体
from agents.market_data_agent import MarketDataAgent
from agents.order_agent import OrderAgent
from agents.risk_management_agent import RiskManagementAgent
from agents.strategy_execution_agent import StrategyExecutionAgent
from agents.decision_coordination_agent import DecisionCoordinationAgent

# 导入策略基类
from strategies.base_strategy import BaseStrategy

class TradingBot:
    """交易机器人主类"""
    
    def __init__(self, config_path="config/okx_config.json"):
        """初始化交易机器人
        
        Args:
            config_path (str): 配置文件路径
        """
        # 导入配置管理器
        from commons.config_manager import global_config_manager
        
        # 使用全局配置管理器
        self.config_manager = global_config_manager
        self.config = self.config_manager.get_config()
        self.agents = {}
        self.app = None
        
        logger.info("交易机器人初始化完成")
    
    def run_network_adaptation(self):
        """Run network auto-adaptation during initialization"""
        # 检查是否启用网络适配
        enable_network_adaptation = self.config.get("network", {}).get("enable_adaptation", True)
        if not enable_network_adaptation:
            logger.info("网络适配已禁用")
            return
        
        logger.info("开始运行网络自动适配...")
        try:
            from okx_api_client import OKXAPIClient
            api_client = OKXAPIClient()
            success = api_client.run_network_adapter(auto_update=True)
            if success:
                logger.info("网络自动适配完成，配置已更新")
            else:
                logger.warning("网络自动适配失败，将使用现有配置继续运行")
        except Exception as e:
            logger.error(f"运行网络自动适配时出错: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
    

    
    def init_agents(self):
        """初始化所有智能体"""
        logger.info("开始初始化智能体...")
        
        # 获取API配置
        api_config = self.config.get("api", {})
        
        # 初始化市场数据智能体
        market_data_agent = MarketDataAgent(
            agent_id="market_data_agent",
            config={
                "api_key": api_config.get("api_key"),
                "api_secret": api_config.get("api_secret"),
                "passphrase": api_config.get("passphrase"),
                "is_test": api_config.get("is_test", True),
                "update_interval": self.config.get("market_data", {}).get("update_interval", 1)
            }
        )
        self.agents["market_data_agent"] = market_data_agent
        global_agent_registry.register_agent(market_data_agent)
        
        # 初始化订单管理智能体
        order_agent = OrderAgent(
            agent_id="order_agent",
            config={
                "api_key": api_config.get("api_key"),
                "api_secret": api_config.get("api_secret"),
                "passphrase": api_config.get("passphrase"),
                "is_test": api_config.get("is_test", True)
            }
        )
        self.agents["order_agent"] = order_agent
        global_agent_registry.register_agent(order_agent)
        
        # 初始化风险控制智能体
        risk_management_agent = RiskManagementAgent(
            agent_id="risk_management_agent",
            config={
                "api_key": api_config.get("api_key"),
                "api_secret": api_config.get("api_secret"),
                "passphrase": api_config.get("passphrase"),
                "is_test": api_config.get("is_test", True),
                **self.config.get("risk_management", {})
            }
        )
        self.agents["risk_management_agent"] = risk_management_agent
        global_agent_registry.register_agent(risk_management_agent)
        
        # 初始化策略执行智能体
        strategy_execution_agent = StrategyExecutionAgent(
            agent_id="strategy_execution_agent",
            config={
                "strategy_configs": self.config.get("strategy_configs", {}),
                "strategy_extension_path": self.config.get("strategy_extension_path", "strategies")
            }
        )
        self.agents["strategy_execution_agent"] = strategy_execution_agent
        global_agent_registry.register_agent(strategy_execution_agent)
        
        # 初始化决策协调智能体
        decision_coordination_agent = DecisionCoordinationAgent(
            agent_id="decision_coordination_agent",
            config={}
        )
        self.agents["decision_coordination_agent"] = decision_coordination_agent
        global_agent_registry.register_agent(decision_coordination_agent)
        
        logger.info(f"智能体初始化完成，共 {len(self.agents)} 个智能体")
    
    def start_agents(self):
        """启动所有智能体"""
        logger.info("开始启动智能体...")
        
        # 按顺序启动智能体
        start_order = [
            "decision_coordination_agent",
            "market_data_agent",
            "risk_management_agent",
            "strategy_execution_agent",
            "order_agent"
        ]
        
        for agent_id in start_order:
            if agent_id in self.agents:
                agent = self.agents[agent_id]
                agent.start()
                logger.info(f"智能体启动成功: {agent_id}")
        
        logger.info("所有智能体启动完成")
    
    def stop_agents(self):
        """停止所有智能体"""
        logger.info("开始停止智能体...")
        
        # 按相反顺序停止智能体
        stop_order = [
            "order_agent",
            "strategy_execution_agent",
            "risk_management_agent",
            "market_data_agent",
            "decision_coordination_agent"
        ]
        
        for agent_id in stop_order:
            if agent_id in self.agents:
                agent = self.agents[agent_id]
                agent.stop()
                logger.info(f"智能体停止成功: {agent_id}")
        
        # 停止健康检查器
        global_health_checker.stop()
        logger.info("健康检查器已停止")
        
        # 停止告警管理器
        global_alert_manager.stop()
        logger.info("告警管理器已停止")
        
        # 更新服务状态
        global_health_checker.update_check_status(
            'services',
            'FAIL',
            '交易机器人服务已停止',
            running_services=[],
            stopped_services=list(self.agents.keys())
        )
        
        logger.info("所有智能体停止完成")
    
    def start_gui(self):
        """启动GUI界面"""
        logger.info("启动交易界面...")
        
        from trading_gui import TradingGUI
        
        # 直接使用已创建的QApplication实例，不再重新创建
        gui = TradingGUI(self.config, self)
        gui.show()
        
        logger.info("交易界面启动完成")
        return self.app.exec_()
    
    def load_features(self):
        """加载功能：网络适配和智能体初始化"""
        logger.info("开始加载功能...")
        
        try:
            # 检查是否启用网络适配
            enable_network_adaptation = self.config.get("network", {}).get("enable_adaptation", True)
            if enable_network_adaptation:
                # 先执行网络适配
                self.run_network_adaptation()
            else:
                logger.info("网络适配已禁用")
            
            # 初始化智能体
            self.init_agents()
            
            # 启动智能体
            self.start_agents()
            
            # 订阅默认交易对
            decision_agent = self.agents.get("decision_coordination_agent")
            if decision_agent:
                decision_agent.add_symbol_subscription(self.config.get("symbol", "BTC-USDT-SWAP"))
            
            # 注意：不再自动激活默认策略，需要用户手动激活
            logger.info("智能体初始化完成，策略需要手动激活")
        except Exception as e:
            logger.error(f"初始化和启动智能体失败: {e}", exc_info=True)

    def start(self, use_gui=True):
        """启动交易机器人
        
        Args:
            use_gui (bool): 是否使用GUI界面
            
        Returns:
            int: 退出码
        """
        try:
            # 启动健康检查器
            global_health_checker.start()
            
            # 启动告警管理器
            global_alert_manager.start()
            
            # 启动进程监控
            global_process_monitor.start_monitoring()
            
            # 更新服务状态
            global_health_checker.update_check_status(
                'services',
                'PASS',
                '交易机器人服务启动成功',
                running_services=list(self.agents.keys()),
                stopped_services=[]
            )
            
            # 启动GUI
            if use_gui:
                # 先创建QApplication实例
                self.app = QApplication(sys.argv)
                logger.info("启动交易界面...")
                from trading_gui import TradingGUI
                gui = TradingGUI(self.config, self)
                gui.show()
                logger.info("交易界面启动完成")
                
                # 自动加载功能
                self.load_features()
                
                # 运行应用程序事件循环
                return self.app.exec_()
            else:
                # 无GUI模式，保持程序运行
                logger.info("交易机器人以无GUI模式启动")
                
                # 自动加载功能
                self.load_features()
                
                # 保持程序运行，等待用户中断
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    logger.info("交易机器人被用户中断")
        
        except KeyboardInterrupt:
            logger.info("交易机器人被用户中断")
        except Exception as e:
            logger.error(f"交易机器人运行失败: {e}", exc_info=True)
        finally:
            # 停止所有智能体
            self.stop_agents()
            
            # 停止进程监控
            global_process_monitor.stop_monitoring()
        
        return 0
    
    def get_agent(self, agent_id):
        """获取智能体
        
        Args:
            agent_id (str): 智能体ID
            
        Returns:
            BaseAgent: 智能体实例
        """
        return self.agents.get(agent_id)
    
    def register_strategy(self, strategy_class):
        """注册自定义策略
        
        Args:
            strategy_class (type): 策略类，必须继承自BaseStrategy
            
        Returns:
            bool: 是否注册成功
        """
        if not issubclass(strategy_class, BaseStrategy):
            logger.error(f"策略类 {strategy_class.__name__} 必须继承自 BaseStrategy")
            return False
        
        strategy_agent = self.agents.get("strategy_execution_agent")
        if not strategy_agent:
            logger.error("策略执行智能体未初始化")
            return False
        
        # 创建策略实例
        strategy_name = strategy_class.__name__
        strategy_config = self.config.get("strategy_configs", {}).get(strategy_name, {})
        strategy_instance = strategy_class(config=strategy_config)
        
        # 注册策略
        strategy_agent.strategies[strategy_name] = strategy_instance
        
        # 发布策略注册事件
        global_event_bus.publish('strategy_registered', {
            "strategy_name": strategy_name,
            "strategy_class": strategy_name,
            "module": strategy_class.__module__,
            "timestamp": self.get_current_timestamp()
        })
        
        logger.info(f"自定义策略注册成功: {strategy_name}")
        return True
    
    def get_current_timestamp(self):
        """获取当前时间戳
        
        Returns:
            float: 当前时间戳
        """
        import time
        return time.time()

# 策略扩展端口使用示例
# 要添加新策略，只需创建一个继承自BaseStrategy的策略类，并实现execute方法
# 示例：
# 
# from strategies.base_strategy import BaseStrategy
# 
# class MyCustomStrategy(BaseStrategy):
#     """自定义策略示例"""
#     
#     def __init__(self, config=None):
#         super().__init__(config)
#         self.name = "MyCustomStrategy"
#         self.params = {
#             "ma_period": config.get("ma_period", 20),
#             "threshold": config.get("threshold", 0.01)
#         }
#     
#     def execute(self, market_data):
#         """执行策略，生成交易信号
#         
#         Args:
#             market_data (dict): 市场数据
#             
#         Returns:
#             dict: 交易信号，包含side, price, amount等信息
#         """
#         # 实现自定义策略逻辑
#         # ...
#         
#         # 返回交易信号
#         return {
#             "side": "buy",  # buy或sell
#             "price": market_data.get("price"),
#             "amount": 0.001,
#             "symbol": market_data.get("symbol"),
#             "leverage": 1,
#             "signal_strength": 0.8
#         }
# 
# # 然后在主程序中注册该策略
# trading_bot.register_strategy(MyCustomStrategy)

if __name__ == "__main__":
    try:
        # 创建交易机器人实例
        logger.info("创建交易机器人实例...")
        trading_bot = TradingBot()
        
        # 启动交易机器人
        logger.info("启动交易机器人...")
        exit_code = trading_bot.start(use_gui=True)
        
        logger.info(f"交易机器人退出，退出码: {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"交易机器人启动失败: {e}")
        import traceback
        logger.error(f"异常堆栈: {traceback.format_exc()}")
        sys.exit(1)
