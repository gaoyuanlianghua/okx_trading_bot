from loguru import logger
from agents.base_agent import BaseAgent
import time

class DecisionCoordinationAgent(BaseAgent):
    """决策协调智能体，负责协调各个智能体之间的工作"""
    
    def __init__(self, agent_id, config=None):
        super().__init__(agent_id, config)
        self.system_state = {
            "is_running": False,
            "active_symbols": set(),
            "total_agents": 0,
            "running_agents": 0,
            "active_strategies": 0,
            "system_health": 1.0,  # 系统健康度 (0.0-1.0)
            "resource_utilization": {  # 资源利用率
                "cpu": 0.0,
                "memory": 0.0,
                "network": 0.0
            },
            "predicted_load": 0.0,  # 预测负载
        }
        self.agent_status_cache = {}  # 智能体状态缓存
        self.agent_capabilities = {}  # 智能体能力评估
        self.resource_allocation = {}  # 资源分配情况
        self.fault_recovery_history = []  # 故障恢复历史
        self.collaboration_rules = {}  # 协作规则
        self.decision_history = []  # 决策历史
        self.resource_usage_history = {}  # 资源使用历史
        self.resource_efficiency = {}  # 资源使用效率
        self.performance_metrics = {}  # 性能指标
        self.event_processing_times = {}  # 事件处理时间
        
        # 订阅事件
        self.subscribe('agent_status_changed', self.on_agent_status_changed)
        self.subscribe('market_data_updated', self.on_market_data_updated)
        self.subscribe('order_placed', self.on_order_placed)
        self.subscribe('order_updated', self.on_order_updated)
        self.subscribe('order_canceled', self.on_order_canceled)
        self.subscribe('risk_alert', self.on_risk_alert)
        self.subscribe('strategy_activated', self.on_strategy_activated)
        self.subscribe('strategy_deactivated', self.on_strategy_deactivated)
        self.subscribe('system_state_updated', self.on_system_state_updated)
        self.subscribe('risk_rules_updated', self.on_risk_rules_updated)
        self.subscribe('strategy_params_updated', self.on_strategy_params_updated)
        
        # 初始化协作规则
        self._init_collaboration_rules()
        
        logger.info(f"决策协调智能体初始化完成: {self.agent_id}")
    
    def start(self):
        """启动决策协调智能体"""
        super().start()
        
        # 更新系统状态
        self.system_state["is_running"] = True
        
        # 启动系统监控循环
        self.run_in_thread(self.system_monitor_loop)
        
        logger.info(f"决策协调智能体启动完成: {self.agent_id}")
    
    def stop(self):
        """停止决策协调智能体"""
        super().stop()
        
        # 更新系统状态
        self.system_state["is_running"] = False
        
        logger.info(f"决策协调智能体停止完成: {self.agent_id}")
    
    def system_monitor_loop(self):
        """系统监控循环"""
        while self.status == 'running':
            try:
                # 更新系统状态
                self.update_system_state()
                
                # 检查系统健康状况
                self.check_system_health()
                
                # 智能资源分配
                self.allocate_resources()
                
                # 系统故障自动恢复
                self.auto_recover_from_faults()
                
                # 等待下一次检查
                time.sleep(10)  # 每10秒检查一次系统状态
            except Exception as e:
                logger.error(f"系统监控循环失败: {e}")
                time.sleep(10)
    
    def update_system_state(self):
        """更新系统状态"""
        try:
            # 获取所有智能体
            all_agents = self.agent_registry.get_all_agents()
            running_agents = [agent for agent in all_agents if agent.status == 'running']
            
            # 更新系统状态
            self.system_state.update({
                "total_agents": len(all_agents),
                "running_agents": len(running_agents),
            })
            
            # 发布系统状态更新事件
            self.publish('system_state_updated', {
                "state": self.system_state,
                "timestamp": time.time()
            })
            
        except Exception as e:
            logger.error(f"更新系统状态失败: {e}")
    
    def check_system_health(self):
        """检查系统健康状况"""
        try:
            # 获取所有智能体
            all_agents = self.agent_registry.get_all_agents()
            
            # 检查智能体运行状态
            error_agents = []
            warning_agents = []
            healthy_agents = []
            
            for agent in all_agents:
                # 使用内部英文状态进行比较
                if agent.status == 'error':
                    error_agents.append(agent)
                    # 处理智能体错误
                    self.handle_agent_error(agent)
                elif agent.status == 'warning':
                    warning_agents.append(agent)
                elif agent.status == 'running':
                    healthy_agents.append(agent)
            
            # 计算系统健康度
            health_score = self._calculate_health_score(all_agents, error_agents, warning_agents)
            
            # 更新系统健康度
            self.system_state["system_health"] = health_score
            
            # 发布健康状态更新事件
            self.publish('system_health_updated', {
                "health_score": health_score,
                "error_agents": [agent.agent_id for agent in error_agents],
                "warning_agents": [agent.agent_id for agent in warning_agents],
                "timestamp": time.time()
            })
            
            logger.info(f"系统健康检查完成，健康度: {health_score:.2f}")
            
            # 更新性能指标
            self.update_performance_metric('health_check_count')
            
        except Exception as e:
            logger.error(f"检查系统健康状况失败: {e}")
    
    def _calculate_health_score(self, all_agents, error_agents, warning_agents):
        """计算系统健康度
        
        Args:
            all_agents (list): 所有智能体
            error_agents (list): 错误状态的智能体
            warning_agents (list): 警告状态的智能体
            
        Returns:
            float: 健康度得分 (0.0-1.0)
        """
        try:
            if not all_agents:
                return 0.0
            
            # 基础健康度：基于智能体状态
            healthy_ratio = len([a for a in all_agents if a.status == 'running']) / len(all_agents)
            
            # 资源利用率影响
            resource_utilization = self.system_state.get('resource_utilization', {})
            cpu_usage = resource_utilization.get('cpu', 0.0)
            memory_usage = resource_utilization.get('memory', 0.0)
            
            # 资源使用过高会降低健康度
            resource_penalty = 0.0
            if cpu_usage > 0.9:
                resource_penalty += 0.3
            elif cpu_usage > 0.7:
                resource_penalty += 0.1
            if memory_usage > 0.9:
                resource_penalty += 0.3
            elif memory_usage > 0.7:
                resource_penalty += 0.1
            
            # 系统负载影响
            system_load = self.system_state.get('predicted_load', 0.0)
            load_penalty = min(0.3, system_load * 0.3)
            
            # 故障恢复历史影响
            recent_failures = len([h for h in self.fault_recovery_history 
                                if time.time() - h.get('recovery_time', 0) < 300])  # 最近5分钟的故障
            failure_penalty = min(0.4, recent_failures * 0.1)
            
            # 计算最终健康度
            health_score = healthy_ratio - resource_penalty - load_penalty - failure_penalty
            
            # 确保健康度在0-1范围内
            return max(0.0, min(1.0, health_score))
            
        except Exception as e:
            logger.error(f"计算健康度失败: {e}")
            return 0.5  # 默认健康度
    
    def handle_agent_error(self, agent):
        """处理智能体错误
        
        Args:
            agent (BaseAgent): 出错的智能体
        """
        try:
            logger.error(f"处理智能体错误: {agent.agent_id}, 状态: {agent.status}")
            
            # 根据智能体类型和错误次数决定恢复策略
            recovery_strategy = self._determine_recovery_strategy(agent)
            
            if recovery_strategy == 'restart':
                # 简单重启策略
                self._simple_restart_agent(agent)
            elif recovery_strategy == 'delayed_restart':
                # 延迟重启策略
                self._delayed_restart_agent(agent)
            elif recovery_strategy == 'emergency_recovery':
                # 紧急恢复策略
                self._emergency_recovery_agent(agent)
                
        except Exception as e:
            logger.error(f"处理智能体错误失败: {e}")
    
    def _determine_recovery_strategy(self, agent):
        """确定恢复策略
        
        Args:
            agent (BaseAgent): 智能体
            
        Returns:
            str: 恢复策略类型
        """
        try:
            # 获取智能体的错误历史
            error_count = len([h for h in self.fault_recovery_history 
                            if h.get('agent_id') == agent.agent_id 
                            and time.time() - h.get('recovery_time', 0) < 3600])  # 1小时内的错误次数
            
            # 根据错误次数和智能体类型确定策略
            if error_count >= 3:
                # 多次错误，使用紧急恢复策略
                return 'emergency_recovery'
            elif error_count >= 2:
                # 两次错误，使用延迟重启策略
                return 'delayed_restart'
            else:
                # 首次错误，使用简单重启策略
                return 'restart'
                
        except Exception as e:
            logger.error(f"确定恢复策略失败: {e}")
            return 'restart'  # 默认使用简单重启策略
    
    def _simple_restart_agent(self, agent):
        """简单重启智能体"""
        try:
            logger.info(f"执行简单重启策略: {agent.agent_id}")
            
            # 停止智能体
            agent.stop()
            time.sleep(1)
            
            # 启动智能体
            agent.start()
            
            # 记录恢复历史
            self.fault_recovery_history.append({
                "agent_id": agent.agent_id,
                "recovery_time": time.time(),
                "strategy": "simple_restart",
                "status": "success"
            })
            
            logger.info(f"智能体重启成功: {agent.agent_id}")
            
        except Exception as e:
            logger.error(f"简单重启失败: {e}")
            self.fault_recovery_history.append({
                "agent_id": agent.agent_id,
                "recovery_time": time.time(),
                "strategy": "simple_restart",
                "status": "failed",
                "error": str(e)
            })
    
    def _delayed_restart_agent(self, agent):
        """延迟重启智能体"""
        try:
            logger.info(f"执行延迟重启策略: {agent.agent_id}")
            
            # 停止智能体
            agent.stop()
            
            # 延迟一段时间后重启
            delay_time = 5  # 延迟5秒
            logger.info(f"延迟 {delay_time} 秒后重启智能体: {agent.agent_id}")
            time.sleep(delay_time)
            
            # 启动智能体
            agent.start()
            
            # 记录恢复历史
            self.fault_recovery_history.append({
                "agent_id": agent.agent_id,
                "recovery_time": time.time(),
                "strategy": "delayed_restart",
                "status": "success"
            })
            
            logger.info(f"智能体延迟重启成功: {agent.agent_id}")
            
        except Exception as e:
            logger.error(f"延迟重启失败: {e}")
            self.fault_recovery_history.append({
                "agent_id": agent.agent_id,
                "recovery_time": time.time(),
                "strategy": "delayed_restart",
                "status": "failed",
                "error": str(e)
            })
    
    def _emergency_recovery_agent(self, agent):
        """紧急恢复智能体"""
        try:
            logger.warning(f"执行紧急恢复策略: {agent.agent_id}")
            
            # 停止智能体
            agent.stop()
            
            # 清理智能体状态
            if hasattr(agent, 'clear_state'):
                agent.clear_state()
            
            # 延迟更长时间后重启
            delay_time = 10  # 延迟10秒
            logger.info(f"延迟 {delay_time} 秒后紧急重启智能体: {agent.agent_id}")
            time.sleep(delay_time)
            
            # 启动智能体
            agent.start()
            
            # 记录恢复历史
            self.fault_recovery_history.append({
                "agent_id": agent.agent_id,
                "recovery_time": time.time(),
                "strategy": "emergency_recovery",
                "status": "success"
            })
            
            logger.info(f"智能体紧急恢复成功: {agent.agent_id}")
            
        except Exception as e:
            logger.error(f"紧急恢复失败: {e}")
            self.fault_recovery_history.append({
                "agent_id": agent.agent_id,
                "recovery_time": time.time(),
                "strategy": "emergency_recovery",
                "status": "failed",
                "error": str(e)
            })
    
    def on_agent_status_changed(self, data):
        """处理智能体状态变化事件
        
        Args:
            data (dict): 智能体状态数据
        """
        try:
            agent_id = data.get('agent_id')
            status = data.get('status')
            
            # 获取中文智能体名称
            from agents.base_agent import BaseAgent
            agent_name = BaseAgent.AGENT_ID_MAP.get(agent_id, agent_id)
            
            # 更新智能体状态缓存
            self.agent_status_cache[agent_id] = status
            
            logger.info(f"智能体状态变化: {agent_name} -> {status}")
            
            # 更新系统状态
            self.update_system_state()
            
        except Exception as e:
            logger.error(f"处理智能体状态变化事件失败: {e}")
    
    def on_market_data_updated(self, data):
        """处理市场数据更新事件
        
        Args:
            data (dict): 市场数据
        """
        try:
            symbol = data.get('symbol')
            if symbol:
                # 添加到活跃交易对
                self.system_state["active_symbols"].add(symbol)
                
            logger.debug(f"市场数据更新: {symbol}")
            
        except Exception as e:
            logger.error(f"处理市场数据更新事件失败: {e}")
    
    def on_order_placed(self, data):
        """处理订单已下单事件
        
        Args:
            data (dict): 订单数据
        """
        try:
            order = data.get('order')
            if order:
                symbol = order.get('instId')
                logger.info(f"订单已下单: {symbol}, 订单ID: {order.get('ordId')}")
            
        except Exception as e:
            logger.error(f"处理订单已下单事件失败: {e}")
    
    def on_order_updated(self, data):
        """处理订单更新事件
        
        Args:
            data (dict): 订单数据
        """
        try:
            order = data.get('order')
            if order:
                symbol = order.get('instId')
                state = order.get('state')
                logger.debug(f"订单更新: {symbol}, 订单ID: {order.get('ordId')}, 状态: {state}")
            
        except Exception as e:
            logger.error(f"处理订单更新事件失败: {e}")
    
    def on_order_canceled(self, data):
        """处理订单取消事件
        
        Args:
            data (dict): 订单数据
        """
        try:
            order_id = data.get('order_id')
            logger.info(f"订单已取消: {order_id}")
            
        except Exception as e:
            logger.error(f"处理订单取消事件失败: {e}")
    
    def on_risk_alert(self, data):
        """处理风险告警事件
        
        Args:
            data (dict): 风险告警数据
        """
        try:
            alert_type = data.get('type')
            logger.warning(f"风险告警: {alert_type}, 数据: {data}")
            
            # 根据风险类型采取相应措施
            self.handle_risk_alert(data)
            
        except Exception as e:
            logger.error(f"处理风险告警事件失败: {e}")
    
    def on_strategy_activated(self, data):
        """处理策略激活事件
        
        Args:
            data (dict): 策略激活数据
        """
        try:
            strategy_name = data.get('strategy_name')
            logger.info(f"策略已激活: {strategy_name}")
            
            # 更新系统状态
            self.system_state["active_strategies"] += 1
            
        except Exception as e:
            logger.error(f"处理策略激活事件失败: {e}")
    
    def on_strategy_deactivated(self, data):
        """处理策略停用事件
        
        Args:
            data (dict): 策略停用数据
        """
        try:
            strategy_name = data.get('strategy_name')
            logger.info(f"策略已停用: {strategy_name}")
            
            # 更新系统状态
            self.system_state["active_strategies"] = max(0, self.system_state["active_strategies"] - 1)
            
        except Exception as e:
            logger.error(f"处理策略停用事件失败: {e}")
    
    def handle_risk_alert(self, alert_data):
        """处理风险告警
        
        Args:
            alert_data (dict): 风险告警数据
        """
        try:
            alert_type = alert_data.get('type')
            
            # 根据不同的风险类型采取不同的措施
            if alert_type == "max_position_exceeded":
                # 持仓价值超过限制，发送消息给订单智能体，暂停下单
                self.send_message("order_agent", {
                    "type": "pause_trading",
                    "reason": "持仓价值超过限制",
                    "timestamp": time.time()
                })
            
            elif alert_type == "max_orders_exceeded":
                # 订单数超过限制，发送消息给订单智能体，暂停下单
                self.send_message("order_agent", {
                    "type": "pause_trading",
                    "reason": "订单数超过限制",
                    "timestamp": time.time()
                })
            
            elif alert_type == "max_order_size_exceeded":
                # 单笔订单大小超过限制，记录日志，不暂停交易
                logger.warning(f"单笔订单大小超过限制: {alert_data}")
            
            elif alert_type == "max_drawdown_exceeded":
                # 最大回撤超过限制，发送消息给策略执行智能体，停用所有策略
                self.send_message("strategy_execution_agent", {
                    "type": "deactivate_all_strategies",
                    "reason": "最大回撤超过限制",
                    "timestamp": time.time()
                })
            
        except Exception as e:
            logger.error(f"处理风险告警失败: {e}")
    
    def add_symbol_subscription(self, symbol):
        """添加交易对订阅
        
        Args:
            symbol (str): 交易对
        """
        try:
            # 发送消息给市场数据智能体，订阅该交易对
            self.send_message("market_data_agent", {
                "type": "subscribe_symbol",
                "symbol": symbol,
                "timestamp": time.time()
            })
            
            # 添加到活跃交易对
            self.system_state["active_symbols"].add(symbol)
            
            logger.info(f"添加交易对订阅: {symbol}")
            
        except Exception as e:
            logger.error(f"添加交易对订阅失败: {e}")
    
    def remove_symbol_subscription(self, symbol):
        """移除交易对订阅
        
        Args:
            symbol (str): 交易对
        """
        try:
            # 发送消息给市场数据智能体，取消订阅该交易对
            self.send_message("market_data_agent", {
                "type": "unsubscribe_symbol",
                "symbol": symbol,
                "timestamp": time.time()
            })
            
            # 从活跃交易对中移除
            if symbol in self.system_state["active_symbols"]:
                self.system_state["active_symbols"].remove(symbol)
            
            logger.info(f"移除交易对订阅: {symbol}")
            
        except Exception as e:
            logger.error(f"移除交易对订阅失败: {e}")
    
    def activate_strategy(self, strategy_name):
        """激活策略
        
        Args:
            strategy_name (str): 策略名称
        """
        try:
            # 发送消息给策略执行智能体，激活该策略
            self.send_message("strategy_execution_agent", {
                "type": "activate_strategy",
                "strategy_name": strategy_name,
                "timestamp": time.time()
            })
            
            logger.info(f"激活策略: {strategy_name}")
            
        except Exception as e:
            logger.error(f"激活策略失败: {e}")
    
    def deactivate_strategy(self, strategy_name):
        """停用策略
        
        Args:
            strategy_name (str): 策略名称
        """
        try:
            # 发送消息给策略执行智能体，停用该策略
            self.send_message("strategy_execution_agent", {
                "type": "deactivate_strategy",
                "strategy_name": strategy_name,
                "timestamp": time.time()
            })
            
            logger.info(f"停用策略: {strategy_name}")
            
        except Exception as e:
            logger.error(f"停用策略失败: {e}")
    
    def get_system_state(self):
        """获取系统状态
        
        Returns:
            dict: 系统状态
        """
        return self.system_state.copy()
    
    def get_agent_status(self, agent_id):
        """获取智能体状态
        
        Args:
            agent_id (str): 智能体ID
            
        Returns:
            dict: 智能体状态
        """
        return self.agent_status_cache.get(agent_id)
    
    def process_message(self, message):
        """处理收到的消息
        
        Args:
            message (dict): 消息内容
        """
        start_time = time.time()
        try:
            super().process_message(message)
        finally:
            processing_time = time.time() - start_time
            self.update_performance_metric('message_processing_count')
            self.update_performance_metric('message_processing_time', processing_time)
        
        if message.get('type') == 'get_system_state':
            # 获取系统状态请求
            if message.get('sender'):
                self.send_message(message.get('sender'), {
                    'type': 'system_state_response',
                    'state': self.get_system_state()
                })
        
        elif message.get('type') == 'add_symbol_subscription':
            # 添加交易对订阅请求
            symbol = message.get('symbol')
            self.add_symbol_subscription(symbol)
            
        elif message.get('type') == 'remove_symbol_subscription':
            # 移除交易对订阅请求
            symbol = message.get('symbol')
            self.remove_symbol_subscription(symbol)
        
        elif message.get('type') == 'activate_strategy':
            # 激活策略请求
            strategy_name = message.get('strategy_name')
            self.activate_strategy(strategy_name)
        
        elif message.get('type') == 'deactivate_strategy':
            # 停用策略请求
            strategy_name = message.get('strategy_name')
            self.deactivate_strategy(strategy_name)
        
        elif message.get('type') == 'get_agent_status':
            # 获取智能体状态请求
            agent_id = message.get('agent_id')
            if message.get('sender'):
                self.send_message(message.get('sender'), {
                    'type': 'agent_status_response',
                    'agent_id': agent_id,
                    'status': self.get_agent_status(agent_id)
                })
        
        elif message.get('type') == 'resume_trading':
            # 恢复交易请求
            self.send_message("order_agent", {
                "type": "resume_trading",
                "reason": message.get('reason', '用户请求恢复交易'),
                "timestamp": time.time()
            })
        
        elif message.get('type') == 'pause_trading':
            # 暂停交易请求
            self.send_message("order_agent", {
                "type": "pause_trading",
                "reason": message.get('reason', '用户请求暂停交易'),
                "timestamp": time.time()
            })
    
    def on_system_state_updated(self, data):
        """处理系统状态更新事件
        
        Args:
            data (dict): 系统状态数据
        """
        try:
            state = data.get('state')
            if state:
                # 更新本地系统状态
                self.system_state.update(state)
                logger.debug("系统状态更新")
            
        except Exception as e:
            logger.error(f"处理系统状态更新事件失败: {e}")
    
    def on_risk_rules_updated(self, data):
        """处理风险规则更新事件
        
        Args:
            data (dict): 风险规则更新数据
        """
        try:
            rules = data.get('rules')
            if rules:
                logger.info("风险规则更新")
            
        except Exception as e:
            logger.error(f"处理风险规则更新事件失败: {e}")
    
    def on_strategy_params_updated(self, data):
        """处理策略参数更新事件
        
        Args:
            data (dict): 策略参数更新数据
        """
        try:
            strategy_name = data.get('strategy_name')
            new_params = data.get('params')
            logger.info(f"策略参数更新: {strategy_name}")
            
        except Exception as e:
            logger.error(f"处理策略参数更新事件失败: {e}")
    
    def _init_collaboration_rules(self):
        """初始化协作规则"""
        try:
            # 初始化协作规则
            self.collaboration_rules = {
                "market_data_priority": 10,  # 市场数据智能体优先级
                "order_priority": 8,  # 订单智能体优先级
                "risk_management_priority": 12,  # 风险控制智能体优先级
                "strategy_execution_priority": 9,  # 策略执行智能体优先级
                "decision_coordination_priority": 15  # 决策协调智能体优先级
            }
            
            logger.info("协作规则初始化完成")
            
            # 初始化性能指标
            self._init_performance_metrics()
            
        except Exception as e:
            logger.error(f"初始化协作规则失败: {e}")
    
    def _init_performance_metrics(self):
        """初始化性能指标"""
        try:
            self.performance_metrics = {
                'event_processing_count': 0,
                'event_processing_time': 0.0,
                'message_processing_count': 0,
                'message_processing_time': 0.0,
                'resource_allocation_count': 0,
                'health_check_count': 0,
                'fault_recovery_count': 0,
                'start_time': time.time()
            }
            
            logger.info("性能指标初始化完成")
            
        except Exception as e:
            logger.error(f"初始化性能指标失败: {e}")
    
    def allocate_resources(self):
        """智能资源分配"""
        try:
            # 获取当前系统负载
            current_load = self._calculate_system_load()
            
            # 更新资源使用历史
            self._update_resource_usage_history()
            
            # 计算资源使用效率
            self._calculate_resource_efficiency()
            
            # 根据负载和效率动态分配资源
            total_allocation = 0.0
            temp_allocation = {}
            
            # 第一阶段：基于优先级和效率分配基础资源
            for agent_id, priority in self.collaboration_rules.items():
                # 获取资源使用效率（默认为1.0）
                efficiency = self.resource_efficiency.get(agent_id, 1.0)
                
                # 计算基础分配比例（优先级 * 效率）
                base_ratio = priority * efficiency
                temp_allocation[agent_id] = base_ratio
                total_allocation += base_ratio
            
            # 第二阶段：根据系统负载动态调整分配
            final_allocation = {}
            if total_allocation > 0:
                for agent_id, base_ratio in temp_allocation.items():
                    # 基础分配比例
                    base_allocation = base_ratio / total_allocation
                    
                    # 根据系统负载调整
                    if current_load > 0.8:
                        # 高负载情况：优先保障关键智能体
                        priority = self.collaboration_rules[agent_id]
                        if priority >= 10:
                            # 高优先级智能体获得更多资源
                            allocation = min(0.4, base_allocation * 1.5)
                        else:
                            # 低优先级智能体资源受限
                            allocation = max(0.05, base_allocation * 0.5)
                    elif current_load < 0.3:
                        # 低负载情况：更均衡分配
                        allocation = base_allocation * 0.8 + 0.2 / len(temp_allocation)
                    else:
                        # 正常负载情况：按比例分配
                        allocation = base_allocation
                    
                    final_allocation[agent_id] = allocation
            
            # 更新资源分配
            self.resource_allocation = final_allocation
            
            # 发布资源分配更新事件
            self.publish('resource_allocation_updated', {
                "allocation": self.resource_allocation,
                "timestamp": time.time(),
                "system_load": current_load
            })
            
            # 更新性能指标
            self.update_performance_metric('resource_allocation_count')
            
            logger.debug(f"资源分配更新完成: {self.resource_allocation}")
            
        except Exception as e:
            logger.error(f"智能资源分配失败: {e}")
    
    def _update_resource_usage_history(self):
        """更新资源使用历史"""
        try:
            current_time = time.time()
            
            for agent_id in self.collaboration_rules:
                if agent_id not in self.resource_usage_history:
                    self.resource_usage_history[agent_id] = []
                
                # 获取智能体状态
                agent = self.agent_registry.get_agent(agent_id)
                usage_data = {
                    'timestamp': current_time,
                    'status': agent.status if agent else 'unknown',
                    'allocated_resource': self.resource_allocation.get(agent_id, 0.0),
                    'system_load': self.system_state.get('predicted_load', 0.0)
                }
                
                self.resource_usage_history[agent_id].append(usage_data)
                
                # 限制历史记录数量
                if len(self.resource_usage_history[agent_id]) > 100:
                    self.resource_usage_history[agent_id].pop(0)
                    
        except Exception as e:
            logger.error(f"更新资源使用历史失败: {e}")
    
    def _calculate_resource_efficiency(self):
        """计算资源使用效率"""
        try:
            for agent_id, history in self.resource_usage_history.items():
                if len(history) < 5:
                    # 历史数据不足，使用默认效率
                    self.resource_efficiency[agent_id] = 1.0
                    continue
                
                # 计算最近一段时间的资源使用效率
                recent_history = history[-5:]
                total_allocated = sum(item['allocated_resource'] for item in recent_history)
                active_time = sum(1 for item in recent_history if item['status'] == 'running')
                
                if total_allocated > 0:
                    # 效率 = 活跃时间 / 资源分配总量
                    efficiency = active_time / (total_allocated * len(recent_history))
                    self.resource_efficiency[agent_id] = min(2.0, max(0.5, efficiency))
                else:
                    self.resource_efficiency[agent_id] = 1.0
                    
        except Exception as e:
            logger.error(f"计算资源使用效率失败: {e}")
    
    def auto_recover_from_faults(self):
        """系统故障自动恢复"""
        try:
            # 获取系统健康度
            health_score = self.system_state.get("system_health", 1.0)
            
            # 根据健康度选择恢复策略
            if health_score < 0.3:
                # 严重故障，执行全面紧急恢复
                self._execute_comprehensive_recovery()
            elif health_score < 0.6:
                # 中度故障，执行选择性恢复
                self._execute_selective_recovery()
            else:
                # 轻度故障，执行常规恢复
                self._execute_routine_recovery()
            
        except Exception as e:
            logger.error(f"系统故障自动恢复失败: {e}")
    
    def _execute_comprehensive_recovery(self):
        """执行全面紧急恢复"""
        try:
            logger.critical("执行全面紧急恢复")
            
            # 1. 暂停所有交易活动
            self.send_message("order_agent", {
                "type": "pause_trading",
                "reason": "系统严重故障，执行全面恢复",
                "timestamp": time.time()
            })
            
            # 2. 停用所有策略
            self.send_message("strategy_execution_agent", {
                "type": "deactivate_all_strategies",
                "reason": "系统严重故障，执行全面恢复",
                "timestamp": time.time()
            })
            
            # 3. 重启所有异常智能体
            all_agents = self.agent_registry.get_all_agents()
            error_agents = [agent for agent in all_agents if agent.status == 'error']
            
            for agent in error_agents:
                self._emergency_recovery_agent(agent)
                
            # 4. 清理系统状态
            self.system_state["active_symbols"] = set()
            self.system_state["active_strategies"] = 0
            
            # 5. 重置系统健康度
            self.system_state["system_health"] = 0.7  # 恢复到中等健康度
            
            logger.info("全面紧急恢复执行完成")
            
        except Exception as e:
            logger.error(f"执行全面紧急恢复失败: {e}")
    
    def _execute_selective_recovery(self):
        """执行选择性恢复"""
        try:
            logger.warning("执行选择性恢复")
            
            # 获取所有智能体
            all_agents = self.agent_registry.get_all_agents()
            error_agents = [agent for agent in all_agents if agent.status == 'error']
            
            # 按优先级恢复智能体
            priority_order = ['risk_management_agent', 'market_data_agent', 'order_agent', 'strategy_execution_agent']
            
            for priority_agent_id in priority_order:
                for agent in error_agents:
                    if agent.agent_id == priority_agent_id:
                        self._delayed_restart_agent(agent)
                        break
            
            # 对于其他错误智能体，使用简单重启
            for agent in error_agents:
                if agent.agent_id not in priority_order:
                    self._simple_restart_agent(agent)
                    
            logger.info("选择性恢复执行完成")
            
        except Exception as e:
            logger.error(f"执行选择性恢复失败: {e}")
    
    def _execute_routine_recovery(self):
        """执行常规恢复"""
        try:
            logger.info("执行常规恢复")
            
            # 获取所有智能体
            all_agents = self.agent_registry.get_all_agents()
            
            # 只恢复错误状态的智能体
            for agent in all_agents:
                if agent.status == 'error':
                    self.handle_agent_error(agent)
                    
            logger.info("常规恢复执行完成")
            
        except Exception as e:
            logger.error(f"执行常规恢复失败: {e}")
    
    def _calculate_system_load(self):
        """计算系统负载
        
        Returns:
            float: 系统负载 (0.0-1.0)
        """
        try:
            # 基于活跃交易对数量、运行智能体数量和策略数量计算负载
            active_symbols_count = len(self.system_state["active_symbols"])
            running_agents_count = self.system_state["running_agents"]
            active_strategies_count = self.system_state["active_strategies"]
            
            # 计算负载值 (0.0-1.0)
            load = min(1.0, (active_symbols_count * 0.1 + running_agents_count * 0.3 + active_strategies_count * 0.6) / 10)
            
            # 更新系统状态
            self.system_state["predicted_load"] = load
            
            return load
            
        except Exception as e:
            logger.error(f"计算系统负载失败: {e}")
            return 0.0
    

    
    def _execute_emergency_recovery(self):
        """执行紧急恢复措施"""
        try:
            logger.warning("执行紧急恢复措施")
            
            # 1. 暂停所有交易
            self.send_message("order_agent", {
                "type": "pause_trading",
                "reason": "系统健康度低，执行紧急恢复",
                "timestamp": time.time()
            })
            
            # 2. 停用所有策略
            self.send_message("strategy_execution_agent", {
                "type": "deactivate_all_strategies",
                "reason": "系统健康度低，执行紧急恢复",
                "timestamp": time.time()
            })
            
            # 3. 清理系统状态
            self.system_state["active_symbols"] = set()
            
            # 4. 重启所有智能体
            all_agents = self.agent_registry.get_all_agents()
            for agent in all_agents:
                if agent.status != 'running':
                    self._recover_agent(agent)
            
            # 5. 重置系统健康度
            self.system_state["system_health"] = 1.0
            
            logger.info("紧急恢复措施执行完成")
            
        except Exception as e:
            logger.error(f"执行紧急恢复措施失败: {e}")
    
    def send_message(self, agent_id, message):
        """发送消息给其他智能体
        
        Args:
            agent_id (str): 智能体ID
            message (dict): 消息内容
        """
        try:
            # 获取目标智能体
            agent = self.agent_registry.get_agent(agent_id)
            if agent:
                # 发送消息
                agent.process_message(message)
                logger.debug(f"发送消息给智能体: {agent_id}, 消息类型: {message.get('type')}")
            else:
                logger.error(f"智能体不存在: {agent_id}")
                
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
    
    def update_performance_metric(self, metric_name, value=1):
        """更新性能指标
        
        Args:
            metric_name (str): 指标名称
            value (float): 指标值
        """
        try:
            if metric_name in self.performance_metrics:
                if isinstance(self.performance_metrics[metric_name], int):
                    self.performance_metrics[metric_name] += value
                elif isinstance(self.performance_metrics[metric_name], float):
                    self.performance_metrics[metric_name] += value
                    
        except Exception as e:
            logger.error(f"更新性能指标失败: {e}")
    
    def record_event_processing_time(self, event_name, processing_time):
        """记录事件处理时间
        
        Args:
            event_name (str): 事件名称
            processing_time (float): 处理时间（秒）
        """
        try:
            if event_name not in self.event_processing_times:
                self.event_processing_times[event_name] = []
            
            self.event_processing_times[event_name].append(processing_time)
            
            # 限制历史记录数量
            if len(self.event_processing_times[event_name]) > 1000:
                self.event_processing_times[event_name].pop(0)
                
        except Exception as e:
            logger.error(f"记录事件处理时间失败: {e}")
    
    def generate_performance_report(self):
        """生成性能报告
        
        Returns:
            dict: 性能报告
        """
        try:
            uptime = time.time() - self.performance_metrics.get('start_time', time.time())
            
            # 计算平均处理时间
            avg_event_time = 0.0
            if self.performance_metrics.get('event_processing_count', 0) > 0:
                avg_event_time = self.performance_metrics.get('event_processing_time', 0.0) / self.performance_metrics.get('event_processing_count', 1)
            
            avg_message_time = 0.0
            if self.performance_metrics.get('message_processing_count', 0) > 0:
                avg_message_time = self.performance_metrics.get('message_processing_time', 0.0) / self.performance_metrics.get('message_processing_count', 1)
            
            # 计算事件处理时间统计
            event_stats = {}
            for event_name, times in self.event_processing_times.items():
                if times:
                    event_stats[event_name] = {
                        'count': len(times),
                        'avg_time': sum(times) / len(times),
                        'min_time': min(times),
                        'max_time': max(times)
                    }
            
            report = {
                'timestamp': time.time(),
                'uptime': uptime,
                'metrics': self.performance_metrics.copy(),
                'avg_event_processing_time': avg_event_time,
                'avg_message_processing_time': avg_message_time,
                'event_stats': event_stats,
                'system_state': self.system_state.copy()
            }
            
            return report
            
        except Exception as e:
            logger.error(f"生成性能报告失败: {e}")
            return {}
    
    def log_performance_report(self):
        """记录性能报告到日志"""
        try:
            report = self.generate_performance_report()
            
            logger.info("=== 性能报告 ===")
            logger.info(f"运行时间: {report.get('uptime', 0):.2f}秒")
            logger.info(f"事件处理总数: {report.get('metrics', {}).get('event_processing_count', 0)}")
            logger.info(f"消息处理总数: {report.get('metrics', {}).get('message_processing_count', 0)}")
            logger.info(f"平均事件处理时间: {report.get('avg_event_processing_time', 0):.4f}秒")
            logger.info(f"平均消息处理时间: {report.get('avg_message_processing_time', 0):.4f}秒")
            logger.info(f"资源分配次数: {report.get('metrics', {}).get('resource_allocation_count', 0)}")
            logger.info(f"健康检查次数: {report.get('metrics', {}).get('health_check_count', 0)}")
            logger.info(f"故障恢复次数: {report.get('metrics', {}).get('fault_recovery_count', 0)}")
            
            # 记录事件处理统计
            event_stats = report.get('event_stats', {})
            if event_stats:
                logger.info("事件处理统计:")
                for event_name, stats in event_stats.items():
                    logger.info(f"  {event_name}: 计数={stats['count']}, "
                              f"平均={stats['avg_time']:.4f}s, "
                              f"最小={stats['min_time']:.4f}s, "
                              f"最大={stats['max_time']:.4f}s")
                              
        except Exception as e:
            logger.error(f"记录性能报告失败: {e}")
