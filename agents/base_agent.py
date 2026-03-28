from PyQt5.QtCore import QObject, QThread
from commons.logger_config import get_logger
logger = get_logger(region="Agent")
from commons.event_bus import global_event_bus
from commons.agent_registry import global_agent_registry

class BaseAgent(QObject):
    """智能体基类，所有智能体的父类"""
    
    # 状态映射字典，将英文状态转换为中文
    STATUS_MAP = {
        "idle": "空闲",
        "running": "运行中",
        "stopped": "已停止",
        "error": "错误"
    }
    
    # 智能体ID映射，将英文ID转换为中文名称
    AGENT_ID_MAP = {
        "decision_coordination_agent": "决策协调智能体",
        "market_data_agent": "市场数据智能体",
        "order_agent": "订单管理智能体",
        "risk_management_agent": "风险控制智能体",
        "strategy_execution_agent": "策略执行智能体"
    }
    
    # 智能体类型映射，将类名转换为中文类型
    AGENT_TYPE_MAP = {
        "DecisionCoordinationAgent": "决策协调智能体",
        "MarketDataAgent": "市场数据智能体",
        "OrderAgent": "订单管理智能体",
        "RiskManagementAgent": "风险控制智能体",
        "StrategyExecutionAgent": "策略执行智能体"
    }
    
    def __init__(self, agent_id, config=None):
        super().__init__()
        self.agent_id = agent_id
        self.config = config or {}
        self._status = "idle"  # idle, running, stopped, error
        self.event_bus = global_event_bus
        self.agent_registry = global_agent_registry
        self.threads = []  # 存储所有线程
        
        logger.info(f"智能体基类初始化: {self.agent_id}")
    
    @property
    def status(self):
        """获取智能体状态（英文）"""
        return self._status
    
    @status.setter
    def status(self, value):
        """设置智能体状态（英文）"""
        if value in self.STATUS_MAP:
            self._status = value
        else:
            logger.warning(f"无效的智能体状态: {value}")
    
    def start(self):
        """启动智能体"""
        if self._status == "running":
            logger.warning(f"智能体已在运行: {self.agent_id}")
            return
        
        self._status = "running"
        logger.info(f"智能体启动: {self.agent_id}")
        
        # 发布智能体状态变化事件（使用中文状态）
        self.event_bus.publish("agent_status_changed", {
            "agent_id": self.agent_id,
            "status": self.STATUS_MAP[self._status]
        })
    
    def stop(self):
        """停止智能体"""
        if self._status == "stopped":
            logger.warning(f"智能体已停止: {self.agent_id}")
            return
        
        # 先更新状态，让线程的循环条件失效
        self._status = "stopped"
        
        # 停止所有线程
        for thread in self.threads:
            if thread:
                try:
                    # 检查是否是 QThread
                    if hasattr(thread, 'isRunning') and hasattr(thread, 'quit') and hasattr(thread, 'wait'):
                        if thread.isRunning():
                            thread.quit()
                            # 添加超时机制，避免无限等待
                            if not thread.wait(5000):  # 5秒超时
                                logger.warning(f"智能体 QThread 停止超时: {self.agent_id}")
                            else:
                                logger.info(f"智能体 QThread 已停止: {self.agent_id}")
                    # 检查是否是 threading.Thread
                    elif hasattr(thread, 'is_alive'):
                        if thread.is_alive():
                            # 对于普通线程，我们只能等待其自行结束
                            # 因为线程循环条件会检查 self.status == 'running'
                            logger.info(f"等待智能体线程结束: {self.agent_id}")
                except Exception as e:
                    logger.error(f"停止线程时出错: {e}")
        
        # 清空线程列表
        self.threads.clear()
        
        logger.info(f"智能体停止: {self.agent_id}")
        
        # 发布智能体状态变化事件（使用中文状态）
        self.event_bus.publish("agent_status_changed", {
            "agent_id": self.agent_id,
            "status": self.STATUS_MAP[self._status]
        })
    
    def process_message(self, message):
        """处理收到的消息
        
        Args:
            message (dict): 消息内容
        """
        logger.debug(f"智能体 {self.agent_id} 收到消息: {message}")
    
    def send_message(self, recipient_id, message):
        """发送消息给其他智能体
        
        Args:
            recipient_id (str): 接收智能体ID
            message (dict): 消息内容
        """
        recipient = self.agent_registry.get_agent(recipient_id)
        if recipient:
            recipient.process_message(message)
            logger.debug(f"智能体 {self.agent_id} 发送消息给 {recipient_id}: {message}")
        else:
            logger.warning(f"智能体 {recipient_id} 不存在")
    
    def publish(self, event_name, data):
        """发布事件
        
        Args:
            event_name (str): 事件名称
            data (dict): 事件数据
        """
        self.event_bus.publish(event_name, data)
    
    def subscribe(self, event_name, callback):
        """订阅事件
        
        Args:
            event_name (str): 事件名称
            callback (callable): 回调函数
        """
        self.event_bus.subscribe(event_name, callback)
    
    def unsubscribe(self, event_name, callback):
        """取消订阅事件
        
        Args:
            event_name (str): 事件名称
            callback (callable): 回调函数
        """
        self.event_bus.unsubscribe(event_name, callback)
    
    def run_in_thread(self, target):
        """在独立线程中运行目标函数
        
        Args:
            target (callable): 目标函数
        """
        try:
            from PyQt5.QtCore import QThread, QObject
            # 检查是否有 QApplication 实例
            from PyQt5.QtWidgets import QApplication
            if QApplication.instance() is not None:
                # 使用 QThread（有 GUI 环境）
                thread = QThread()
                
                # 创建一个工作对象
                class Worker(QObject):
                    def __init__(self, target):
                        super().__init__()
                        self.target = target
                    
                    def run(self):
                        try:
                            self.target()
                        except Exception as e:
                            logger.error(f"线程执行失败: {e}")
                
                worker = Worker(target)
                worker.moveToThread(thread)
                thread.started.connect(worker.run)
                thread.finished.connect(worker.deleteLater)
                thread.finished.connect(thread.deleteLater)
                
                # 添加线程到列表
                self.threads.append(thread)
                
                thread.start()
            else:
                # 使用普通 threading.Thread（无 GUI 环境，如测试）
                import threading
                def thread_target():
                    try:
                        target()
                    except Exception as e:
                        logger.error(f"线程执行失败: {e}")
                
                thread = threading.Thread(target=thread_target, daemon=True)
                # 添加线程到列表
                self.threads.append(thread)
                thread.start()
        except ImportError:
            # 如果没有 PyQt5，使用普通 threading.Thread
            import threading
            def thread_target():
                try:
                    target()
                except Exception as e:
                    logger.error(f"线程执行失败: {e}")
            
            thread = threading.Thread(target=thread_target, daemon=True)
            # 添加线程到列表
            self.threads.append(thread)
            thread.start()
        logger.debug(f"智能体 {self.agent_id} 启动线程，当前线程数: {len(self.threads)}")
    
    def get_status(self):
        """获取智能体状态
        
        Returns:
            dict: 智能体状态（包含中文名称、类型和状态）
        """
        return {
            "agent_id": self.agent_id,  # 保留英文ID用于内部识别
            "agent_name": self.AGENT_ID_MAP.get(self.agent_id, self.agent_id),  # 返回中文名称
            "status": self.STATUS_MAP[self._status],  # 返回中文状态
            "agent_type": self.AGENT_TYPE_MAP.get(self.__class__.__name__, self.__class__.__name__)  # 返回中文类型
        }
    
    def update_config(self, new_config):
        """更新智能体配置
        
        Args:
            new_config (dict): 新配置
        """
        self.config.update(new_config)
        logger.info(f"智能体配置更新: {self.agent_id}, 新配置: {new_config}")
    
    def get_config(self):
        """获取智能体配置
        
        Returns:
            dict: 智能体配置
        """
        return self.config.copy()