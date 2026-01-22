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
        }
        self.agent_status_cache = {}  # 智能体状态缓存
        
        # 订阅事件
        self.subscribe('agent_status_changed', self.on_agent_status_changed)
        self.subscribe('market_data_updated', self.on_market_data_updated)
        self.subscribe('order_placed', self.on_order_placed)
        self.subscribe('order_updated', self.on_order_updated)
        self.subscribe('order_canceled', self.on_order_canceled)
        self.subscribe('risk_alert', self.on_risk_alert)
        self.subscribe('strategy_activated', self.on_strategy_activated)
        self.subscribe('strategy_deactivated', self.on_strategy_deactivated)
        
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
            # 检查智能体运行状态
            all_agents = self.agent_registry.get_all_agents()
            for agent in all_agents:
                # 使用内部英文状态进行比较
                if agent.status == 'error':
                    # 处理智能体错误
                    self.handle_agent_error(agent)
            
            # 检查风险状态
            # 这里可以添加更复杂的风险评估逻辑
            
        except Exception as e:
            logger.error(f"检查系统健康状况失败: {e}")
    
    def handle_agent_error(self, agent):
        """处理智能体错误
        
        Args:
            agent (BaseAgent): 出错的智能体
        """
        try:
            logger.error(f"处理智能体错误: {agent.agent_id}, 状态: {agent.status}")
            
            # 尝试重启智能体
            agent.stop()
            time.sleep(2)
            agent.start()
            
            logger.info(f"尝试重启智能体: {agent.agent_id}")
            
        except Exception as e:
            logger.error(f"重启智能体失败: {e}")
    
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
        super().process_message(message)
        
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
