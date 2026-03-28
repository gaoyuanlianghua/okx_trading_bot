from commons.logger_config import get_logger
logger = get_logger(region="Strategy")
from agents.base_agent import BaseAgent
import importlib.util
import os
import time

# 导入策略基类
try:
    from strategies.base_strategy import BaseStrategy
except ImportError as e:
    logger.error(f"导入BaseStrategy失败: {e}")
    BaseStrategy = None

class StrategyExecutionAgent(BaseAgent):
    """策略执行智能体，负责管理和执行各种交易策略"""
    
    def __init__(self, agent_id, config=None):
        super().__init__(agent_id, config)
        self.strategies = {}  # 已加载的策略实例
        self.strategy_modules = {}  # 策略模块
        self.active_strategies = set()  # 激活的策略
        self.strategy_extension_path = config.get("strategy_extension_path", "strategies")  # 策略扩展路径
        self.market_data_cache = {}  # 市场数据缓存
        self.market_environment = {  # 市场环境分析
            "volatility": 0.0,  # 市场波动率
            "trend_strength": 0.0,  # 趋势强度
            "market_phase": "neutral",  # 市场阶段: bullish, bearish, neutral, volatile
            "liquidity": 0.0,  # 流动性指标
        }
        self.strategy_params_history = {}  # 策略参数历史
        self.adaptive_params_config = config.get("adaptive_params_config", {})  # 自适应参数配置
        self.param_adjustment_interval = 300  # 参数调整间隔（秒）
        self.last_adjustment_time = 0
        
        # 订阅事件
        self.subscribe('market_data_updated', self.on_market_data_updated)
        self.subscribe('risk_check_passed', self.on_risk_check_passed)
        self.subscribe('strategy_registered', self.on_strategy_registered)
        self.subscribe('risk_rules_updated', self.on_risk_rules_updated)
        
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
                        try:
                            module = importlib.util.module_from_spec(spec)
                            # 执行模块，捕获所有异常，确保单个策略加载失败不会影响其他策略
                            try:
                                spec.loader.exec_module(module)
                            except Exception as exec_error:
                                logger.warning(f"执行策略模块 {module_name} 时出错: {exec_error}")
                                # 继续处理下一个文件，不影响其他策略
                                continue
                            
                            # 查找继承自BaseStrategy的类
                            try:
                                if BaseStrategy is None:
                                    logger.error("BaseStrategy未成功导入，无法加载策略")
                                    continue
                                for attr_name in dir(module):
                                    attr = getattr(module, attr_name)
                                    if isinstance(attr, type) and issubclass(attr, BaseStrategy) and attr != BaseStrategy:
                                        # 实例化策略
                                        strategy_name = attr.__name__
                                        try:
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
                                            logger.warning(f"实例化策略 {strategy_name} 失败: {e}")
                            except Exception as e:
                                logger.warning(f"查找策略类失败: {e}")
                        except Exception as e:
                            logger.warning(f"加载策略模块 {module_name} 失败: {e}")
        
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
                            # 分析市场环境
                            self.analyze_market_environment()
                            
                            # 自适应调整策略参数
                            self.adjust_strategy_parameters()
                            
                            # 获取所有订阅的市场数据
                            for symbol in self.market_data_cache:
                                market_data = self.market_data_cache[symbol]
                                # 执行策略，生成交易信号
                                self.execute_strategy(strategy, market_data)
                    
                    # 有活跃策略时，保持较高的执行频率
                    time.sleep(0.5)  # 每0.5秒执行一次策略
                else:
                    # 没有活跃策略时，降低执行频率，减少资源消耗
                    time.sleep(5)  # 每5秒检查一次是否有活跃策略
            
            except Exception as e:
                logger.error(f"策略执行循环失败: {e}")
                time.sleep(1)
    
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
    
    def activate_strategy(self, strategy_name, strategy_config=None):
        """激活策略
        
        Args:
            strategy_name (str): 策略名称
            strategy_config (dict): 策略配置（可选）
        """
        if strategy_name in self.strategies:
            strategy = self.strategies[strategy_name]
            
            # 如果提供了配置，更新策略参数
            if strategy_config:
                strategy.set_params(strategy_config)
                logger.info(f"更新策略 {strategy_name} 配置: {strategy_config}")
            
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
    
    def analyze_market_environment(self):
        """分析市场环境"""
        try:
            if not self.market_data_cache:
                return
            
            # 计算市场波动率
            volatilities = []
            for symbol, data in self.market_data_cache.items():
                if data and 'change_pct' in data:
                    volatilities.append(abs(data['change_pct']))
            
            if volatilities:
                self.market_environment["volatility"] = sum(volatilities) / len(volatilities)
            
            # 分析市场阶段
            self._analyze_market_phase()
            
            # 分析趋势强度
            self._analyze_trend_strength()
            
        except Exception as e:
            logger.error(f"分析市场环境失败: {e}")
    
    def _analyze_market_phase(self):
        """分析市场阶段"""
        volatility = self.market_environment["volatility"]
        
        if volatility < 0.5:
            self.market_environment["market_phase"] = "neutral"
        elif volatility < 1.5:
            # 基于价格变化判断牛市/熊市
            trend_indicators = []
            for symbol, data in self.market_data_cache.items():
                if data and 'change' in data:
                    trend_indicators.append(data['change'])
            
            if trend_indicators:
                avg_change = sum(trend_indicators) / len(trend_indicators)
                if avg_change > 0.5:
                    self.market_environment["market_phase"] = "bullish"
                elif avg_change < -0.5:
                    self.market_environment["market_phase"] = "bearish"
                else:
                    self.market_environment["market_phase"] = "neutral"
        else:
            self.market_environment["market_phase"] = "volatile"
    
    def _analyze_trend_strength(self):
        """分析趋势强度"""
        trend_strengths = []
        for symbol, data in self.market_data_cache.items():
            if data and 'change_pct' in data:
                trend_strengths.append(abs(data['change_pct']))
        
        if trend_strengths:
            self.market_environment["trend_strength"] = sum(trend_strengths) / len(trend_strengths)
    
    def adjust_strategy_parameters(self):
        """自适应调整策略参数"""
        current_time = time.time()
        if current_time - self.last_adjustment_time < self.param_adjustment_interval:
            return
        
        try:
            for strategy_name in self.active_strategies:
                strategy = self.strategies.get(strategy_name)
                if strategy:
                    # 基于市场环境调整策略参数
                    new_params = self._calculate_adaptive_params(strategy_name, strategy)
                    if new_params:
                        # 更新策略参数
                        strategy.set_params(new_params)
                        
                        # 保存参数历史
                        self._save_params_history(strategy_name, new_params)
                        
                        # 发布参数更新事件
                        self.publish('strategy_params_updated', {
                            "strategy_name": strategy_name,
                            "params": new_params,
                            "market_environment": self.market_environment,
                            "timestamp": time.time()
                        })
            
            self.last_adjustment_time = current_time
            
        except Exception as e:
            logger.error(f"调整策略参数失败: {e}")
    
    def _calculate_adaptive_params(self, strategy_name, strategy):
        """计算自适应参数
        
        Args:
            strategy_name (str): 策略名称
            strategy (BaseStrategy): 策略实例
            
        Returns:
            dict: 新的策略参数
        """
        current_params = strategy.get_params()
        new_params = current_params.copy()
        
        # 根据市场环境调整参数
        market_phase = self.market_environment["market_phase"]
        volatility = self.market_environment["volatility"]
        
        # 基于策略类型和市场环境调整参数
        if hasattr(strategy, 'name'):
            strategy_type = strategy.name.lower()
            
            # 趋势策略参数调整
            if 'trend' in strategy_type:
                if market_phase == "bullish":
                    # 牛市环境下，增加趋势跟踪灵敏度
                    if 'trend_ma_period' in new_params:
                        new_params['trend_ma_period'] = max(5, int(new_params['trend_ma_period'] * 0.8))
                    if 'stop_loss_pct' in new_params:
                        new_params['stop_loss_pct'] = max(0.01, new_params['stop_loss_pct'] * 0.9)
                elif market_phase == "bearish":
                    # 熊市环境下，降低风险敞口
                    if 'position_size' in new_params:
                        new_params['position_size'] = max(0.1, new_params['position_size'] * 0.7)
                    if 'stop_loss_pct' in new_params:
                        new_params['stop_loss_pct'] = min(0.1, new_params['stop_loss_pct'] * 1.2)
            
            # 均值回归策略参数调整
            if 'mean_reversion' in strategy_type or 'mean' in strategy_type:
                if market_phase == "volatile":
                    # 高波动环境下，增加回归阈值
                    if 'threshold' in new_params:
                        new_params['threshold'] = min(0.05, new_params['threshold'] * 1.5)
                    if 'position_size' in new_params:
                        new_params['position_size'] = max(0.1, new_params['position_size'] * 0.8)
                elif market_phase == "neutral":
                    # 低波动环境下，降低回归阈值
                    if 'threshold' in new_params:
                        new_params['threshold'] = max(0.01, new_params['threshold'] * 0.8)
            
            # 通用参数调整
            if volatility > 2.0:
                # 高波动率环境
                if 'position_size' in new_params:
                    new_params['position_size'] = max(0.1, new_params['position_size'] * 0.6)
                if 'leverage' in new_params:
                    new_params['leverage'] = max(1, int(new_params['leverage'] * 0.5))
            elif volatility < 0.5:
                # 低波动率环境
                if 'position_size' in new_params:
                    new_params['position_size'] = min(1.0, new_params['position_size'] * 1.2)
                if 'leverage' in new_params:
                    new_params['leverage'] = min(10, new_params['leverage'] * 1.2)
        
        return new_params
    
    def _save_params_history(self, strategy_name, params):
        """保存策略参数历史
        
        Args:
            strategy_name (str): 策略名称
            params (dict): 策略参数
        """
        if strategy_name not in self.strategy_params_history:
            self.strategy_params_history[strategy_name] = []
        
        self.strategy_params_history[strategy_name].append({
            "params": params,
            "timestamp": time.time(),
            "market_environment": self.market_environment.copy()
        })
        
        # 保持历史记录不超过100条
        if len(self.strategy_params_history[strategy_name]) > 100:
            self.strategy_params_history[strategy_name] = self.strategy_params_history[strategy_name][-100:]
    
    def on_risk_rules_updated(self, data):
        """处理风险规则更新事件
        
        Args:
            data (dict): 风险规则更新数据
        """
        try:
            risk_level = data.get('risk_level')
            if risk_level:
                # 根据风险等级调整策略参数
                for strategy_name in self.active_strategies:
                    strategy = self.strategies.get(strategy_name)
                    if strategy:
                        params = strategy.get_params()
                        
                        # 基于风险等级调整参数
                        if risk_level == "high" or risk_level == "extreme":
                            # 高风险环境，降低风险敞口
                            if 'position_size' in params:
                                params['position_size'] = max(0.1, params['position_size'] * 0.5)
                            if 'leverage' in params:
                                params['leverage'] = max(1, int(params['leverage'] * 0.5))
                        elif risk_level == "low":
                            # 低风险环境，增加风险敞口
                            if 'position_size' in params:
                                params['position_size'] = min(1.0, params['position_size'] * 1.3)
                            if 'leverage' in params:
                                params['leverage'] = min(10, params['leverage'] * 1.3)
                        
                        # 更新策略参数
                        strategy.set_params(params)
                        
                        logger.info(f"根据风险等级 {risk_level} 调整策略 {strategy_name} 参数")
        except Exception as e:
            logger.error(f"处理风险规则更新失败: {e}")
    
    def apply_trading_plans(self, strategy_name, plans):
        """应用交易规划到策略
        
        Args:
            strategy_name (str): 策略名称
            plans (list): 交易规划列表
            
        Returns:
            bool: 是否成功应用
        """
        try:
            strategy = self.strategies.get(strategy_name)
            if not strategy:
                logger.error(f"策略不存在: {strategy_name}")
                return False
            
            # 处理交易规划
            for plan in plans:
                direction = plan.get("direction")
                time_horizon = plan.get("time_horizon")
                confidence = plan.get("confidence")
                notes = plan.get("notes", "")
                
                # 根据时间范围和信心程度调整策略参数
                if time_horizon == "短期":
                    # 短期交易，调整为更敏感的参数
                    strategy.params["grid_spacing"] = 0.005  # 减小网格间距
                    strategy.params["max_leverage"] = 10  # 增加杠杆
                elif time_horizon == "中期":
                    # 中期交易，使用默认参数
                    strategy.params["grid_spacing"] = 0.01
                    strategy.params["max_leverage"] = 5
                elif time_horizon == "长期":
                    # 长期交易，调整为更保守的参数
                    strategy.params["grid_spacing"] = 0.02  # 增大网格间距
                    strategy.params["max_leverage"] = 2  # 减小杠杆
                
                # 根据信心程度调整策略行为
                if confidence == "高":
                    # 高信心，增加交易频率和仓位
                    strategy.params["trade_frequency"] = "high"
                elif confidence == "中":
                    # 中等信心，使用默认设置
                    strategy.params["trade_frequency"] = "medium"
                elif confidence == "低":
                    # 低信心，减少交易频率和仓位
                    strategy.params["trade_frequency"] = "low"
                
                # 记录交易规划
                logger.info(f"应用交易规划到策略 {strategy_name}: 方向={direction}, 时间范围={time_horizon}, 信心={confidence}")
            
            # 更新策略状态
            if strategy.status == "idle":
                # 如果策略未激活，自动激活
                self.activate_strategy(strategy_name, strategy.params)
            
            return True
        except Exception as e:
            logger.error(f"应用交易规划失败: {e}")
            return False
