"""
策略回测模块 - 用于测试策略在历史数据上的表现
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
import pandas as pd
from datetime import datetime, timedelta

from core.api.okx_rest_client import OKXRESTClient
from strategies.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class StrategyBacktester:
    """
    策略回测器

    用于在历史数据上测试策略的表现
    """

    def __init__(self, rest_client: OKXRESTClient):
        """
        初始化回测器

        Args:
            rest_client: REST API客户端
        """
        self.rest_client = rest_client
        self.results = {}

    async def backtest_strategy(
        self,
        strategy: BaseStrategy,
        inst_id: str,
        start_time: datetime,
        end_time: datetime,
        bar: str = "1m",
        initial_balance: float = 10000,
    ) -> Dict[str, Any]:
        """
        回测策略

        Args:
            strategy: 要回测的策略实例
            inst_id: 产品ID
            start_time: 开始时间
            end_time: 结束时间
            bar: K线时间粒度
            initial_balance: 初始资金

        Returns:
            Dict[str, Any]: 回测结果
        """
        try:
            logger.info(f"开始回测策略 {strategy.__class__.__name__} 产品: {inst_id}")

            # 获取历史K线数据
            kline_data = await self._get_historical_data(
                inst_id, bar, start_time, end_time
            )
            if not kline_data:
                logger.error("获取历史数据失败")
                return {}

            # 转换为DataFrame
            df = self._convert_to_dataframe(kline_data)
            if df.empty:
                logger.error("数据转换失败")
                return {}

            # 初始化回测环境
            balance = initial_balance
            position = 0
            trades = []
            portfolio_value = []

            # 运行策略
            for i in range(len(df)):
                row = df.iloc[i]

                # 准备市场数据
                market_data = {
                    "inst_id": inst_id,
                    "price": row["close"],
                    "high": row["high"],
                    "low": row["low"],
                    "open": row["open"],
                    "volume": row["volume"],
                    "timestamp": row["timestamp"],
                }

                # 执行策略
                signal = strategy.execute(market_data)

                # 处理交易信号
                if signal:
                    trade = self._process_signal(signal, market_data, balance, position)
                    if trade:
                        trades.append(trade)
                        # 更新余额和持仓
                        if trade["side"] == "buy":
                            position += trade["quantity"]
                            balance -= trade["quantity"] * trade["price"]
                        elif trade["side"] == "sell":
                            position -= trade["quantity"]
                            balance += trade["quantity"] * trade["price"]

                # 记录资产价值
                current_value = balance + (position * row["close"])
                portfolio_value.append(current_value)

            # 计算回测结果
            result = self._calculate_results(trades, portfolio_value, initial_balance)
            result["strategy"] = strategy.__class__.__name__
            result["inst_id"] = inst_id
            result["start_time"] = start_time
            result["end_time"] = end_time
            result["bar"] = bar

            # 存储结果
            self.results[strategy.__class__.__name__] = result

            logger.info(
                f"回测完成，总收益: {result['total_profit']:.2f}，夏普比率: {result['sharpe_ratio']:.2f}"
            )

            return result

        except Exception as e:
            logger.error(f"回测失败: {e}")
            return {}

    async def _get_historical_data(
        self, inst_id: str, bar: str, start_time: datetime, end_time: datetime
    ) -> List[List]:
        """
        获取历史K线数据

        Args:
            inst_id: 产品ID
            bar: K线时间粒度
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            List[List]: K线数据
        """
        all_data = []
        current_time = start_time

        # 分批获取数据，每批最多1000条
        while current_time < end_time:
            next_time = current_time + timedelta(days=7)  # 每次获取7天的数据
            if next_time > end_time:
                next_time = end_time

            # 转换时间为Unix时间戳（毫秒）
            start_ts = int(current_time.timestamp() * 1000)
            end_ts = int(next_time.timestamp() * 1000)

            # 获取K线数据
            data = await self.rest_client.get_candles(
                inst_id=inst_id, bar=bar, limit=1000
            )

            if data:
                all_data.extend(data)

            current_time = next_time
            await asyncio.sleep(0.1)  # 避免API限流

        return all_data

    def _convert_to_dataframe(self, kline_data: List[List]) -> pd.DataFrame:
        """
        将K线数据转换为DataFrame

        Args:
            kline_data: K线数据

        Returns:
            pd.DataFrame: 转换后的数据
        """
        # OKX K线数据格式: [时间戳, 开盘价, 最高价, 最低价, 收盘价, 成交量, 成交金额]
        columns = ["timestamp", "open", "high", "low", "close", "volume", "amount"]
        data = []

        for kline in kline_data:
            if len(kline) >= 6:
                try:
                    timestamp = datetime.fromtimestamp(int(kline[0]) / 1000)
                    open_price = float(kline[1])
                    high_price = float(kline[2])
                    low_price = float(kline[3])
                    close_price = float(kline[4])
                    volume = float(kline[5])

                    data.append(
                        [
                            timestamp,
                            open_price,
                            high_price,
                            low_price,
                            close_price,
                            volume,
                        ]
                    )
                except (ValueError, IndexError) as e:
                    logger.warning(f"解析K线数据失败: {e}")

        df = pd.DataFrame(
            data, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df.sort_values("timestamp", inplace=True)
        df.reset_index(drop=True, inplace=True)

        return df

    def _process_signal(
        self,
        signal: Dict[str, Any],
        market_data: Dict[str, Any],
        balance: float,
        position: float,
    ) -> Optional[Dict[str, Any]]:
        """
        处理交易信号

        Args:
            signal: 交易信号
            market_data: 市场数据
            balance: 当前余额
            position: 当前持仓

        Returns:
            Optional[Dict[str, Any]]: 交易记录
        """
        side = signal.get("side")
        quantity = signal.get("quantity")
        price = market_data["price"]

        if not side or not quantity:
            return None

        # 检查余额是否足够
        if side == "buy":
            required_balance = quantity * price
            if required_balance > balance:
                logger.warning("余额不足，无法执行买入操作")
                return None
        elif side == "sell":
            if quantity > position:
                logger.warning("持仓不足，无法执行卖出操作")
                return None

        # 创建交易记录
        trade = {
            "timestamp": market_data["timestamp"],
            "side": side,
            "price": price,
            "quantity": quantity,
            "value": quantity * price,
        }

        return trade

    def _calculate_results(
        self,
        trades: List[Dict[str, Any]],
        portfolio_value: List[float],
        initial_balance: float,
    ) -> Dict[str, Any]:
        """
        计算回测结果

        Args:
            trades: 交易记录
            portfolio_value: 资产价值历史
            initial_balance: 初始资金

        Returns:
            Dict[str, Any]: 回测结果
        """
        if not portfolio_value:
            return {}

        # 计算总收益
        final_value = portfolio_value[-1]
        total_profit = final_value - initial_balance
        total_return = (total_profit / initial_balance) * 100

        # 计算胜率
        win_trades = 0
        for i in range(1, len(trades)):
            current_trade = trades[i]
            previous_trade = trades[i - 1]
            if current_trade["side"] != previous_trade["side"]:
                if (
                    current_trade["side"] == "sell"
                    and current_trade["price"] > previous_trade["price"]
                ):
                    win_trades += 1
                elif (
                    current_trade["side"] == "buy"
                    and current_trade["price"] < previous_trade["price"]
                ):
                    win_trades += 1

        win_rate = (win_trades / len(trades)) * 100 if trades else 0

        # 计算最大回撤
        max_drawdown = 0
        peak = portfolio_value[0]
        for value in portfolio_value:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # 计算夏普比率（假设无风险利率为0）
        returns = []
        for i in range(1, len(portfolio_value)):
            daily_return = (
                portfolio_value[i] - portfolio_value[i - 1]
            ) / portfolio_value[i - 1]
            returns.append(daily_return)

        if returns:
            avg_return = sum(returns) / len(returns)
            std_return = pd.Series(returns).std()
            sharpe_ratio = avg_return / std_return * (252**0.5) if std_return > 0 else 0
        else:
            sharpe_ratio = 0

        # 计算索提诺比率（只考虑下行风险）
        if returns:
            negative_returns = [r for r in returns if r < 0]
            if negative_returns:
                downside_std = pd.Series(negative_returns).std()
                sortino_ratio = (
                    avg_return / downside_std * (252**0.5) if downside_std > 0 else 0
                )
            else:
                sortino_ratio = float("inf")
        else:
            sortino_ratio = 0

        # 计算卡马比率（回报与最大回撤的比率）
        calmar_ratio = (
            (total_return / 100) / (max_drawdown / 100) if max_drawdown > 0 else 0
        )

        # 计算平均盈亏
        total_win = 0
        total_loss = 0
        win_count = 0
        loss_count = 0
        trade_profits = []

        for i in range(1, len(trades)):
            current_trade = trades[i]
            previous_trade = trades[i - 1]
            if current_trade["side"] != previous_trade["side"]:
                if current_trade["side"] == "sell":
                    profit = (
                        current_trade["price"] - previous_trade["price"]
                    ) * current_trade["quantity"]
                    trade_profits.append(profit)
                    if profit > 0:
                        total_win += profit
                        win_count += 1
                    else:
                        total_loss += profit
                        loss_count += 1

        avg_win = total_win / win_count if win_count > 0 else 0
        avg_loss = total_loss / loss_count if loss_count > 0 else 0

        # 计算盈亏比
        profit_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")

        # 计算最大连续盈利和亏损
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        current_wins = 0
        current_losses = 0

        for profit in trade_profits:
            if profit > 0:
                current_wins += 1
                current_losses = 0
                if current_wins > max_consecutive_wins:
                    max_consecutive_wins = current_wins
            else:
                current_losses += 1
                current_wins = 0
                if current_losses > max_consecutive_losses:
                    max_consecutive_losses = current_losses

        # 计算平均持仓时间
        avg_holding_period = 0
        if len(trades) >= 2:
            holding_periods = []
            for i in range(1, len(trades)):
                if trades[i]["side"] != trades[i - 1]["side"]:
                    start_time = trades[i - 1]["timestamp"]
                    end_time = trades[i]["timestamp"]
                    holding_period = (
                        end_time - start_time
                    ).total_seconds() / 60  # 转换为分钟
                    holding_periods.append(holding_period)
            if holding_periods:
                avg_holding_period = sum(holding_periods) / len(holding_periods)

        # 计算风险调整回报率
        risk_adjusted_return = total_return / max_drawdown if max_drawdown > 0 else 0

        return {
            "initial_balance": initial_balance,
            "final_balance": final_value,
            "total_profit": total_profit,
            "total_return": total_return,
            "win_rate": win_rate,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "calmar_ratio": calmar_ratio,
            "profit_loss_ratio": profit_loss_ratio,
            "max_consecutive_wins": max_consecutive_wins,
            "max_consecutive_losses": max_consecutive_losses,
            "avg_holding_period": avg_holding_period,
            "risk_adjusted_return": risk_adjusted_return,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "total_trades": len(trades),
            "win_trades": win_count,
            "loss_trades": loss_count,
        }

    def get_results(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有回测结果

        Returns:
            Dict[str, Dict[str, Any]]: 回测结果
        """
        return self.results

    def clear_results(self):
        """
        清空回测结果
        """
        self.results.clear()

    async def optimize_strategy_params(
        self,
        strategy_class,
        inst_id: str,
        start_time: datetime,
        end_time: datetime,
        param_ranges: Dict[str, List[float]],
        bar: str = "1m",
        initial_balance: float = 10000,
        optimization_metric: str = "sharpe_ratio",
    ) -> Dict[str, Any]:
        """
        优化策略参数

        Args:
            strategy_class: 策略类
            inst_id: 产品ID
            start_time: 开始时间
            end_time: 结束时间
            param_ranges: 参数范围字典，格式为 {param_name: [min, max, step]}
            bar: K线时间粒度
            initial_balance: 初始资金
            optimization_metric: 优化指标，可选值: 'sharpe_ratio', 'total_return', 'win_rate', 'max_drawdown'

        Returns:
            Dict[str, Any]: 最优参数和对应的回测结果
        """
        try:
            logger.info(f"开始优化策略参数: {strategy_class.__name__}")

            # 生成参数组合
            param_combinations = self._generate_param_combinations(param_ranges)
            logger.info(f"生成了 {len(param_combinations)} 个参数组合")

            # 存储每个参数组合的结果
            results = []

            # 测试每个参数组合
            for i, params in enumerate(param_combinations):
                logger.info(f"测试参数组合 {i+1}/{len(param_combinations)}: {params}")

                # 创建策略实例
                strategy = strategy_class(config=params)

                # 回测策略
                result = await self.backtest_strategy(
                    strategy=strategy,
                    inst_id=inst_id,
                    start_time=start_time,
                    end_time=end_time,
                    bar=bar,
                    initial_balance=initial_balance,
                )

                if result:
                    # 存储参数和结果
                    result["params"] = params
                    results.append(result)

                    logger.info(
                        f"参数组合结果: 夏普比率={result['sharpe_ratio']:.2f}, 总收益={result['total_return']:.2f}%"
                    )

                # 避免API限流
                await asyncio.sleep(0.1)

            if not results:
                logger.error("所有参数组合测试失败")
                return {}

            # 选择最优参数组合
            optimal_result = self._select_optimal_result(results, optimization_metric)

            logger.info(f"参数优化完成，最优参数: {optimal_result['params']}")
            logger.info(
                f"最优结果: 夏普比率={optimal_result['sharpe_ratio']:.2f}, 总收益={optimal_result['total_return']:.2f}%"
            )

            return optimal_result

        except Exception as e:
            logger.error(f"参数优化失败: {e}")
            return {}

    def _generate_param_combinations(
        self, param_ranges: Dict[str, List[float]]
    ) -> List[Dict[str, float]]:
        """
        生成参数组合

        Args:
            param_ranges: 参数范围字典，格式为 {param_name: [min, max, step]}

        Returns:
            List[Dict[str, float]]: 参数组合列表
        """
        import itertools

        # 生成每个参数的可能值
        param_values = {}
        for param_name, (min_val, max_val, step) in param_ranges.items():
            values = []
            current = min_val
            while current <= max_val:
                values.append(current)
                current += step
            param_values[param_name] = values

        # 生成所有参数组合
        param_names = list(param_values.keys())
        value_combinations = itertools.product(
            *(param_values[name] for name in param_names)
        )

        # 转换为字典列表
        combinations = []
        for values in value_combinations:
            param_dict = {}
            for name, value in zip(param_names, values):
                param_dict[name] = value
            combinations.append(param_dict)

        return combinations

    def _select_optimal_result(
        self, results: List[Dict[str, Any]], optimization_metric: str
    ) -> Dict[str, Any]:
        """
        选择最优结果

        Args:
            results: 回测结果列表
            optimization_metric: 优化指标

        Returns:
            Dict[str, Any]: 最优结果
        """
        if not results:
            return {}

        # 根据优化指标选择最优结果
        if optimization_metric == "sharpe_ratio":
            # 夏普比率越高越好
            optimal = max(results, key=lambda x: x.get("sharpe_ratio", 0))
        elif optimization_metric == "total_return":
            # 总收益越高越好
            optimal = max(results, key=lambda x: x.get("total_return", 0))
        elif optimization_metric == "win_rate":
            # 胜率越高越好
            optimal = max(results, key=lambda x: x.get("win_rate", 0))
        elif optimization_metric == "max_drawdown":
            # 最大回撤越小越好
            optimal = min(results, key=lambda x: x.get("max_drawdown", float("inf")))
        else:
            # 默认使用夏普比率
            optimal = max(results, key=lambda x: x.get("sharpe_ratio", 0))

        return optimal
