from commons.logger_config import get_logger
logger = get_logger(region="Strategy")

class BaseStrategy:
    """策略基类，所有交易策略的父类"""
    
    def __init__(self, api_client=None, config=None):
        """初始化策略
        
        Args:
            api_client: OKX API客户端实例
            config (dict): 策略配置
        """
        self.api_client = api_client
        self.config = config or {}
        self.name = self.__class__.__name__
        self.status = "idle"  # idle, running, paused
        self.performance = {
            "total_trades": 0,
            "win_trades": 0,
            "lose_trades": 0,
            "total_profit": 0,
            "max_drawdown": 0,
            "sharpe_ratio": 0
        }
        
        logger.info(f"策略初始化完成: {self.name}")
    
    def execute(self, market_data):
        """执行策略，生成交易信号
        
        Args:
            market_data (dict): 市场数据
            
        Returns:
            dict: 交易信号，包含side, price, amount等信息
        """
        raise NotImplementedError("子类必须实现execute方法")
    
    def get_params(self):
        """获取策略参数
        
        Returns:
            dict: 策略参数
        """
        return self.config.copy()
    
    def set_params(self, params):
        """设置策略参数
        
        Args:
            params (dict): 策略参数
        """
        self.config.update(params)
        logger.info(f"策略参数更新: {self.name}, 新参数: {params}")
    
    def start(self):
        """启动策略"""
        self.status = "running"
        logger.info(f"策略启动: {self.name}")
    
    def stop(self):
        """停止策略"""
        self.status = "idle"
        logger.info(f"策略停止: {self.name}")
    
    def pause(self):
        """暂停策略"""
        self.status = "paused"
        logger.info(f"策略暂停: {self.name}")
    
    def resume(self):
        """恢复策略"""
        self.status = "running"
        logger.info(f"策略恢复: {self.name}")
    
    def get_status(self):
        """获取策略状态
        
        Returns:
            dict: 策略状态
        """
        return {
            "name": self.name,
            "status": self.status,
            "performance": self.performance
        }
    
    def update_performance(self, trade_result):
        """更新策略性能指标
        
        Args:
            trade_result (dict): 交易结果
        """
        # 更新交易次数
        self.performance["total_trades"] += 1
        
        # 更新盈亏
        profit = trade_result.get("profit", 0)
        self.performance["total_profit"] += profit
        
        # 更新胜负次数
        if profit > 0:
            self.performance["win_trades"] += 1
        elif profit < 0:
            self.performance["lose_trades"] += 1
        
        # 更新最大回撤（简化计算）
        current_drawdown = trade_result.get("drawdown", 0)
        if current_drawdown > self.performance["max_drawdown"]:
            self.performance["max_drawdown"] = current_drawdown
        
        # 计算夏普比率（简化计算）
        if self.performance["total_trades"] > 0:
            win_rate = self.performance["win_trades"] / self.performance["total_trades"]
            self.performance["sharpe_ratio"] = win_rate * 2 - 1  # 简化的夏普比率计算
        
        logger.debug(f"策略性能更新: {self.name}, 性能指标: {self.performance}")
    
    def backtest(self, historical_data):
        """回测策略
        
        Args:
            historical_data (list): 历史数据
            
        Returns:
            dict: 回测结果
        """
        logger.info(f"开始回测: {self.name}")
        # 回测实现逻辑
        return {
            "strategy": self.name,
            "total_trades": 0,
            "win_rate": 0,
            "total_profit": 0,
            "max_drawdown": 0,
            "sharpe_ratio": 0
        }