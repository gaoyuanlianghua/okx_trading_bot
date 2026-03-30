import logging
import time
from strategies.base_strategy import BaseStrategy

logger = logging.getLogger("Strategy")


class CombinedStrategy(BaseStrategy):
    """组合策略类 - 整合多个子策略的信号"""

    def __init__(self, api_client=None, config=None):
        """
        初始化组合策略

        Args:
            api_client: OKX API客户端实例
            config (dict): 策略配置，包含子策略列表和权重
        """
        super().__init__(api_client, config)

        # 子策略配置
        self.sub_strategies = []
        self.strategy_weights = {}

        # 信号历史
        self.signal_history = {}

        # 初始化子策略
        if config and "sub_strategies" in config:
            self._initialize_sub_strategies(config["sub_strategies"])

        logger.info("组合策略初始化完成")

    def _initialize_sub_strategies(self, sub_strategy_configs):
        """
        初始化子策略

        Args:
            sub_strategy_configs (list): 子策略配置列表
        """
        for config in sub_strategy_configs:
            try:
                strategy_name = config.get("name")
                strategy_class = config.get("class")
                strategy_config = config.get("config", {})
                weight = config.get("weight", 1.0)

                if not strategy_name or not strategy_class:
                    logger.warning("子策略配置缺少名称或类")
                    continue

                # 创建子策略实例
                strategy = strategy_class(
                    api_client=self.api_client, config=strategy_config
                )
                self.sub_strategies.append(strategy)
                self.strategy_weights[strategy_name] = weight
                self.signal_history[strategy_name] = []

                logger.info(f"子策略加载成功: {strategy_name}, 权重: {weight}")
            except Exception as e:
                logger.error(f"加载子策略失败: {e}")

    def _execute_strategy(self, market_data):
        """
        执行策略，整合子策略信号

        Args:
            market_data (dict): 市场数据

        Returns:
            dict: 组合交易信号
        """
        if not self.sub_strategies:
            logger.warning("组合策略没有配置子策略")
            # 返回中性信号
            return {
                "strategy": self.name,
                "side": "neutral",
                "price": market_data.get("price", 0),
                "signal_strength": 0,
                "timestamp": time.time(),
                "inst_id": market_data.get("inst_id", "BTC-USDT-SWAP"),
                "sub_signals": {}
            }

        # 收集子策略信号
        sub_signals = {}
        for strategy in self.sub_strategies:
            try:
                signal = strategy.execute(market_data)
                if signal:
                    strategy_name = strategy.name
                    sub_signals[strategy_name] = signal
                    self.signal_history[strategy_name].append(signal)
                    # 限制信号历史长度
                    if len(self.signal_history[strategy_name]) > 100:
                        self.signal_history[strategy_name] = self.signal_history[
                            strategy_name
                        ][-100:]
            except Exception as e:
                logger.error(f"执行子策略失败 {strategy.name}: {e}")

        # 计算组合信号
        combined_signal = self._combine_signals(sub_signals)

        if combined_signal:
            logger.info(f"组合策略信号: {combined_signal}")

        return combined_signal

    def _combine_signals(self, sub_signals):
        """
        组合子策略信号

        Args:
            sub_signals (dict): 子策略信号字典

        Returns:
            dict: 组合信号
        """
        if not sub_signals:
            # 返回中性信号
            return {
                "strategy": self.name,
                "side": "neutral",
                "price": 0,
                "signal_strength": 0,
                "timestamp": time.time(),
                "inst_id": "BTC-USDT-SWAP",
                "sub_signals": {}
            }

        # 计算信号强度加权和
        buy_strength = 0.0
        sell_strength = 0.0
        total_weight = 0.0

        for strategy_name, signal in sub_signals.items():
            weight = self.strategy_weights.get(strategy_name, 1.0)
            total_weight += weight

            # 计算信号强度
            if signal.get("side") == "buy":
                buy_strength += weight * (
                    signal.get("signal_strength", 1.0)
                    if "signal_strength" in signal
                    else 1.0
                )
            elif signal.get("side") == "sell":
                sell_strength += weight * (
                    signal.get("signal_strength", 1.0)
                    if "signal_strength" in signal
                    else 1.0
                )

        if total_weight == 0:
            # 返回中性信号
            return {
                "strategy": self.name,
                "side": "neutral",
                "price": sub_signals[next(iter(sub_signals))].get("price", 0) if sub_signals else 0,
                "signal_strength": 0,
                "timestamp": time.time(),
                "inst_id": sub_signals[next(iter(sub_signals))].get("inst_id", "BTC-USDT-SWAP") if sub_signals else "BTC-USDT-SWAP",
                "sub_signals": sub_signals,
            }

        # 归一化信号强度
        buy_strength /= total_weight
        sell_strength /= total_weight

        # 确定最终信号
        if buy_strength > sell_strength and buy_strength > 0.5:
            # 生成买入信号
            signal = {
                "strategy": self.name,
                "side": "buy",
                "price": sub_signals[next(iter(sub_signals))].get("price", 0),
                "signal_strength": buy_strength,
                "timestamp": time.time(),
                "inst_id": sub_signals[next(iter(sub_signals))].get(
                    "inst_id", "BTC-USDT-SWAP"
                ),
                "sub_signals": sub_signals,
            }
        elif sell_strength > buy_strength and sell_strength > 0.5:
            # 生成卖出信号
            signal = {
                "strategy": self.name,
                "side": "sell",
                "price": sub_signals[next(iter(sub_signals))].get("price", 0),
                "signal_strength": sell_strength,
                "timestamp": time.time(),
                "inst_id": sub_signals[next(iter(sub_signals))].get(
                    "inst_id", "BTC-USDT-SWAP"
                ),
                "sub_signals": sub_signals,
            }
        else:
            # 信号强度不足，返回中性信号
            return {
                "strategy": self.name,
                "side": "neutral",
                "price": sub_signals[next(iter(sub_signals))].get("price", 0),
                "signal_strength": max(buy_strength, sell_strength),
                "timestamp": time.time(),
                "inst_id": sub_signals[next(iter(sub_signals))].get("inst_id", "BTC-USDT-SWAP"),
                "sub_signals": sub_signals,
            }

        return signal

    def add_sub_strategy(self, strategy, weight=1.0):
        """
        添加子策略

        Args:
            strategy: 子策略实例
            weight (float): 策略权重
        """
        self.sub_strategies.append(strategy)
        self.strategy_weights[strategy.name] = weight
        self.signal_history[strategy.name] = []
        logger.info(f"添加子策略: {strategy.name}, 权重: {weight}")

    def remove_sub_strategy(self, strategy_name):
        """
        移除子策略

        Args:
            strategy_name (str): 策略名称
        """
        self.sub_strategies = [
            s for s in self.sub_strategies if s.name != strategy_name
        ]
        if strategy_name in self.strategy_weights:
            del self.strategy_weights[strategy_name]
        if strategy_name in self.signal_history:
            del self.signal_history[strategy_name]
        logger.info(f"移除子策略: {strategy_name}")

    def update_strategy_weight(self, strategy_name, weight):
        """
        更新策略权重

        Args:
            strategy_name (str): 策略名称
            weight (float): 新权重
        """
        if strategy_name in self.strategy_weights:
            self.strategy_weights[strategy_name] = weight
            logger.info(f"更新策略权重: {strategy_name} -> {weight}")

    def get_sub_strategy_status(self):
        """
        获取子策略状态

        Returns:
            dict: 子策略状态字典
        """
        status = {}
        for strategy in self.sub_strategies:
            status[strategy.name] = {
                "status": strategy.status,
                "performance": strategy.performance,
                "weight": self.strategy_weights.get(strategy.name, 1.0),
            }
        return status

    def start(self):
        """启动策略"""
        super().start()
        # 启动所有子策略
        for strategy in self.sub_strategies:
            strategy.start()
        logger.info("组合策略及子策略已启动")

    def stop(self):
        """停止策略"""
        super().stop()
        # 停止所有子策略
        for strategy in self.sub_strategies:
            strategy.stop()
        logger.info("组合策略及子策略已停止")

    def pause(self):
        """暂停策略"""
        super().pause()
        # 暂停所有子策略
        for strategy in self.sub_strategies:
            strategy.pause()
        logger.info("组合策略及子策略已暂停")

    def resume(self):
        """恢复策略"""
        super().resume()
        # 恢复所有子策略
        for strategy in self.sub_strategies:
            strategy.resume()
        logger.info("组合策略及子策略已恢复")
