import logging
import time
import json
from datetime import datetime

from core.monitoring import strategy_monitor

logger = logging.getLogger("Strategy")


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
            "sharpe_ratio": 0,
        }
        self.trade_logs = []
        self.execution_logs = []
        self.last_execution_time = None

        # 注册策略到监控器
        strategy_monitor.register_strategy(self.name)
        strategy_monitor.update_strategy_status(self.name, self.status)

        logger.info(f"策略初始化完成: {self.name}")

    def execute(self, market_data):
        """执行策略，生成交易信号

        Args:
            market_data (dict): 市场数据

        Returns:
            dict: 交易信号，包含side, price, amount等信息
        """
        start_time = time.time()
        self.last_execution_time = datetime.now()

        # 记录执行开始
        execution_id = f"exec_{int(time.time() * 1000)}"
        self._log_execution(execution_id, "start", market_data)

        try:
            signal = self._execute_strategy(market_data)
            execution_time = time.time() - start_time

            # 记录执行时间到监控器
            strategy_monitor.record_execution_time(self.name, execution_time)

            # 记录执行结果
            self._log_execution(
                execution_id,
                "end",
                {"signal": signal, "execution_time": f"{execution_time:.3f}s"},
            )

            return signal
        except Exception as e:
            execution_time = time.time() - start_time

            # 记录执行时间到监控器
            strategy_monitor.record_execution_time(self.name, execution_time)

            # 记录错误
            self._log_execution(
                execution_id,
                "error",
                {"error": str(e), "execution_time": f"{execution_time:.3f}s"},
            )

            # 更新策略状态为错误
            strategy_monitor.update_strategy_status(self.name, "error")

            logger.error(f"策略执行错误: {self.name}, 错误: {e}")
            return None

    def _execute_strategy(self, market_data):
        """策略执行逻辑，子类必须实现

        Args:
            market_data (dict): 市场数据

        Returns:
            dict: 交易信号
        """
        raise NotImplementedError("子类必须实现_execute_strategy方法")

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
        old_params = self.config.copy()
        self.config.update(params)
        logger.info(f"策略参数更新: {self.name}, 新参数: {params}")
        self._log_execution(
            "param_update",
            "params_updated",
            {"old_params": old_params, "new_params": params},
        )

    def start(self):
        """启动策略"""
        self.status = "running"
        logger.info(f"策略启动: {self.name}")
        self._log_execution("startup", "strategy_started", {})
        # 更新监控器中的策略状态
        strategy_monitor.update_strategy_status(self.name, self.status)

    def stop(self):
        """停止策略"""
        self.status = "idle"
        logger.info(f"策略停止: {self.name}")
        self._log_execution("shutdown", "strategy_stopped", {})
        # 更新监控器中的策略状态
        strategy_monitor.update_strategy_status(self.name, self.status)

    def pause(self):
        """暂停策略"""
        self.status = "paused"
        logger.info(f"策略暂停: {self.name}")
        self._log_execution("pause", "strategy_paused", {})
        # 更新监控器中的策略状态
        strategy_monitor.update_strategy_status(self.name, self.status)

    def resume(self):
        """恢复策略"""
        self.status = "running"
        logger.info(f"策略恢复: {self.name}")
        self._log_execution("resume", "strategy_resumed", {})
        # 更新监控器中的策略状态
        strategy_monitor.update_strategy_status(self.name, self.status)

    def get_status(self):
        """获取策略状态

        Returns:
            dict: 策略状态
        """
        return {
            "name": self.name,
            "status": self.status,
            "performance": self.performance,
            "last_execution_time": str(self.last_execution_time),
            "total_trades": len(self.trade_logs),
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

        # 记录交易结果
        self._log_trade(trade_result)

        # 更新监控器中的策略性能指标
        strategy_monitor.update_strategy_metrics(self.name, self.performance)

        # 记录交易到监控器
        strategy_monitor.record_trade(self.name, trade_result)

        logger.debug(f"策略性能更新: {self.name}, 性能指标: {self.performance}")

    def backtest(self, historical_data):
        """回测策略

        Args:
            historical_data (list): 历史数据

        Returns:
            dict: 回测结果
        """
        logger.info(f"开始回测: {self.name}")
        self._log_execution(
            "backtest", "backtest_started", {"data_points": len(historical_data)}
        )

        # 回测实现逻辑
        result = {
            "strategy": self.name,
            "total_trades": 0,
            "win_rate": 0,
            "total_profit": 0,
            "max_drawdown": 0,
            "sharpe_ratio": 0,
        }

        self._log_execution("backtest", "backtest_completed", result)
        return result

    def _log_trade(self, trade_result):
        """记录交易日志

        Args:
            trade_result (dict): 交易结果
        """
        trade_log = {
            "timestamp": datetime.now().isoformat(),
            "strategy": self.name,
            "trade_id": trade_result.get(
                "trade_id", f"trade_{int(time.time() * 1000)}"
            ),
            "inst_id": trade_result.get("inst_id", ""),
            "side": trade_result.get("side", ""),
            "price": trade_result.get("price", 0),
            "amount": trade_result.get("amount", 0),
            "profit": trade_result.get("profit", 0),
            "status": trade_result.get("status", "completed"),
            "fee": trade_result.get("fee", 0),
        }
        self.trade_logs.append(trade_log)
        logger.info(f"交易记录: {json.dumps(trade_log, ensure_ascii=False)}")

    def _log_execution(self, execution_id, event_type, details):
        """记录执行日志

        Args:
            execution_id: 执行ID
            event_type: 事件类型
            details: 详细信息
        """
        execution_log = {
            "timestamp": datetime.now().isoformat(),
            "strategy": self.name,
            "execution_id": execution_id,
            "event_type": event_type,
            "details": details,
        }
        self.execution_logs.append(execution_log)
        logger.debug(f"执行记录: {json.dumps(execution_log, ensure_ascii=False)}")

    def get_trade_logs(self, limit=100):
        """获取交易日志

        Args:
            limit: 限制数量

        Returns:
            list: 交易日志列表
        """
        return self.trade_logs[-limit:]

    def get_execution_logs(self, limit=100):
        """获取执行日志

        Args:
            limit: 限制数量

        Returns:
            list: 执行日志列表
        """
        return self.execution_logs[-limit:]

    def clear_logs(self):
        """清空日志"""
        self.trade_logs = []
        self.execution_logs = []
        logger.info(f"策略日志已清空: {self.name}")
