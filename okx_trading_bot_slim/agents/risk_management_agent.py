from loguru import logger
from agents.base_agent import BaseAgent
from services.risk_management.risk_manager import RiskManager
import time

class RiskManagementAgent(BaseAgent):
    """风险控制智能体，负责监控和控制交易风险"""
    
    def __init__(self, agent_id, config=None):
        super().__init__(agent_id, config)
        self.risk_manager = None
        self.risk_rules = {
            # 默认风险规则
            "max_position_size": config.get("max_position_size", 1000),  # 最大持仓价值
            "max_order_size": config.get("max_order_size", 100),  # 最大单笔订单价值
            "max_leverage": config.get("max_leverage", 10),  # 最大杠杆倍数
            "max_drawdown": config.get("max_drawdown", 0.1),  # 最大回撤比例
            "max_orders_per_symbol": config.get("max_orders_per_symbol", 5),  # 每个交易对最大订单数
            "max_total_orders": config.get("max_total_orders", 20),  # 总最大订单数
        }
        self.current_risk_state = {
            "total_position_value": 0,
            "total_orders": 0,
            "current_drawdown": 0,
            "active_symbols": set(),
        }
        
        # 订阅事件
        self.subscribe('order_placed', self.on_order_placed)
        self.subscribe('order_updated', self.on_order_updated)
        self.subscribe('order_canceled', self.on_order_canceled)
        self.subscribe('all_orders_canceled', self.on_all_orders_canceled)
        self.subscribe('trading_signal', self.on_trading_signal)
        
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
