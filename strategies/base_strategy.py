import logging
import time
import json
from datetime import datetime

from core.monitoring import strategy_monitor
from core.storage.data_persistence import data_persistence

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
        
        # 加载历史日志
        self.trade_logs = data_persistence.load_trade_logs(self.name)
        self.execution_logs = data_persistence.load_execution_logs(self.name)
        self.last_execution_time = None

        # 注册策略到监控器
        strategy_monitor.register_strategy(self.name)
        strategy_monitor.update_strategy_status(self.name, self.status)

        logger.info(f"策略初始化完成: {self.name}, 加载了 {len(self.trade_logs)} 条交易记录, {len(self.execution_logs)} 条执行记录")

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
    
    async def on_trade_event(self, trade_data: dict, total_fees: float):
        """处理交易事件
        
        Args:
            trade_data (dict): 交易数据
            total_fees (float): 累计手续费
        """
        try:
            # 分析交易数据
            fee = trade_data.get('fee', 0)
            side = trade_data.get('side')
            price = trade_data.get('price')
            size = trade_data.get('filled_size')
            
            logger.info(f"策略 {self.name} 收到交易事件:")
            logger.info(f"  交易方向: {side}")
            logger.info(f"  交易价格: {price}")
            logger.info(f"  交易数量: {size}")
            logger.info(f"  交易手续费: {fee}")
            logger.info(f"  累计手续费: {total_fees}")
            
            # 更新账户收益信息
            self._update_account_pnl(trade_data, total_fees)
            
            # 分析是否可以交易
            can_trade = self._analyze_trade_opportunity(trade_data, total_fees)
            logger.info(f"  交易机会分析: {'可以交易' if can_trade else '不建议交易'}")
            
            # 记录交易事件
            self._log_execution(
                "trade_event",
                "trade_processed",
                {
                    "trade_id": trade_data.get('trade_id'),
                    "side": side,
                    "price": price,
                    "size": size,
                    "fee": fee,
                    "total_fees": total_fees,
                    "can_trade": can_trade,
                    "account_pnl": getattr(self, 'account_pnl', 0),
                    "account_pnl_ratio": getattr(self, 'account_pnl_ratio', 0)
                }
            )
            
        except Exception as e:
            logger.error(f"策略 {self.name} 处理交易事件失败: {e}")
    
    def _update_account_pnl(self, trade_data: dict, total_fees: float):
        """更新账户收益信息
        
        Args:
            trade_data (dict): 交易数据
            total_fees (float): 累计手续费
        """
        try:
            # 这里简化处理，实际应用中需要从API获取真实的账户余额
            # 假设每次交易后更新账户收益
            if hasattr(self, 'account_equity'):
                # 模拟账户收益更新
                # 实际应用中应该从API获取真实的账户余额
                price = trade_data.get('price', 0)
                size = trade_data.get('filled_size', 0)
                side = trade_data.get('side')
                
                # 计算本次交易的盈亏
                if side == 'buy':
                    # 买入时，假设使用1 USDT
                    self.account_equity -= 1.0
                elif side == 'sell':
                    # 卖出时，假设卖出0.00002 BTC
                    self.account_equity += price * 0.00002
                
                # 初始账户权益假设为2.5 USDT
                if self.account_equity == 0:
                    self.account_equity = 2.5
                
                # 计算账户总盈亏
                self.account_pnl = self.account_equity - 2.5
                # 计算账户收益率
                self.account_pnl_ratio = self.account_pnl / 2.5 * 100
                
                logger.info(f"  账户总权益: {self.account_equity:.4f} USDT")
                logger.info(f"  账户总盈亏: {self.account_pnl:.4f} USDT")
                logger.info(f"  账户收益率: {self.account_pnl_ratio:.2f}%")
                
        except Exception as e:
            logger.error(f"更新账户收益信息失败: {e}")
    
    def _analyze_trade_opportunity(self, trade_data: dict, total_fees: float) -> bool:
        """分析交易机会
        
        Args:
            trade_data (dict): 交易数据
            total_fees (float): 累计手续费
            
        Returns:
            bool: 是否可以交易
        """
        # 简单的交易机会分析
        # 实际应用中可以根据策略逻辑进行更复杂的分析
        try:
            # 检查手续费是否过高
            fee = trade_data.get('fee', 0)
            if fee > 0.01:  # 手续费超过0.01 USDT
                logger.warning(f"手续费过高: {fee} USDT")
                return False
            
            # 检查累计手续费是否过高
            if total_fees > 1.0:  # 累计手续费超过1.0 USDT
                logger.warning(f"累计手续费过高: {total_fees} USDT")
                return False
            
            # 检查交易价格是否合理
            price = trade_data.get('price', 0)
            if price <= 0:
                logger.warning("交易价格不合理")
                return False
            
            # 检查交易数量是否合理
            size = trade_data.get('filled_size', 0)
            if size <= 0:
                logger.warning("交易数量不合理")
                return False
            
            # 默认可以交易
            return True
            
        except Exception as e:
            logger.error(f"分析交易机会失败: {e}")
            return False
    
    async def on_trade_metrics(self, trade_stats: dict, risk_level: str):
        """处理交易指标事件
        
        Args:
            trade_stats (dict): 交易统计数据
            risk_level (str): 风险等级
        """
        try:
            # 分析交易指标数据
            win_rate = trade_stats.get('win_rate', 0)
            profit_factor = trade_stats.get('profit_factor', 1)
            total_trades = trade_stats.get('total_trades', 0)
            
            logger.info(f"策略 {self.name} 收到交易指标事件:")
            logger.info(f"  总交易数: {total_trades}")
            logger.info(f"  胜率: {win_rate:.2f}")
            logger.info(f"  盈利因子: {profit_factor:.2f}")
            logger.info(f"  风险等级: {risk_level}")
            
            # 基于交易指标调整策略参数
            self._adjust_strategy_based_on_metrics(trade_stats, risk_level)
            
            # 记录交易指标事件
            self._log_execution(
                "trade_metrics",
                "metrics_processed",
                {
                    "win_rate": win_rate,
                    "profit_factor": profit_factor,
                    "total_trades": total_trades,
                    "risk_level": risk_level
                }
            )
            
        except Exception as e:
            logger.error(f"策略 {self.name} 处理交易指标事件失败: {e}")
    
    def _adjust_strategy_based_on_metrics(self, trade_stats: dict, risk_level: str):
        """基于交易指标调整策略参数
        
        Args:
            trade_stats (dict): 交易统计数据
            risk_level (str): 风险等级
        """
        try:
            # 分析交易指标
            win_rate = trade_stats.get('win_rate', 0)
            profit_factor = trade_stats.get('profit_factor', 1)
            
            # 根据胜率和盈利因子调整策略参数
            if hasattr(self, 'current_threshold'):
                # 胜率高时，降低阈值，增加交易频率
                if win_rate > 0.6:
                    new_threshold = max(self.min_threshold, self.current_threshold * 0.9)
                    if new_threshold < self.current_threshold:
                        self.current_threshold = new_threshold
                        logger.info(f"基于高胜率调整阈值: {self.current_threshold}")
                # 胜率低时，提高阈值，减少交易频率
                elif win_rate < 0.4:
                    new_threshold = min(self.max_threshold, self.current_threshold * 1.1)
                    if new_threshold > self.current_threshold:
                        self.current_threshold = new_threshold
                        logger.info(f"基于低胜率调整阈值: {self.current_threshold}")
                
                # 盈利因子高时，降低阈值，增加交易频率
                if profit_factor > 1.5:
                    new_threshold = max(self.min_threshold, self.current_threshold * 0.9)
                    if new_threshold < self.current_threshold:
                        self.current_threshold = new_threshold
                        logger.info(f"基于高盈利因子调整阈值: {self.current_threshold}")
                # 盈利因子低时，提高阈值，减少交易频率
                elif profit_factor < 0.8:
                    new_threshold = min(self.max_threshold, self.current_threshold * 1.1)
                    if new_threshold > self.current_threshold:
                        self.current_threshold = new_threshold
                        logger.info(f"基于低盈利因子调整阈值: {self.current_threshold}")
            
            # 根据风险等级调整策略参数
            if risk_level == "high" or risk_level == "critical":
                # 高风险时，提高阈值，减少交易频率
                if hasattr(self, 'current_threshold'):
                    new_threshold = min(self.max_threshold, self.current_threshold * 1.2)
                    if new_threshold > self.current_threshold:
                        self.current_threshold = new_threshold
                        logger.info(f"基于高风险调整阈值: {self.current_threshold}")
            
        except Exception as e:
            logger.error(f"基于交易指标调整策略参数失败: {e}")
    
    async def on_low_return_event(self, params: dict, expected_return: float, reason: str, market_prediction: dict = None):
        """处理低收益率事件
        
        Args:
            params (dict): 订单参数
            expected_return (float): 预期收益率
            reason (str): 拒绝交易的原因
            market_prediction (dict): 市场预测数据
        """
        try:
            logger.info(f"策略 {self.name} 收到低收益率事件:")
            logger.info(f"  预期收益率: {expected_return:.4f}")
            logger.info(f"  原因: {reason}")
            logger.info(f"  订单参数: {params}")
            
            # 打印市场预测数据
            if market_prediction:
                logger.info(f"  市场预测: {market_prediction}")
            
            # 基于低收益率事件和市场预测调整策略参数
            self._adjust_strategy_based_on_low_return(expected_return, params, market_prediction)
            
            # 记录低收益率事件
            self._log_execution(
                "low_return",
                "return_too_low",
                {
                    "expected_return": expected_return,
                    "reason": reason,
                    "params": params,
                    "market_prediction": market_prediction
                }
            )
            
        except Exception as e:
            logger.error(f"策略 {self.name} 处理低收益率事件失败: {e}")
    
    def _adjust_strategy_based_on_low_return(self, expected_return: float, params: dict, market_prediction: dict = None):
        """基于低收益率事件和市场预测调整策略参数
        
        Args:
            expected_return (float): 预期收益率
            params (dict): 订单参数
            market_prediction (dict): 市场预测数据
        """
        try:
            # 分析低收益率原因
            # 1. 调整阈值，提高交易标准
            if hasattr(self, 'current_threshold'):
                # 提高阈值，减少低收益率交易
                new_threshold = min(self.max_threshold, self.current_threshold * 1.1)
                if new_threshold > self.current_threshold:
                    self.current_threshold = new_threshold
                    logger.info(f"基于低收益率调整阈值: {self.current_threshold}")
            
            # 2. 调整信号强度计算参数
            if hasattr(self, 'dynamics_params'):
                # 增加市场耦合系数，提高信号强度
                if 'G_eff' in self.dynamics_params:
                    self.dynamics_params['G_eff'] = min(self.dynamics_params['G_eff'] * 1.2, 0.01)
                    logger.info(f"基于低收益率调整市场耦合系数: {self.dynamics_params['G_eff']}")
            
            # 3. 调整弹簧效应参数
            if hasattr(self, 'spring_params'):
                # 减少均值回归阈值，提高敏感度
                if 'mean_threshold' in self.spring_params:
                    self.spring_params['mean_threshold'] = max(self.spring_params['mean_threshold'] * 0.8, 0.001)
                    logger.info(f"基于低收益率调整均值回归阈值: {self.spring_params['mean_threshold']}")
            
            # 4. 根据市场预测调整策略参数
            if market_prediction:
                trend = market_prediction.get('trend', 'neutral')
                volatility = market_prediction.get('volatility', 0)
                momentum = market_prediction.get('momentum', 'neutral')
                
                # 根据市场趋势调整
                if trend == 'bullish':
                    # 牛市，降低阈值，增加交易频率
                    if hasattr(self, 'current_threshold'):
                        new_threshold = max(self.min_threshold, self.current_threshold * 0.9)
                        if new_threshold < self.current_threshold:
                            self.current_threshold = new_threshold
                            logger.info(f"基于牛市预测调整阈值: {self.current_threshold}")
                elif trend == 'bearish':
                    # 熊市，提高阈值，减少交易频率
                    if hasattr(self, 'current_threshold'):
                        new_threshold = min(self.max_threshold, self.current_threshold * 1.1)
                        if new_threshold > self.current_threshold:
                            self.current_threshold = new_threshold
                            logger.info(f"基于熊市预测调整阈值: {self.current_threshold}")
                
                # 根据市场波动率调整
                if volatility > 5:  # 高波动率
                    # 高波动率，提高阈值，减少交易频率
                    if hasattr(self, 'current_threshold'):
                        new_threshold = min(self.max_threshold, self.current_threshold * 1.15)
                        if new_threshold > self.current_threshold:
                            self.current_threshold = new_threshold
                            logger.info(f"基于高波动率调整阈值: {self.current_threshold}")
                elif volatility < 1:  # 低波动率
                    # 低波动率，降低阈值，增加交易频率
                    if hasattr(self, 'current_threshold'):
                        new_threshold = max(self.min_threshold, self.current_threshold * 0.85)
                        if new_threshold < self.current_threshold:
                            self.current_threshold = new_threshold
                            logger.info(f"基于低波动率调整阈值: {self.current_threshold}")
                
                # 根据市场动量调整
                if momentum == 'strong':
                    # 强动量，降低阈值，增加交易频率
                    if hasattr(self, 'current_threshold'):
                        new_threshold = max(self.min_threshold, self.current_threshold * 0.9)
                        if new_threshold < self.current_threshold:
                            self.current_threshold = new_threshold
                            logger.info(f"基于强市场动量调整阈值: {self.current_threshold}")
                elif momentum == 'weak':
                    # 弱动量，提高阈值，减少交易频率
                    if hasattr(self, 'current_threshold'):
                        new_threshold = min(self.max_threshold, self.current_threshold * 1.1)
                        if new_threshold > self.current_threshold:
                            self.current_threshold = new_threshold
                            logger.info(f"基于弱市场动量调整阈值: {self.current_threshold}")
            
        except Exception as e:
            logger.error(f"基于低收益率调整策略参数失败: {e}")
    
    async def on_risk_assessment(self, inst_id: str, prediction: dict, risk_level: str):
        """处理风险评估事件
        
        Args:
            inst_id (str): 产品ID
            prediction (dict): 市场预测结果
            risk_level (str): 风险等级
        """
        try:
            logger.info(f"策略 {self.name} 收到风险评估事件:")
            logger.info(f"  产品: {inst_id}")
            logger.info(f"  风险等级: {risk_level}")
            logger.info(f"  市场趋势: {prediction.get('trend')}")
            logger.info(f"  市场波动率: {prediction.get('volatility', 0):.2f}%")
            logger.info(f"  市场动量: {prediction.get('momentum')}")
            
            # 基于风险评估调整策略参数
            self._adjust_strategy_based_on_risk(risk_level, prediction)
            
            # 记录风险评估事件
            self._log_execution(
                "risk_assessment",
                "risk_level_updated",
                {
                    "inst_id": inst_id,
                    "risk_level": risk_level,
                    "prediction": prediction
                }
            )
            
        except Exception as e:
            logger.error(f"策略 {self.name} 处理风险评估事件失败: {e}")
    
    def _adjust_strategy_based_on_risk(self, risk_level: str, prediction: dict):
        """基于风险评估调整策略参数
        
        Args:
            risk_level (str): 风险等级
            prediction (dict): 市场预测结果
        """
        try:
            # 根据风险等级调整策略参数
            if hasattr(self, 'current_threshold'):
                if risk_level == "critical":
                    # 极高风险，大幅提高阈值，减少交易频率
                    new_threshold = min(self.max_threshold, self.current_threshold * 1.5)
                    if new_threshold > self.current_threshold:
                        self.current_threshold = new_threshold
                        logger.info(f"基于极高风险调整阈值: {self.current_threshold}")
                elif risk_level == "high":
                    # 高风险，提高阈值，减少交易频率
                    new_threshold = min(self.max_threshold, self.current_threshold * 1.2)
                    if new_threshold > self.current_threshold:
                        self.current_threshold = new_threshold
                        logger.info(f"基于高风险调整阈值: {self.current_threshold}")
                elif risk_level == "medium":
                    # 中等风险，适度提高阈值
                    new_threshold = min(self.max_threshold, self.current_threshold * 1.1)
                    if new_threshold > self.current_threshold:
                        self.current_threshold = new_threshold
                        logger.info(f"基于中等风险调整阈值: {self.current_threshold}")
                else:  # low
                    # 低风险，可以降低阈值，增加交易频率
                    new_threshold = max(self.min_threshold, self.current_threshold * 0.9)
                    if new_threshold < self.current_threshold:
                        self.current_threshold = new_threshold
                        logger.info(f"基于低风险调整阈值: {self.current_threshold}")
            
            # 根据市场趋势调整策略参数
            trend = prediction.get("trend", "neutral")
            if trend == "bearish":
                # 熊市，提高阈值，减少交易频率
                if hasattr(self, 'current_threshold'):
                    new_threshold = min(self.max_threshold, self.current_threshold * 1.1)
                    if new_threshold > self.current_threshold:
                        self.current_threshold = new_threshold
                        logger.info(f"基于熊市调整阈值: {self.current_threshold}")
            elif trend == "bullish":
                # 牛市，降低阈值，增加交易频率
                if hasattr(self, 'current_threshold'):
                    new_threshold = max(self.min_threshold, self.current_threshold * 0.9)
                    if new_threshold < self.current_threshold:
                        self.current_threshold = new_threshold
                        logger.info(f"基于牛市调整阈值: {self.current_threshold}")
            
        except Exception as e:
            logger.error(f"基于风险评估调整策略参数失败: {e}")

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
        
        # 保存到文件
        data_persistence.save_trade_logs(self.name, self.trade_logs)

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
        
        # 保存到文件
        data_persistence.save_execution_logs(self.name, self.execution_logs)

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
        # 清空文件中的数据
        data_persistence.save_trade_logs(self.name, self.trade_logs)
        data_persistence.save_execution_logs(self.name, self.execution_logs)
        logger.info(f"策略日志已清空: {self.name}")

    @property
    def is_running(self):
        """是否正在运行"""
        return self.status == "running"
