from loguru import logger
from agents.base_agent import BaseAgent
from services.risk_management.risk_manager import RiskManager
import time

class RiskManagementAgent(BaseAgent):
    """风险控制智能体，负责监控和控制交易风险"""
    
    def __init__(self, agent_id, config=None):
        super().__init__(agent_id, config)
        self.risk_manager = None
        self.base_risk_rules = {
            # 基础风险规则
            "max_position_size": config.get("max_position_size", 1000),  # 最大持仓价值
            "max_order_size": config.get("max_order_size", 100),  # 最大单笔订单价值
            "max_leverage": config.get("max_leverage", 10),  # 最大杠杆倍数
            "max_drawdown": config.get("max_drawdown", 0.1),  # 最大回撤比例
            "max_orders_per_symbol": config.get("max_orders_per_symbol", 5),  # 每个交易对最大订单数
            "max_total_orders": config.get("max_total_orders", 20),  # 总最大订单数
        }
        self.risk_rules = self.base_risk_rules.copy()  # 当前风险规则
        self.current_risk_state = {
            "total_position_value": 0,
            "total_orders": 0,
            "current_drawdown": 0,
            "active_symbols": set(),
            "market_volatility": 0.0,  # 市场波动率
            "risk_level": "normal",  # 风险等级: low, normal, high, extreme
            "adjustment_factor": 1.0,  # 调整因子
        }
        self.volatility_history = []  # 波动率历史
        self.volatility_window = 20  # 波动率计算窗口
        self.risk_adjustment_interval = 60  # 风险调整间隔（秒）
        self.last_adjustment_time = 0
        
        # 订阅事件
        self.subscribe('order_placed', self.on_order_placed)
        self.subscribe('order_updated', self.on_order_updated)
        self.subscribe('order_canceled', self.on_order_canceled)
        self.subscribe('all_orders_canceled', self.on_all_orders_canceled)
        self.subscribe('trading_signal', self.on_trading_signal)
        self.subscribe('market_data_updated', self.on_market_data_updated)
        
        logger.info(f"风险控制智能体初始化完成: {self.agent_id}")
    
    def start(self):
        """启动风险控制智能体"""
        super().start()
        
        # 初始化风险管理器
        from okx_api_client import OKXAPIClient
        api_client = OKXAPIClient(
            api_key=self.config.get('api_key'),
            api_secret=self.config.get('api_secret'),
            passphrase=self.config.get('passphrase'),
            is_test=self.config.get('is_test', False)
        )
        self.risk_manager = RiskManager(api_client)
        
        # 启动风险监控线程
        self.run_in_thread(self.risk_monitor_loop)
        
        logger.info(f"风险控制智能体启动完成: {self.agent_id}")
    
    def stop(self):
        """停止风险控制智能体"""
        super().stop()
        logger.info(f"风险控制智能体停止完成: {self.agent_id}")
    
    def risk_monitor_loop(self):
        """风险监控循环"""
        while self.status == 'running':
            try:
                # 更新风险状态
                self.update_risk_state()
                
                # 检查风险规则
                self.check_risk_rules()
                
                # 动态调整风险阈值
                self.adjust_risk_thresholds()
                
                # 等待下一次检查
                time.sleep(5)  # 每5秒检查一次风险
            except Exception as e:
                logger.error(f"风险监控失败: {e}")
                time.sleep(5)
    
    def update_risk_state(self):
        """更新风险状态"""
        try:
            # 获取当前持仓
            positions = self.risk_manager.get_positions()
            total_position_value = 0
            active_symbols = set()
            
            for position in positions:
                # 计算持仓价值
                notional_value = float(position.get('notionalUsd', 0))
                total_position_value += notional_value
                active_symbols.add(position.get('instId'))
            
            # 获取当前订单数
            orders = self.risk_manager.get_pending_orders()
            total_orders = len(orders)
            
            # 更新风险状态
            self.current_risk_state.update({
                "total_position_value": total_position_value,
                "total_orders": total_orders,
                "active_symbols": active_symbols,
            })
            
            # 发布风险状态更新事件
            self.publish('risk_state_updated', {
                "state": self.current_risk_state,
                "timestamp": time.time()
            })
            
        except Exception as e:
            logger.error(f"更新风险状态失败: {e}")
    
    def check_risk_rules(self):
        """检查风险规则"""
        try:
            # 检查最大持仓价值
            if self.current_risk_state["total_position_value"] > self.risk_rules["max_position_size"]:
                self.publish('risk_alert', {
                    "type": "max_position_exceeded",
                    "current_value": self.current_risk_state["total_position_value"],
                    "max_value": self.risk_rules["max_position_size"],
                    "timestamp": time.time()
                })
            
            # 检查最大订单数
            if self.current_risk_state["total_orders"] > self.risk_rules["max_total_orders"]:
                self.publish('risk_alert', {
                    "type": "max_orders_exceeded",
                    "current_count": self.current_risk_state["total_orders"],
                    "max_count": self.risk_rules["max_total_orders"],
                    "timestamp": time.time()
                })
            
        except Exception as e:
            logger.error(f"检查风险规则失败: {e}")
    
    def on_order_placed(self, data):
        """处理订单已下单事件
        
        Args:
            data (dict): 订单数据
        """
        logger.info(f"收到订单已下单事件: {data}")
        
        # 更新风险状态
        self.update_risk_state()
        
        # 检查订单是否符合风险规则
        order = data.get('order')
        if order:
            # 检查单笔订单大小
            order_size = float(order.get('notionalUsd', 0))
            if order_size > self.risk_rules["max_order_size"]:
                self.publish('risk_alert', {
                    "type": "max_order_size_exceeded",
                    "order_id": order.get('ordId'),
                    "order_size": order_size,
                    "max_size": self.risk_rules["max_order_size"],
                    "timestamp": time.time()
                })
    
    def on_order_updated(self, data):
        """处理订单更新事件
        
        Args:
            data (dict): 订单数据
        """
        logger.info(f"收到订单更新事件: {data}")
        # 更新风险状态
        self.update_risk_state()
    
    def on_order_canceled(self, data):
        """处理订单取消事件
        
        Args:
            data (dict): 订单数据
        """
        logger.info(f"收到订单取消事件: {data}")
        # 更新风险状态
        self.update_risk_state()
    
    def on_all_orders_canceled(self, data):
        """处理所有订单取消事件
        
        Args:
            data (dict): 订单数据
        """
        logger.info(f"收到所有订单取消事件: {data}")
        # 更新风险状态
        self.update_risk_state()
    
    def on_trading_signal(self, data):
        """处理交易信号，进行风险检查
        
        Args:
            data (dict): 交易信号数据
        """
        logger.info(f"收到交易信号，进行风险检查: {data}")
        
        # 检查信号是否符合风险规则
        can_trade = self.check_signal_risk(data)
        
        if can_trade:
            # 发布风险检查通过事件
            self.publish('risk_check_passed', {
                "signal": data,
                "timestamp": time.time()
            })
        else:
            # 发布风险检查失败事件
            self.publish('risk_check_failed', {
                "signal": data,
                "reason": "风险检查失败",
                "timestamp": time.time()
            })
    
    def check_signal_risk(self, signal):
        """检查交易信号的风险
        
        Args:
            signal (dict): 交易信号
            
        Returns:
            bool: 是否允许交易
        """
        try:
            # 检查持仓价值
            if self.current_risk_state["total_position_value"] > self.risk_rules["max_position_size"]:
                logger.warning(f"持仓价值超过限制: {self.current_risk_state['total_position_value']} > {self.risk_rules['max_position_size']}")
                return False
            
            # 检查订单数
            if self.current_risk_state["total_orders"] >= self.risk_rules["max_total_orders"]:
                logger.warning(f"订单数超过限制: {self.current_risk_state['total_orders']} >= {self.risk_rules['max_total_orders']}")
                return False
            
            # 检查杠杆倍数
            leverage = signal.get('leverage', 1)
            if leverage > self.risk_rules["max_leverage"]:
                logger.warning(f"杠杆倍数超过限制: {leverage} > {self.risk_rules['max_leverage']}")
                return False
            
            logger.info(f"风险检查通过: {signal}")
            return True
            
        except Exception as e:
            logger.error(f"检查信号风险失败: {e}")
            return False
    
    def set_risk_rules(self, rules):
        """设置风险规则
        
        Args:
            rules (dict): 风险规则
        """
        self.risk_rules.update(rules)
        logger.info(f"风险规则更新: {self.agent_id}, 新规则: {rules}")
    
    def get_risk_rules(self):
        """获取风险规则
        
        Returns:
            dict: 风险规则
        """
        return self.risk_rules.copy()
    
    def get_risk_state(self):
        """获取风险状态
        
        Returns:
            dict: 风险状态
        """
        return self.current_risk_state.copy()
    
    def on_market_data_updated(self, data):
        """处理市场数据更新事件
        
        Args:
            data (dict): 市场数据
        """
        try:
            symbol = data.get('symbol')
            market_data = data.get('data')
            
            if market_data:
                # 计算波动率（使用价格变化百分比）
                change_pct = abs(market_data.get('change_pct', 0))
                self._update_volatility(change_pct)
        except Exception as e:
            logger.error(f"处理市场数据更新失败: {e}")
    
    def _update_volatility(self, volatility):
        """更新波动率历史
        
        Args:
            volatility (float): 波动率值
        """
        self.volatility_history.append(volatility)
        if len(self.volatility_history) > self.volatility_window:
            self.volatility_history.pop(0)
        
        # 计算平均波动率
        if self.volatility_history:
            avg_volatility = sum(self.volatility_history) / len(self.volatility_history)
            self.current_risk_state["market_volatility"] = avg_volatility
    
    def adjust_risk_thresholds(self):
        """动态调整风险阈值"""
        current_time = time.time()
        if current_time - self.last_adjustment_time < self.risk_adjustment_interval:
            return
        
        try:
            # 评估风险等级
            risk_level = self._assess_risk_level()
            self.current_risk_state["risk_level"] = risk_level
            
            # 根据风险等级调整风险规则
            adjustment_factor = self._calculate_adjustment_factor(risk_level)
            self.current_risk_state["adjustment_factor"] = adjustment_factor
            
            # 应用调整因子
            self._apply_adjustment_factor(adjustment_factor)
            
            # 发布风险规则更新事件
            self.publish('risk_rules_updated', {
                "rules": self.risk_rules,
                "risk_level": risk_level,
                "adjustment_factor": adjustment_factor,
                "timestamp": time.time()
            })
            
            self.last_adjustment_time = current_time
            
            logger.info(f"动态调整风险阈值完成，风险等级: {risk_level}, 调整因子: {adjustment_factor}")
            
        except Exception as e:
            logger.error(f"调整风险阈值失败: {e}")
    
    def _assess_risk_level(self):
        """评估风险等级
        
        Returns:
            str: 风险等级
        """
        volatility = self.current_risk_state.get("market_volatility", 0)
        
        if volatility < 0.5:
            return "low"
        elif volatility < 1.5:
            return "normal"
        elif volatility < 3.0:
            return "high"
        else:
            return "extreme"
    
    def _calculate_adjustment_factor(self, risk_level):
        """计算调整因子
        
        Args:
            risk_level (str): 风险等级
            
        Returns:
            float: 调整因子
        """
        factor_map = {
            "low": 1.2,    # 低风险时增加风险敞口
            "normal": 1.0,  # 正常风险时保持默认
            "high": 0.7,    # 高风险时减少风险敞口
            "extreme": 0.5  # 极端风险时大幅减少风险敞口
        }
        return factor_map.get(risk_level, 1.0)
    
    def _apply_adjustment_factor(self, factor):
        """应用调整因子到风险规则
        
        Args:
            factor (float): 调整因子
        """
        for key in self.base_risk_rules:
            if key in ["max_position_size", "max_order_size", "max_orders_per_symbol", "max_total_orders"]:
                # 调整数量类规则
                self.risk_rules[key] = int(self.base_risk_rules[key] * factor)
            elif key == "max_leverage":
                # 调整杠杆规则
                self.risk_rules[key] = max(1, int(self.base_risk_rules[key] * factor))
            elif key == "max_drawdown":
                # 调整回撤规则
                self.risk_rules[key] = self.base_risk_rules[key] * factor
    
    def process_message(self, message):
        """处理收到的消息
        
        Args:
            message (dict): 消息内容
        """
        super().process_message(message)
        
        if message.get('type') == 'set_risk_rules':
            # 设置风险规则请求
            self.set_risk_rules(message.get('rules', {}))
            if message.get('sender'):
                self.send_message(message.get('sender'), {
                    'type': 'risk_rules_updated',
                    'rules': self.get_risk_rules()
                })
        elif message.get('type') == 'get_risk_state':
            # 获取风险状态请求
            if message.get('sender'):
                self.send_message(message.get('sender'), {
                    'type': 'risk_state_response',
                    'state': self.get_risk_state()
                })
        elif message.get('type') == 'get_risk_rules':
            # 获取风险规则请求
            if message.get('sender'):
                self.send_message(message.get('sender'), {
                    'type': 'risk_rules_response',
                    'rules': self.get_risk_rules()
                })
        elif message.get('type') == 'get_risk_level':
            # 获取风险等级请求
            if message.get('sender'):
                self.send_message(message.get('sender'), {
                    'type': 'risk_level_response',
                    'risk_level': self.current_risk_state.get('risk_level'),
                    'market_volatility': self.current_risk_state.get('market_volatility')
                })
