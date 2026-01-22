from loguru import logger
from agents.base_agent import BaseAgent
import importlib.util
import os
import time

class StrategyExecutionAgent(BaseAgent):
    """策略执行智能体，负责管理和执行各种交易策略"""
    
    def __init__(self, agent_id, config=None):
        super().__init__(agent_id, config)
        self.strategies = {}  # 已加载的策略实例
        self.strategy_modules = {}  # 策略模块
        self.active_strategies = set()  # 激活的策略
        self.strategy_extension_path = config.get("strategy_extension_path", "strategies")  # 策略扩展路径
        self.market_data_cache = {}  # 市场数据缓存
        
        # 订阅事件
        self.subscribe('market_data_updated', self.on_market_data_updated)
        self.subscribe('risk_check_passed', self.on_risk_check_passed)
        self.subscribe('strategy_registered', self.on_strategy_registered)
        
        # 初始化时加载所有策略
        self.load_all_strategies()
        
        logger.info(f"策略执行智能体初始化完成: {self.agent_id}")
    
    def start(self):
        """启动策略执行智能体"""
        super().start()
        
        # 启动策略执行循环
        self.run_in_thread(self.strategy_execution_loop)
        
        logger.info(f"策略执行智能体启动完成: {self.agent_id}")
    
    def stop(self):
        """停止策略执行智能体"""
        super().stop()
        
        # 停止所有激活的策略
        for strategy_name in list(self.active_strategies):
            self.deactivate_strategy(strategy_name)
        
        logger.info(f"策略执行智能体停止完成: {self.agent_id}")
    
    def load_all_strategies(self):
        """加载所有策略"""
        logger.info(f"开始加载策略，扩展路径: {self.strategy_extension_path}")
        
        # 加载内置策略
        self.load_strategies_from_path(os.path.join(os.path.dirname(__file__), "..", self.strategy_extension_path))
        
        logger.info(f"策略加载完成，共加载 {len(self.strategies)} 个策略")
    
    def load_strategies_from_path(self, path):
        """从指定路径加载策略
        
        Args:
            path (str): 策略文件路径
        """
        try:
            # 遍历路径下的所有Python文件
            for file_name in os.listdir(path):
                if file_name.endswith(".py") and not file_name.startswith("__") and file_name != "base_strategy.py":
                    # 构建模块名和文件路径
                    module_name = file_name[:-3]  # 去掉.py后缀
                    file_path = os.path.join(path, file_name)
                    
                    # 加载模块
                    spec = importlib.util.spec_from_file_location(module_name, file_path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        
                        # 查找继承自BaseStrategy的类
                        from strategies.base_strategy import BaseStrategy
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if isinstance(attr, type) and issubclass(attr, BaseStrategy) and attr != BaseStrategy:
                                # 实例化策略
                                strategy_name = attr.__name__
                                strategy_instance = attr(config=self.config.get("strategy_configs", {}).get(strategy_name, {}))
                                
                                # 保存策略实例和模块
                                self.strategies[strategy_name] = strategy_instance
                                self.strategy_modules[strategy_name] = module
                                
                                # 发布策略注册事件
                                self.publish('strategy_registered', {
                                    "strategy_name": strategy_name,
                                    "strategy_class": strategy_name,
                                    "module": module_name,
                                    "timestamp": time.time()
                                })
                                
                                logger.info(f"加载策略成功: {strategy_name} from {file_name}")
        
        except Exception as e:
            logger.error(f"加载策略失败: {e}")
    
    def strategy_execution_loop(self):
        """策略执行循环"""
        while self.status == 'running':
            try:
                # 执行所有激活的策略
                if self.active_strategies:
                    for strategy_name in self.active_strategies:
                        strategy = self.strategies.get(strategy_name)
                        if strategy and strategy.status == "running":
                            # 获取所有订阅的市场数据
                            for symbol in self.market_data_cache:
                                market_data = self.market_data_cache[symbol]
                                # 执行策略，生成交易信号
                                self.execute_strategy(strategy, market_data)
                
                # 等待下一次执行
                time.sleep(0.5)  # 每0.5秒执行一次策略
            
            except Exception as e:
                logger.error(f"策略执行循环失败: {e}")
                time.sleep(0.5)
    
    def execute_strategy(self, strategy, market_data):
        """执行策略
        
        Args:
            strategy (BaseStrategy): 策略实例
            market_data (dict): 市场数据
        """
        try:
            # 执行策略，生成交易信号
            signal = strategy.execute(market_data)
            
            if signal:
                # 添加上下文信息
                signal.update({
                    "strategy": strategy.name,
                    "timestamp": time.time(),
                    "symbol": market_data.get("symbol"),
                })
                
                # 发布交易信号
                self.publish('trading_signal', signal)
                
                logger.info(f"策略 {strategy.name} 生成交易信号: {signal}")
        
        except Exception as e:
            logger.error(f"执行策略 {strategy.name} 失败: {e}")
    
    def on_market_data_updated(self, data):
        """处理市场数据更新事件
        
        Args:
            data (dict): 市场数据
        """
        try:
            symbol = data.get("symbol")
            if symbol:
                # 更新市场数据缓存
                self.market_data_cache[symbol] = data.get("data", {})
                
                # 对于激活的策略，立即执行
                for strategy_name in self.active_strategies:
                    strategy = self.strategies.get(strategy_name)
                    if strategy and strategy.status == "running":
                        self.execute_strategy(strategy, self.market_data_cache[symbol])
        
        except Exception as e:
            logger.error(f"处理市场数据更新失败: {e}")
    
    def on_risk_check_passed(self, data):
        """处理风险检查通过事件
        
        Args:
            data (dict): 风险检查通过数据
        """
        logger.info(f"风险检查通过，交易信号将被执行: {data}")
    
    def on_strategy_registered(self, data):
        """处理策略注册事件
        
        Args:
            data (dict): 策略注册数据
        """
        logger.info(f"策略注册事件: {data}")
    
    def activate_strategy(self, strategy_name):
        """激活策略
        
        Args:
            strategy_name (str): 策略名称
        """
        if strategy_name in self.strategies:
            strategy = self.strategies[strategy_name]
            if strategy.status != "running":
                # 如果策略是暂停状态，恢复它；否则启动它
                if strategy.status == "paused":
                    strategy.resume()
                else:
                    strategy.start()
                
                self.active_strategies.add(strategy_name)
                
                # 发布策略激活事件
                self.publish('strategy_activated', {
                    "strategy_name": strategy_name,
                    "status": "activated",
                    "timestamp": time.time()
                })
                
                logger.info(f"激活策略成功: {strategy_name}")
                return True
            else:
                logger.warning(f"策略已激活: {strategy_name}")
                return False
        else:
            logger.error(f"策略不存在: {strategy_name}")
            return False
    
    def deactivate_strategy(self, strategy_name):
        """停用策略
        
        Args:
            strategy_name (str): 策略名称
        """
        if strategy_name in self.active_strategies:
            if strategy_name in self.strategies:
                strategy = self.strategies[strategy_name]
                strategy.stop()
            
            self.active_strategies.remove(strategy_name)
            
            # 发布策略停用事件
            self.publish('strategy_deactivated', {
                "strategy_name": strategy_name,
                "status": "deactivated",
                "timestamp": time.time()
            })
            
            logger.info(f"停用策略成功: {strategy_name}")
            return True
        else:
            logger.warning(f"策略未激活: {strategy_name}")
            return False
    
    def pause_strategy(self, strategy_name):
        """暂停策略
        
        Args:
            strategy_name (str): 策略名称
        """
        if strategy_name in self.strategies:
            strategy = self.strategies[strategy_name]
            if strategy.status == "running":
                strategy.pause()
                
                # 发布策略暂停事件
                self.publish('strategy_paused', {
                    "strategy_name": strategy_name,
                    "status": "paused",
                    "timestamp": time.time()
                })
                
                logger.info(f"暂停策略成功: {strategy_name}")
                return True
            else:
                logger.warning(f"策略不在运行状态，无法暂停: {strategy_name}")
                return False
        else:
            logger.error(f"策略不存在: {strategy_name}")
            return False
    
    def resume_strategy(self, strategy_name):
        """恢复策略
        
        Args:
            strategy_name (str): 策略名称
        """
        if strategy_name in self.strategies:
            strategy = self.strategies[strategy_name]
            if strategy.status == "paused":
                strategy.resume()
                
                # 发布策略恢复事件
                self.publish('strategy_resumed', {
                    "strategy_name": strategy_name,
                    "status": "resumed",
                    "timestamp": time.time()
                })
                
                logger.info(f"恢复策略成功: {strategy_name}")
                return True
            else:
                logger.warning(f"策略不在暂停状态，无法恢复: {strategy_name}")
                return False
        else:
            logger.error(f"策略不存在: {strategy_name}")
            return False
    
    def list_strategies(self):
        """列出所有策略
        
        Returns:
            list: 策略列表
        """
        strategy_list = []
        for strategy_name, strategy in self.strategies.items():
            # 状态映射：英文 -> 中文
            status_map = {
                "idle": "已停用",
                "running": "已激活",
                "paused": "已暂停"
            }
            # 使用策略实例的实际状态，而不是active_strategies集合
            actual_status = strategy.status
            strategy_list.append({
                "name": strategy_name,
                "status": status_map[actual_status],
                "class": strategy.__class__.__name__,
                "params": strategy.get_params(),
                "performance": strategy.performance
            })
        return strategy_list
    
    def get_strategy(self, strategy_name):
        """获取策略
        
        Args:
            strategy_name (str): 策略名称
            
        Returns:
            BaseStrategy: 策略实例
        """
        return self.strategies.get(strategy_name)
    
    def update_strategy_params(self, strategy_name, params):
        """更新策略参数
        
        Args:
            strategy_name (str): 策略名称
            params (dict): 策略参数
            
        Returns:
            bool: 是否更新成功
        """
        if strategy_name in self.strategies:
            strategy = self.strategies[strategy_name]
            strategy.set_params(params)
            logger.info(f"更新策略参数成功: {strategy_name}, 新参数: {params}")
            return True
        else:
            logger.error(f"策略不存在: {strategy_name}")
            return False
    
    def reload_strategy(self, strategy_name):
        """重新加载策略
        
        Args:
            strategy_name (str): 策略名称
            
        Returns:
            bool: 是否重新加载成功
        """
        if strategy_name in self.strategies:
            # 先停用策略
            self.deactivate_strategy(strategy_name)
            
            # 移除旧策略
            del self.strategies[strategy_name]
            if strategy_name in self.strategy_modules:
                del self.strategy_modules[strategy_name]
            
            # 重新加载所有策略
            self.load_all_strategies()
            
            logger.info(f"重新加载策略成功: {strategy_name}")
            return True
        else:
            logger.error(f"策略不存在: {strategy_name}")
            return False
    
    def add_strategy_extension(self, extension_path):
        """添加策略扩展路径
        
        Args:
            extension_path (str): 策略扩展路径
            
        Returns:
            bool: 是否添加成功
        """
        try:
            # 加载扩展路径下的策略
            self.load_strategies_from_path(extension_path)
            logger.info(f"添加策略扩展路径成功: {extension_path}")
            return True
        except Exception as e:
            logger.error(f"添加策略扩展路径失败: {e}")
            return False
    
    def process_message(self, message):
        """处理收到的消息
        
        Args:
            message (dict): 消息内容
        """
        super().process_message(message)
        
        if message.get('type') == 'list_strategies':
            # 列出所有策略请求
            if message.get('sender'):
                self.send_message(message.get('sender'), {
                    'type': 'list_strategies_response',
                    'strategies': self.list_strategies()
                })
        
        elif message.get('type') == 'activate_strategy':
            # 激活策略请求
            strategy_name = message.get('strategy_name')
            result = self.activate_strategy(strategy_name)
            if message.get('sender'):
                self.send_message(message.get('sender'), {
                    'type': 'activate_strategy_response',
                    'result': result,
                    'strategy_name': strategy_name
                })
        
        elif message.get('type') == 'deactivate_strategy':
            # 停用策略请求
            strategy_name = message.get('strategy_name')
            result = self.deactivate_strategy(strategy_name)
            if message.get('sender'):
                self.send_message(message.get('sender'), {
                    'type': 'deactivate_strategy_response',
                    'result': result,
                    'strategy_name': strategy_name
                })
        elif message.get('type') == 'pause_strategy':
            # 暂停策略请求
            strategy_name = message.get('strategy_name')
            result = self.pause_strategy(strategy_name)
            if message.get('sender'):
                self.send_message(message.get('sender'), {
                    'type': 'pause_strategy_response',
                    'result': result,
                    'strategy_name': strategy_name
                })
        elif message.get('type') == 'resume_strategy':
            # 恢复策略请求
            strategy_name = message.get('strategy_name')
            result = self.resume_strategy(strategy_name)
            if message.get('sender'):
                self.send_message(message.get('sender'), {
                    'type': 'resume_strategy_response',
                    'result': result,
                    'strategy_name': strategy_name
                })
        
        elif message.get('type') == 'update_strategy_params':
            # 更新策略参数请求
            strategy_name = message.get('strategy_name')
            params = message.get('params', {})
            result = self.update_strategy_params(strategy_name, params)
            if message.get('sender'):
                self.send_message(message.get('sender'), {
                    'type': 'update_strategy_params_response',
                    'result': result,
                    'strategy_name': strategy_name,
                    'params': params
                })
        
        elif message.get('type') == 'reload_strategy':
            # 重新加载策略请求
            strategy_name = message.get('strategy_name')
            result = self.reload_strategy(strategy_name)
            if message.get('sender'):
                self.send_message(message.get('sender'), {
                    'type': 'reload_strategy_response',
                    'result': result,
                    'strategy_name': strategy_name
                })
        
        elif message.get('type') == 'add_strategy_extension':
            # 添加策略扩展路径请求
            extension_path = message.get('extension_path')
            result = self.add_strategy_extension(extension_path)
            if message.get('sender'):
                self.send_message(message.get('sender'), {
                    'type': 'add_strategy_extension_response',
                    'result': result,
                    'extension_path': extension_path
                })
        
        elif message.get('type') == 'get_strategy':
            # 获取策略请求
            strategy_name = message.get('strategy_name')
            strategy = self.get_strategy(strategy_name)
            if message.get('sender'):
                if strategy:
                    # 使用策略实例的实际状态
                    status_map = {
                        "idle": "deactivated",
                        "running": "activated",
                        "paused": "paused"
                    }
                    actual_status = status_map[strategy.status]
                else:
                    actual_status = "deactivated"
                
                self.send_message(message.get('sender'), {
                    'type': 'get_strategy_response',
                    'strategy': {
                        "name": strategy_name,
                        "status": actual_status,
                        "params": strategy.get_params() if strategy else {},
                        "performance": strategy.performance if strategy else {}
                    }
                })
