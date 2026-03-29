"""
策略监控模块 - 用于监控策略运行状态和性能指标
"""
import asyncio
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger("StrategyMonitor")


@dataclass
class StrategyMetrics:
    """策略性能指标"""
    total_trades: int = 0
    win_trades: int = 0
    lose_trades: int = 0
    total_profit: float = 0
    max_drawdown: float = 0
    sharpe_ratio: float = 0
    win_rate: float = 0
    avg_profit_per_trade: float = 0
    last_trade_time: Optional[datetime] = None
    strategy_uptime: float = 0  # 策略运行时间（秒）
    execution_count: int = 0  # 策略执行次数
    average_execution_time: float = 0  # 平均执行时间（秒）


class StrategyMonitor:
    """策略监控器"""
    
    def __init__(self):
        """初始化策略监控器"""
        self.strategies: Dict[str, Dict] = {}
        self.start_time = time.time()
        self.monitoring_task: Optional[asyncio.Task] = None
        self.running = False
        
        logger.info("策略监控器初始化完成")
    
    def register_strategy(self, strategy_name: str):
        """注册策略
        
        Args:
            strategy_name: 策略名称
        """
        if strategy_name not in self.strategies:
            self.strategies[strategy_name] = {
                'status': 'idle',
                'metrics': StrategyMetrics(),
                'start_time': None,
                'last_update': datetime.now(),
                'execution_times': [],  # 存储执行时间
                'performance_history': [],  # 存储性能历史
                'trade_history': []  # 存储交易历史
            }
            logger.info(f"策略已注册: {strategy_name}")
    
    def update_strategy_status(self, strategy_name: str, status: str):
        """更新策略状态
        
        Args:
            strategy_name: 策略名称
            status: 状态 (idle, running, paused, error)
        """
        if strategy_name in self.strategies:
            self.strategies[strategy_name]['status'] = status
            self.strategies[strategy_name]['last_update'] = datetime.now()
            
            if status == 'running' and self.strategies[strategy_name]['start_time'] is None:
                self.strategies[strategy_name]['start_time'] = time.time()
            
            logger.debug(f"策略状态更新: {strategy_name} -> {status}")
    
    def update_strategy_metrics(self, strategy_name: str, metrics: Dict):
        """更新策略性能指标
        
        Args:
            strategy_name: 策略名称
            metrics: 性能指标
        """
        if strategy_name in self.strategies:
            strategy_data = self.strategies[strategy_name]
            strategy_metrics = strategy_data['metrics']
            
            # 更新基本指标
            if 'total_trades' in metrics:
                strategy_metrics.total_trades = metrics['total_trades']
            if 'win_trades' in metrics:
                strategy_metrics.win_trades = metrics['win_trades']
            if 'lose_trades' in metrics:
                strategy_metrics.lose_trades = metrics['lose_trades']
            if 'total_profit' in metrics:
                strategy_metrics.total_profit = metrics['total_profit']
            if 'max_drawdown' in metrics:
                strategy_metrics.max_drawdown = metrics['max_drawdown']
            if 'sharpe_ratio' in metrics:
                strategy_metrics.sharpe_ratio = metrics['sharpe_ratio']
            
            # 计算派生指标
            if strategy_metrics.total_trades > 0:
                strategy_metrics.win_rate = strategy_metrics.win_trades / strategy_metrics.total_trades
                strategy_metrics.avg_profit_per_trade = strategy_metrics.total_profit / strategy_metrics.total_trades
            
            # 更新运行时间
            if strategy_data['start_time']:
                strategy_metrics.strategy_uptime = time.time() - strategy_data['start_time']
            
            # 记录性能历史
            strategy_data['performance_history'].append({
                'timestamp': datetime.now(),
                'profit': strategy_metrics.total_profit,
                'win_rate': strategy_metrics.win_rate,
                'total_trades': strategy_metrics.total_trades
            })
            
            # 限制历史记录长度
            if len(strategy_data['performance_history']) > 1000:
                strategy_data['performance_history'] = strategy_data['performance_history'][-1000:]
            
            strategy_data['last_update'] = datetime.now()
    
    def record_execution_time(self, strategy_name: str, execution_time: float):
        """记录策略执行时间
        
        Args:
            strategy_name: 策略名称
            execution_time: 执行时间（秒）
        """
        if strategy_name in self.strategies:
            strategy_data = self.strategies[strategy_name]
            strategy_data['execution_times'].append(execution_time)
            strategy_data['metrics'].execution_count += 1
            
            # 计算平均执行时间
            if strategy_data['metrics'].execution_count > 0:
                strategy_data['metrics'].average_execution_time = (
                    sum(strategy_data['execution_times']) / len(strategy_data['execution_times'])
                )
            
            # 限制执行时间记录长度
            if len(strategy_data['execution_times']) > 100:
                strategy_data['execution_times'] = strategy_data['execution_times'][-100:]
    
    def record_trade(self, strategy_name: str, trade_data: Dict):
        """记录交易
        
        Args:
            strategy_name: 策略名称
            trade_data: 交易数据
        """
        if strategy_name in self.strategies:
            strategy_data = self.strategies[strategy_name]
            trade_record = {
                'timestamp': datetime.now(),
                'trade_id': trade_data.get('trade_id', f"trade_{int(time.time() * 1000)}"),
                'inst_id': trade_data.get('inst_id', ''),
                'side': trade_data.get('side', ''),
                'price': trade_data.get('price', 0),
                'amount': trade_data.get('amount', 0),
                'profit': trade_data.get('profit', 0),
                'status': trade_data.get('status', 'completed')
            }
            
            strategy_data['trade_history'].append(trade_record)
            strategy_data['metrics'].last_trade_time = trade_record['timestamp']
            
            # 限制交易历史长度
            if len(strategy_data['trade_history']) > 100:
                strategy_data['trade_history'] = strategy_data['trade_history'][-100:]
    
    def get_strategy_status(self, strategy_name: str) -> Optional[Dict]:
        """获取策略状态
        
        Args:
            strategy_name: 策略名称
            
        Returns:
            Optional[Dict]: 策略状态
        """
        if strategy_name in self.strategies:
            strategy_data = self.strategies[strategy_name]
            return {
                'name': strategy_name,
                'status': strategy_data['status'],
                'metrics': strategy_data['metrics'].__dict__,
                'last_update': strategy_data['last_update'].isoformat(),
                'start_time': strategy_data['start_time']
            }
        return None
    
    def get_all_strategies_status(self) -> Dict[str, Dict]:
        """获取所有策略状态
        
        Returns:
            Dict[str, Dict]: 所有策略状态
        """
        statuses = {}
        for strategy_name in self.strategies:
            statuses[strategy_name] = self.get_strategy_status(strategy_name)
        return statuses
    
    def get_strategy_performance_history(self, strategy_name: str, limit: int = 100) -> List[Dict]:
        """获取策略性能历史
        
        Args:
            strategy_name: 策略名称
            limit: 限制数量
            
        Returns:
            List[Dict]: 性能历史
        """
        if strategy_name in self.strategies:
            history = self.strategies[strategy_name]['performance_history']
            return history[-limit:]
        return []
    
    def get_strategy_trade_history(self, strategy_name: str, limit: int = 50) -> List[Dict]:
        """获取策略交易历史
        
        Args:
            strategy_name: 策略名称
            limit: 限制数量
            
        Returns:
            List[Dict]: 交易历史
        """
        if strategy_name in self.strategies:
            history = self.strategies[strategy_name]['trade_history']
            return history[-limit:]
        return []
    
    def get_overall_metrics(self) -> Dict:
        """获取整体指标
        
        Returns:
            Dict: 整体指标
        """
        total_trades = 0
        total_profit = 0
        running_strategies = 0
        total_strategies = len(self.strategies)
        
        for strategy_name, data in self.strategies.items():
            total_trades += data['metrics'].total_trades
            total_profit += data['metrics'].total_profit
            if data['status'] == 'running':
                running_strategies += 1
        
        return {
            'total_strategies': total_strategies,
            'running_strategies': running_strategies,
            'total_trades': total_trades,
            'total_profit': total_profit,
            'uptime': time.time() - self.start_time
        }
    
    async def start_monitoring(self, interval: float = 10.0):
        """开始监控
        
        Args:
            interval: 监控间隔（秒）
        """
        self.running = True
        logger.info(f"开始策略监控，间隔: {interval}秒")
        
        while self.running:
            await asyncio.sleep(interval)
            self._perform_monitoring()
    
    def _perform_monitoring(self):
        """执行监控任务"""
        # 检查策略状态
        for strategy_name, data in self.strategies.items():
            # 检查策略是否长时间未更新
            time_since_update = (datetime.now() - data['last_update']).total_seconds()
            if time_since_update > 60 and data['status'] == 'running':
                logger.warning(f"策略长时间未更新: {strategy_name} ({time_since_update:.1f}秒)")
            
            # 检查执行时间是否过长
            if data['metrics'].average_execution_time > 1.0:
                logger.warning(f"策略执行时间过长: {strategy_name} ({data['metrics'].average_execution_time:.2f}秒)")
        
        # 记录整体状态
        overall = self.get_overall_metrics()
        logger.debug(f"监控状态: 策略数={overall['total_strategies']}, 运行中={overall['running_strategies']}, 总交易数={overall['total_trades']}, 总盈亏={overall['total_profit']:.2f}")
    
    def stop_monitoring(self):
        """停止监控"""
        self.running = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
        logger.info("策略监控已停止")
    
    def clear_strategy_data(self, strategy_name: str):
        """清除策略数据
        
        Args:
            strategy_name: 策略名称
        """
        if strategy_name in self.strategies:
            self.strategies[strategy_name] = {
                'status': 'idle',
                'metrics': StrategyMetrics(),
                'start_time': None,
                'last_update': datetime.now(),
                'execution_times': [],
                'performance_history': [],
                'trade_history': []
            }
            logger.info(f"策略数据已清除: {strategy_name}")
    
    def remove_strategy(self, strategy_name: str):
        """移除策略
        
        Args:
            strategy_name: 策略名称
        """
        if strategy_name in self.strategies:
            del self.strategies[strategy_name]
            logger.info(f"策略已移除: {strategy_name}")


# 创建全局策略监控实例
strategy_monitor = StrategyMonitor()
