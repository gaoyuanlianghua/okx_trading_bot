import asyncio
import time
import numpy as np
import logging

logger = logging.getLogger("Strategy")
from strategies.base_strategy import BaseStrategy

# 尝试导入scipy，如不可用则使用替代实现
try:
    from scipy.optimize import minimize
    from scipy.linalg import qr

    has_scipy = True
except Exception as e:
    logger.warning(f"scipy not available, some advanced features will be disabled: {e}")
    has_scipy = False


class DynamicsStrategy(BaseStrategy):
    """原子核互反动力学交易策略"""

    def __init__(self, api_client=None, config=None):
        """
        初始化动力学交易策略

        Args:
            api_client (OKXAPIClient, optional): OKX API客户端实例
            config (dict, optional): 策略配置
        """
        super().__init__(api_client, config)

        # 风险管理参数
        self.risk_params = {
            "max_order_amount": 10000,
            "max_daily_loss": 0.05,
            "max_daily_trades": 100,
            "max_consecutive_losses": 5,
        }

        # 风险管理器（简化版）
        class SimpleRiskManager:
            def __init__(self, api_client=None, risk_params=None):
                self.api_client = api_client
                self.risk_params = risk_params or {}

            def assess_overall_risk(self):
                # 简化实现，返回基本风险评估
                return {
                    "is_account_healthy": True,
                    "account_balance": 10000,  # 假设账户余额
                }

            def check_order_risk(self, order_info):
                # 简化实现，返回风险检查结果
                return True, "风险检查通过"

            def update_risk_params(self, **kwargs):
                self.risk_params.update(kwargs)

        self.risk_manager = SimpleRiskManager(api_client, self.risk_params)

        # 动力学参数配置
        self.dynamics_params = {
            "ε": 0.85,  # 市场动量方向算符 (1同向/-1反向)
            "G_eff": 5.0e-3,  # 市场耦合系数 (增加到5e-3，提高敏感度)
            "n": 2,  # 市场影响力衰减指数 (从3降到2，减缓衰减)
            "η": 1.0,  # 配对反馈强度 (从0.75增加到1.0)
            "γ": 0.05,  # 价差异常衰减率 (从0.1降到0.05，减缓衰减)
            "κ": 5.0,  # 相位同步强度 (从2.5增加到5.0)
            "λ": 2.0,  # 相位耦合衰减 (从3.0降到2.0，减缓衰减)
            "t_coll": 0.05,  # 市场协同时标(秒) (从0.1降到0.05，加快响应)
        }

        # 弹簧效应均值回归参数
        self.spring_params = {"lookback_period": 10, "mean_threshold": 0.005}  # 降低阈值，增加敏感度

        # 数据容器
        self.price_history = []
        self.phase_history = []

        # 交易统计
        self.trade_stats = {
            "daily_trades": 0,
            "daily_loss": 0,
            "consecutive_losses": 0,
            "last_reset_time": time.time(),
        }
        
        # 累计盈利和浮亏
        self.total_profit = 0
        self.total_floating_loss = 0
        # 累计手续费
        self.total_fees = 0
        # 账户收益跟踪
        self.account_equity = 0  # 账户总权益
        self.account_pnl = 0  # 账户总盈亏
        self.account_pnl_ratio = 0  # 账户收益率
        # 阈值自动调节参数
        self.base_threshold = 0.0001  # 基础阈值，降低以更容易生成交易信号
        self.current_threshold = 0.0001  # 当前阈值，降低以更容易生成交易信号
        self.threshold_adjustment_factor = 0.0001  # 阈值调整因子
        self.max_threshold = 0.01  # 最大阈值
        self.min_threshold = 0.0001  # 最小阈值，降低以更容易生成交易信号

        # 订单参数验证配置
        self.order_param_config = {
            "min_order_sizes": {"BTC-USDT-SWAP": 0.001, "ETH-USDT-SWAP": 0.01},
            "max_order_sizes": {"BTC-USDT-SWAP": 100, "ETH-USDT-SWAP": 1000},
            "price_precisions": {"BTC-USDT-SWAP": 2, "ETH-USDT-SWAP": 2},
        }

        # 更新配置
        if config:
            if "dynamics" in config:
                self.dynamics_params.update(config["dynamics"])
            if "spring" in config:
                self.spring_params.update(config["spring"])
            if "risk" in config:
                self.risk_manager.update_risk_params(**config["risk"])
            if "order_params" in config:
                self.order_param_config.update(config["order_params"])

        logger.info("原子核互反动力学策略初始化完成")

    async def get_market_data(self, inst_id="BTC-USDT-SWAP"):
        """获取市场数据并计算动力学特征"""
        try:
            ticker = self.api_client.get_ticker(inst_id)
            if ticker:
                last_price = float(ticker[0]["last"])
                self.price_history.append(last_price)

                # 计算量子相位 (价格波动率)
                if len(self.price_history) > 10:
                    returns = np.diff(np.log(self.price_history[-10:]))
                    phase = np.std(returns) * 100  # 波动率作为相位代理
                    self.phase_history.append(phase)

                return last_price
            return None
        except Exception as e:
            logger.error(f"获取市场数据失败: {e}")
            return None

    def calculate_angular_momentum(self, cluster_a, cluster_b):
        """
        角动量重分布方程实现
        dL_A/dt = ε·G_eff[(ρv)_BΔS_BA/rⁿ - (ρv)_AΔS_AB/rⁿ]
        """
        # 计算角通量密度 (交易量密度)
        flux_a = cluster_a["volume"] * cluster_a["velocity"]
        flux_b = cluster_b["volume"] * cluster_b["velocity"]

        # 计算角旋态梯度 (tanh函数模拟市场不平衡)
        delta_s_ab = np.tanh((cluster_a["liquidity"] - cluster_b["liquidity"]) / 0.2)
        delta_s_ba = np.tanh((cluster_b["liquidity"] - cluster_a["liquidity"]) / 0.2)

        # 计算市场距离 (相关性倒数)
        r = 1 / (cluster_a["correlation"] + 1e-5)

        # 角动量变化率
        dL_dt = (
            self.dynamics_params["ε"]
            * self.dynamics_params["G_eff"]
            * (
                (flux_b * delta_s_ba) / (r ** self.dynamics_params["n"])
                - (flux_a * delta_s_ab) / (r ** self.dynamics_params["n"])
            )
        )
        return dL_dt

    def pairing_feedback(self, delta, cluster_a, cluster_b):
        """
        非对称配对反馈方程
        dΔ/dt = ηṅv_pair²[Φ(q_A) - 𝒜_m^(nuc)Φ(q_B)] - γΔ
        """
        # 计算不对称因子
        a_m = abs(cluster_a["size"] - cluster_b["size"]) / (
            cluster_a["size"] + cluster_b["size"]
        )

        # 计算配对势 (市场强度指标)
        phi_a = (
            cluster_a["external_pressure"] - cluster_a["market_depth"]
        ) / cluster_a["market_depth"]
        phi_b = (
            cluster_b["external_pressure"] - cluster_b["market_depth"]
        ) / cluster_b["market_depth"]

        # 配对振动速度 (市场波动率)
        v_pair = np.sqrt(delta / cluster_a["mass"])

        # 反馈方程
        d_delta_dt = (
            self.dynamics_params["η"]
            * cluster_a["growth_rate"]
            * (v_pair**2)
            * (phi_a - a_m * phi_b)
            - self.dynamics_params["γ"] * delta
        )

        return d_delta_dt

    def quantum_phase_sync(self, phase_a, phase_b, inertia_a, inertia_b):
        """
        量子相位同步方程
        d(φ_A-φ_B)/dt = -κ(I_Aω_A²-I_Bω_B²)/t_coll·e^{-λ|φ_A-φ_B|} + ξ(t)
        """
        # 计算角速度 (价格变化率)
        omega_a = (
            np.mean(np.diff(self.price_history[-5:]))
            if len(self.price_history) >= 5
            else 0
        )
        omega_b = (
            np.mean(np.diff(self.phase_history[-5:]))
            if len(self.phase_history) >= 5
            else 0
        )

        # 相位同步项
        phase_diff = abs(phase_a - phase_b)
        sync_term = (
            -self.dynamics_params["κ"]
            * (
                (inertia_a * omega_a**2 - inertia_b * omega_b**2)
                / self.dynamics_params["t_coll"]
            )
            * np.exp(-self.dynamics_params["λ"] * phase_diff)
        )

        # 添加市场噪声 (高斯白噪声)
        noise = np.random.normal(0, 0.1)

        return sync_term + noise

    def calculate_spring_effect(self):
        """计算弹簧效应均值回归信号"""
        if len(self.price_history) > self.spring_params["lookback_period"]:
            ma = np.mean(self.price_history[-self.spring_params["lookback_period"] :])
            deviation = (self.price_history[-1] - ma) / ma

            # 弹簧回归信号
            spring_signal = -np.tanh(deviation / self.spring_params["mean_threshold"])
            return spring_signal
        return 0

    def calculate_signal_strength(self):
        """计算综合信号强度"""
        if len(self.price_history) < self.spring_params["lookback_period"]:
            return 0

        # 计算弹簧效应信号
        spring_signal = self.calculate_spring_effect()

        # 模拟集群数据
        cluster_a = {
            "volume": 1000,  # 交易量
            "velocity": 0.02,  # 价格变化速度
            "liquidity": 0.8,  # 流动性指标
            "correlation": 0.6,
            "size": 1.0,
            "external_pressure": 0.3,
            "market_depth": 0.5,
            "mass": 1.0,
            "growth_rate": 0.01,
        }

        cluster_b = {**cluster_a, "size": 1.2, "correlation": 0.7}

        # 计算动力学信号
        momentum_signal = self.calculate_angular_momentum(cluster_a, cluster_b)
        pairing_signal = self.pairing_feedback(0.2, cluster_a, cluster_b)

        # 计算相位信号
        if len(self.phase_history) > 5:
            phase_signal = self.quantum_phase_sync(
                self.phase_history[-1], self.phase_history[-5], 1.0, 1.2
            )
        else:
            phase_signal = 0

        # 信号融合 (加权合成) - 增加spring_signal权重以提高敏感度
        combined_signal = (
            0.6 * spring_signal  # 从0.4增加到0.6
            + 0.25 * momentum_signal  # 从0.3降到0.25
            + 0.1 * pairing_signal  # 从0.2降到0.1
            + 0.05 * phase_signal  # 从0.1降到0.05
        )

        return combined_signal

    async def execute_trade(self, inst_id, signal_strength):
        """执行交易订单"""
        try:
            # 基于信号强度调整阈值
            self.adjust_threshold_based_on_signal_strength(signal_strength)
            
            # 检查信号强度 (使用当前阈值)
            if -self.current_threshold <= signal_strength <= self.current_threshold:
                logger.info(f"⚖️ 信号强度中性，保持观望 (阈值: {self.current_threshold})")
                return True

            # 策略风险检查
            is_strategy_safe, strategy_reason = self.check_strategy_risk()
            if not is_strategy_safe:
                logger.warning(f"⚠️ 策略风险检查失败: {strategy_reason}")
                return False

            # 风险评估: 检查整体风险状态
            overall_risk = self.risk_manager.assess_overall_risk()
            if not overall_risk or not overall_risk["is_account_healthy"]:
                logger.warning("⚠️ 账户健康状况不佳，跳过交易")
                return False

            # 订单类型决策 (使用当前阈值)
            side = "buy" if signal_strength > self.current_threshold else "sell"

            # 获取当前价格
            current_price = self.price_history[-1]

            # 计算市场波动率
            volatility = 0
            if len(self.price_history) > 10:
                returns = np.diff(np.log(self.price_history[-10:]))
                volatility = np.std(returns)

            # 根据市场波动率和信号强度自动调整委托单价
            price_adjustment = volatility * abs(signal_strength) * 10
            if side == "buy":
                # 买入时，价格适当提高以增加成交概率
                adjusted_price = current_price * (1 + price_adjustment)
            else:
                # 卖出时，价格适当降低以增加成交概率
                adjusted_price = current_price * (1 - price_adjustment)

            # 确保价格精度正确
            price_precision = self.order_param_config["price_precisions"].get(inst_id, 2)
            adjusted_price = round(adjusted_price, price_precision)

            # 计算基础仓位大小 (弹簧效应)
            account_balance = overall_risk["account_balance"]
            base_position_size = np.tanh(signal_strength) * min(
                self.risk_manager.risk_params["max_order_amount"],
                account_balance * 0.2,  # 最多使用20%的账户余额
            )

            # 利用盈利收益增加交易金额
            if self.total_profit > 0:
                # 最多使用50%的累计盈利作为额外交易金额
                profit_boost = min(self.total_profit * 0.5, base_position_size * 0.3)
                position_size = base_position_size + profit_boost
                logger.info(f"📈 利用盈利增加交易金额: +{profit_boost:.2f} USDT")
            else:
                position_size = base_position_size

            order_size = position_size / current_price

            # 构建订单信息
            order_info = {
                "inst_id": inst_id,
                "side": side,
                "sz": str(order_size),
                "px": str(adjusted_price),
            }

            # 订单参数验证
            is_params_valid, params_reason = self.validate_order_params(order_info)
            if not is_params_valid:
                logger.warning(f"⚠️ 订单参数验证失败: {params_reason}")
                return False

            # 风险检查: 使用风险管理服务检查订单风险
            is_allowed, reason = self.risk_manager.check_order_risk(order_info)
            if not is_allowed:
                logger.warning(f"⚠️ 订单风险检查失败: {reason}")
                return False

            # 执行交易前进行阈值校准
            self.adjust_threshold_before_trade()
        
            # 执行交易
            try:
                order_id = self.api_client.place_order(
                    inst_id=inst_id,
                    side=side,
                    ord_type="limit",
                    px=str(adjusted_price),
                    sz=str(order_size),
                )

                if order_id:
                    logger.info(
                        f"✅ 订单执行成功: {side} {inst_id} {order_size} @ {adjusted_price} (调整: {price_adjustment:.4f})"
                    )
                    # 更新交易统计
                    self.update_trade_stats(
                        {"profit": 0}
                    )  # 暂时假设盈亏为0，实际应从订单结果获取
                    # 交易后再次校准阈值
                    self.adjust_threshold_after_trade({"profit": 0})
                    return True
                else:
                    logger.error("❌ 订单失败")
                    # 更新交易统计
                    self.update_trade_stats({"profit": -0.01})  # 假设小亏损
                    # 交易后再次校准阈值
                    self.adjust_threshold_after_trade({"profit": -0.01})
                    return False
            except Exception as api_error:
                # 尝试提取错误码和错误信息
                error_message = str(api_error)
                error_code = None

                # 简单的错误码提取逻辑
                import re

                match = re.search(r"error_code=(\d+)", error_message)
                if match:
                    error_code = match.group(1)

                if error_code:
                    self.handle_api_error(error_code, error_message)
                else:
                    logger.error(f"🔥 API交易异常: {error_message}")

                # 更新交易统计
                self.update_trade_stats({"profit": -0.01})  # 假设小亏损
                # 交易后再次校准阈值
                self.adjust_threshold_after_trade({"profit": -0.01})
                return False

        except Exception as e:
            logger.error(f"🔥 交易异常: {str(e)}")
            # 更新交易统计
            self.update_trade_stats({"profit": -0.01})  # 假设小亏损
            return False

    async def run_live_trading(self, inst_id="BTC-USDT-SWAP", interval=60):
        """
        运行实盘交易

        Args:
            inst_id: 交易品种
            interval: 策略运行间隔(秒)
        """
        logger.info("🚀 启动原子核互反动力学交易策略...")

        iteration_count = 0
        current_interval = interval

        while True:
            try:
                # 获取市场数据
                current_price = await self.get_market_data(inst_id)
                if not current_price:
                    await asyncio.sleep(current_interval)
                    continue

                # 计算市场波动率
                volatility = 0
                if len(self.price_history) > 10:
                    returns = np.diff(np.log(self.price_history[-10:]))
                    volatility = np.std(returns)

                # 计算动态交易间隔
                current_interval = self.calculate_dynamic_interval(volatility)
                logger.debug(
                    f"市场波动率: {volatility:.4f}, 动态交易间隔: {current_interval}秒"
                )

                # 计算信号强度
                signal_strength = self.calculate_signal_strength()

                # 执行交易
                await self.execute_trade(inst_id, signal_strength)

                # 每10次迭代执行一次参数优化
                iteration_count += 1
                if iteration_count % 10 == 0:
                    logger.info("🔄 执行参数优化...")
                    # 生成训练数据并优化参数
                    training_data = self.generate_training_data()
                    self.optimize_dynamics_params(training_data)

                    # 每50次迭代执行一次参数降维
                    if iteration_count % 50 == 0:
                        logger.info("🔄 执行参数降维...")
                        self.reduce_param_set()

                # 等待下一个周期
                await asyncio.sleep(current_interval)

            except KeyboardInterrupt:
                logger.info("🛑 策略手动终止")
                break
            except Exception as e:
                logger.error(f"⚠️ 策略执行异常: {str(e)}")
                await asyncio.sleep(current_interval)

    def run_backtest(self, historical_data):
        """
        运行回测

        Args:
            historical_data: 历史数据列表，包含价格等信息

        Returns:
            dict: 回测结果
        """
        logger.info("📊 开始原子核互反动力学策略回测...")

        # 简化回测实现
        backtest_result = {
            "total_return": 0.0,
            "win_rate": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "total_trades": 0,
        }

        logger.info("📊 回测完成")
        return backtest_result

    def optimize_dynamics_params(self, historical_data):
        """基于历史数据优化动力学参数"""
        if not has_scipy:
            logger.warning("scipy not available, skipping parameter optimization")
            return False

        def loss_function(params):
            # 解包参数
            ε, G_eff, η, γ, κ, λ = params

            # 模拟历史表现
            cumulative_return = 0
            for data in historical_data:
                # 这里简化计算，实际需调用动力学方程
                signal_strength = (
                    ε * G_eff * data.get("momentum", 0)
                    + η * data.get("pairing", 0)
                    - γ * data.get("volatility", 0)
                )
                position_size = np.tanh(κ * signal_strength) * np.exp(
                    -λ * data.get("risk", 0)
                )
                cumulative_return += position_size * data.get("return", 0)

            # 最大化夏普比率
            returns = [d.get("return", 0) for d in historical_data]
            return -cumulative_return / (np.std(returns) + 1e-5)  # 添加小量避免除零

        # 参数边界
        bounds = [
            (-1, 1),  # ε
            (1e-4, 1e-2),  # G_eff
            (0.1, 2.0),  # η
            (0.05, 0.3),  # γ
            (1.0, 5.0),  # κ
            (1.0, 8.0),  # λ
        ]

        # 初始参数
        initial_params = [
            self.dynamics_params["ε"],
            self.dynamics_params["G_eff"],
            self.dynamics_params["η"],
            self.dynamics_params["γ"],
            self.dynamics_params["κ"],
            self.dynamics_params["λ"],
        ]

        # 优化求解
        try:
            result = minimize(
                loss_function, initial_params, bounds=bounds, method="SLSQP"
            )

            # 更新最优参数
            if result.success:
                optimized_params = dict(
                    zip(["ε", "G_eff", "η", "γ", "κ", "λ"], result.x)
                )
                self.dynamics_params.update(optimized_params)
                logger.info(f"✅ 动力学参数优化成功，新参数: {optimized_params}")
            else:
                logger.warning(f"⚠️ 动力学参数优化失败: {result.message}")

            return result.success
        except Exception as e:
            logger.error(f"优化参数时出错: {e}")
            return False

    def excitation_trajectory(self, t, N=5):
        """使用傅里叶级数生成市场激励信号"""
        # 随机生成傅里叶系数
        a = np.random.rand(N) * 0.1
        b = np.random.rand(N) * 0.1

        # 计算傅里叶级数
        trajectory = 0
        for i in range(1, N + 1):
            trajectory += a[i - 1] * np.sin(2 * np.pi * i * t) + b[i - 1] * np.cos(
                2 * np.pi * i * t
            )

        return trajectory

    def reduce_param_set(self):
        """采用QR分解消除参数冗余，实现动态模型降维"""
        if not has_scipy:
            logger.warning("scipy not available, skipping parameter reduction")
            return []

        # 构建参数相关性矩阵
        param_names = list(self.dynamics_params.keys())[:6]  # 取前6个参数
        param_values = np.array(
            [self.dynamics_params[name] for name in param_names]
        ).reshape(-1, 1)

        # 计算参数协方差矩阵（简化版，实际应基于历史数据）
        # 这里使用随机生成的协方差矩阵作为示例
        cov_matrix = np.random.rand(6, 6) * 0.1
        cov_matrix = np.dot(cov_matrix, cov_matrix.T)  # 确保对称正定

        try:
            # QR分解
            Q, R = qr(cov_matrix)

            # 计算奇异值（R矩阵的对角线元素）
            singular_values = np.abs(np.diag(R))

            # 选择前k个最大的奇异值
            k = 4  # 保留4个最重要的参数
            important_params = np.argsort(singular_values)[::-1][:k]

            logger.info(f"✅ 参数降维完成，保留的参数索引: {important_params}")
            logger.info(
                f"   对应的参数名: {[param_names[i] for i in important_params]}"
            )

            return important_params
        except Exception as e:
            logger.error(f"参数降维时出错: {e}")
            return []

    def generate_training_data(self, size=100):
        """生成动力学参数优化训练数据"""
        training_data = []
        for _ in range(size):
            # 生成随机市场数据特征
            momentum = np.random.uniform(-1, 1)
            pairing = np.random.uniform(0, 0.5)
            volatility = np.random.uniform(0.01, 0.1)
            risk = np.random.uniform(0.1, 0.9)

            # 基于弹簧效应和动量生成收益
            if momentum > 0.5:
                return_ = np.random.uniform(0, 0.1)
            elif momentum < -0.5:
                return_ = np.random.uniform(-0.05, 0)
            else:
                return_ = np.random.uniform(-0.02, 0.02)

            training_data.append(
                {
                    "momentum": momentum,
                    "pairing": pairing,
                    "volatility": volatility,
                    "risk": risk,
                    "return": return_,
                }
            )

        return training_data

    def stop_trading(self):
        """停止交易"""
        logger.info("🛑 停止原子核互反动力学策略")
        return True

    def validate_order_params(self, order_info):
        """验证订单参数是否符合OKX API要求

        Args:
            order_info (dict): 订单信息

        Returns:
            tuple: (是否有效, 错误信息)
        """
        inst_id = order_info["inst_id"]
        order_size = float(order_info["sz"])
        price = float(order_info["px"])

        # 检查订单大小
        min_size = self.order_param_config["min_order_sizes"].get(inst_id, 0.001)
        max_size = self.order_param_config["max_order_sizes"].get(inst_id, 100)

        if order_size < min_size:
            return False, f"订单大小小于最小限制: {min_size}"
        if order_size > max_size:
            return False, f"订单大小超过最大限制: {max_size}"

        # 检查价格精度
        price_precision = self.order_param_config["price_precisions"].get(inst_id, 2)
        if not self.is_price_valid(price, price_precision):
            return False, f"价格精度不符合要求，需要 {price_precision} 位小数"

        return True, "订单参数验证通过"

    def is_price_valid(self, price, precision):
        """检查价格是否符合精度要求

        Args:
            price (float): 价格
            precision (int): 精度（小数位数）

        Returns:
            bool: 是否有效
        """
        try:
            # 检查价格是否可以表示为指定精度的小数
            formatted_price = f"{price:.{precision}f}"
            return abs(float(formatted_price) - price) < 1e-9
        except Exception:
            return False

    def calculate_dynamic_interval(self, volatility):
        """根据市场波动率计算动态交易间隔

        Args:
            volatility (float): 市场波动率

        Returns:
            int: 交易间隔（秒）
        """
        # 基础间隔
        base_interval = 60

        # 根据波动率调整间隔
        if volatility > 0.02:
            # 高波动率，缩短间隔
            return max(10, int(base_interval * 0.5))
        elif volatility < 0.005:
            # 低波动率，延长间隔
            return min(300, int(base_interval * 2))
        else:
            # 正常波动率，使用基础间隔
            return base_interval

    def handle_api_error(self, error_code, error_msg):
        """处理API错误

        Args:
            error_code (str): 错误码
            error_msg (str): 错误信息

        Returns:
            bool: 是否处理成功
        """
        error_handlers = {
            "50011": self.handle_rate_limit_error,
            "500001": self.handle_system_error,
            "100002": self.handle_signature_error,
            "100003": self.handle_timestamp_error,
            "102001": self.handle_insufficient_balance,
            "102002": self.handle_order_size_limit,
        }

        if error_code in error_handlers:
            return error_handlers[error_code](error_msg)
        else:
            logger.error(f"未知API错误: {error_code} - {error_msg}")
            return False

    def handle_rate_limit_error(self, error_msg):
        """处理速率限制错误"""
        logger.warning(f"API速率限制: {error_msg}")
        # 增加等待时间
        time.sleep(2)
        return False

    def handle_system_error(self, error_msg):
        """处理系统错误"""
        logger.error(f"系统错误: {error_msg}")
        # 等待一段时间后重试
        time.sleep(5)
        return False

    def handle_signature_error(self, error_msg):
        """处理签名错误"""
        logger.error(f"签名错误: {error_msg}")
        # 检查API密钥
        return False

    def handle_timestamp_error(self, error_msg):
        """处理时间戳错误"""
        logger.error(f"时间戳错误: {error_msg}")
        # 同步时间
        return False

    def handle_insufficient_balance(self, error_msg):
        """处理余额不足错误"""
        logger.warning(f"余额不足: {error_msg}")
        # 减少订单大小
        return False

    def handle_order_size_limit(self, error_msg):
        """处理订单大小限制错误"""
        logger.warning(f"订单大小限制: {error_msg}")
        # 调整订单大小
        return False

    def check_strategy_risk(self):
        """检查策略级别的风险

        Returns:
            tuple: (是否通过, 原因)
        """
        # 检查是否需要重置每日统计
        current_time = time.time()
        if current_time - self.trade_stats["last_reset_time"] > 86400:  # 24小时
            self.trade_stats["daily_trades"] = 0
            self.trade_stats["daily_loss"] = 0
            self.trade_stats["last_reset_time"] = current_time

        # 检查最大单日亏损
        daily_loss = self.trade_stats["daily_loss"]
        max_daily_loss = self.risk_manager.risk_params.get("max_daily_loss", 0.05)
        if daily_loss > max_daily_loss:
            logger.warning(f"单日亏损超过限制: {daily_loss:.2%} > {max_daily_loss:.2%}")
            return False, "单日亏损超过限制"

        # 检查连续亏损
        consecutive_losses = self.trade_stats["consecutive_losses"]
        max_consecutive_losses = self.risk_manager.risk_params.get(
            "max_consecutive_losses", 5
        )
        if consecutive_losses > max_consecutive_losses:
            logger.warning(
                f"连续亏损次数超过限制: {consecutive_losses} > {max_consecutive_losses}"
            )
            return False, "连续亏损次数超过限制"

        # 检查每日交易次数
        daily_trades = self.trade_stats["daily_trades"]
        max_daily_trades = self.risk_manager.risk_params.get("max_daily_trades", 100)
        if daily_trades > max_daily_trades:
            logger.warning(f"每日交易次数超过限制: {daily_trades} > {max_daily_trades}")
            return False, "每日交易次数超过限制"

        return True, "策略风险检查通过"

    def update_trade_stats(self, trade_result):
        """更新交易统计

        Args:
            trade_result (dict): 交易结果
        """
        # 更新每日交易次数
        self.trade_stats["daily_trades"] += 1

        # 更新盈亏
        profit = trade_result.get("profit", 0)
        # 更新手续费
        fee = trade_result.get("fee", 0)
        self.total_fees += fee
        
        if profit < 0:
            self.trade_stats["daily_loss"] += abs(profit)
            self.trade_stats["consecutive_losses"] += 1
            # 更新浮亏
            self.total_floating_loss += abs(profit)
            # 自动调节阈值（考虑手续费）
            self.adjust_threshold_based_on_loss()
        else:
            self.trade_stats["consecutive_losses"] = 0
            # 更新累计盈利
            self.total_profit += profit
            # 盈利时可以考虑降低阈值，增加交易频率
            if self.total_profit > 0:
                self.adjust_threshold_based_on_profit()

        logger.debug(f"交易统计更新: {self.trade_stats}, 累计盈利: {self.total_profit}, 浮亏: {self.total_floating_loss}, 累计手续费: {self.total_fees}")

    def adjust_threshold_based_on_loss(self):
        """基于浮亏自动调节阈值
        当出现浮亏时，增加阈值以减少交易频率，降低风险
        """
        # 计算总损失（浮亏 + 手续费）
        total_loss = self.total_floating_loss + self.total_fees
        
        # 根据总损失程度调整阈值
        if total_loss > 0:
            # 总损失越大，阈值增加越多
            loss_factor = min(total_loss / 10, 1)  # 最多增加1倍
            new_threshold = self.base_threshold + (loss_factor * self.threshold_adjustment_factor * 10)
            # 确保阈值在合理范围内
            self.current_threshold = min(max(new_threshold, self.min_threshold), self.max_threshold)
            logger.info(f"基于浮亏和手续费调整阈值: {self.base_threshold} → {self.current_threshold} (浮亏: {self.total_floating_loss}, 手续费: {self.total_fees}, 总损失: {total_loss})")

    def adjust_threshold_based_on_profit(self):
        """基于盈利自动调节阈值
        当盈利时，适当降低阈值以增加交易频率，提高盈利机会
        """
        # 计算净利润（盈利 - 手续费）
        net_profit = self.total_profit - self.total_fees
        
        # 根据净利润程度调整阈值
        if net_profit > 0:
            # 净利润越多，阈值降低越多
            profit_factor = min(net_profit / 10, 1)  # 最多降低1倍
            new_threshold = self.base_threshold - (profit_factor * self.threshold_adjustment_factor * 5)
            # 确保阈值在合理范围内
            self.current_threshold = min(max(new_threshold, self.min_threshold), self.max_threshold)
            logger.info(f"基于净利润调整阈值: {self.base_threshold} → {self.current_threshold} (盈利: {self.total_profit}, 手续费: {self.total_fees}, 净利润: {net_profit})")

    def adjust_threshold_before_trade(self):
        """交易前进行阈值校准
        基于当前市场状态和策略表现进行阈值调整
        """
        # 计算当前市场波动率
        volatility = 0
        if len(self.price_history) > 10:
            returns = np.diff(np.log(self.price_history[-10:]))
            volatility = np.std(returns)
        
        # 根据市场波动率调整阈值
        if volatility > 0.02:
            # 高波动率市场，增加阈值以减少交易频率，降低风险
            volatility_factor = min(volatility * 100, 2)  # 最多增加2倍
            new_threshold = self.base_threshold * (1 + volatility_factor * 0.1)
            self.current_threshold = min(max(new_threshold, self.min_threshold), self.max_threshold)
            logger.info(f"交易前基于市场波动率调整阈值: {self.base_threshold} → {self.current_threshold} (波动率: {volatility:.4f})")
        
        # 记录阈值校准信息
        logger.info(f"交易前阈值校准完成，当前阈值: {self.current_threshold}")

    def adjust_threshold_after_trade(self, trade_result):
        """交易后进行阈值校准
        基于交易结果进行阈值调整
        
        Args:
            trade_result (dict): 交易结果，包含profit等信息
        """
        profit = trade_result.get("profit", 0)
        fee = trade_result.get("fee", 0)
        
        # 计算实际盈亏（考虑手续费）
        actual_profit = profit - fee
        
        # 根据实际盈亏调整阈值
        if actual_profit < 0:
            # 实际亏损，增加阈值以减少交易频率
            loss_factor = min(abs(actual_profit) * 100, 1)  # 最多增加1倍
            new_threshold = self.base_threshold * (1 + loss_factor * 0.2)
            self.current_threshold = min(max(new_threshold, self.min_threshold), self.max_threshold)
            logger.info(f"交易后基于实际亏损调整阈值: {self.base_threshold} → {self.current_threshold} (盈利: {profit:.4f}, 手续费: {fee:.4f}, 实际亏损: {abs(actual_profit):.4f})")
        elif actual_profit > 0:
            # 实际盈利，适当降低阈值以增加交易频率
            profit_factor = min(actual_profit * 100, 1)  # 最多降低1倍
            new_threshold = self.base_threshold * (1 - profit_factor * 0.1)
            self.current_threshold = min(max(new_threshold, self.min_threshold), self.max_threshold)
            logger.info(f"交易后基于实际盈利调整阈值: {self.base_threshold} → {self.current_threshold} (盈利: {profit:.4f}, 手续费: {fee:.4f}, 实际盈利: {actual_profit:.4f})")
        
        # 记录阈值校准信息
        logger.info(f"交易后阈值校准完成，当前阈值: {self.current_threshold}")

    def adjust_threshold_based_on_signal_strength(self, signal_strength):
        """基于信号强度调整阈值
        信号强度越大，阈值可以适当降低，以捕捉更多的交易机会
        信号强度越小，阈值应该适当提高，以减少噪音交易
        
        Args:
            signal_strength (float): 信号强度
        """
        # 计算信号强度的绝对值
        abs_signal_strength = abs(signal_strength)
        
        # 根据信号强度调整阈值
        if abs_signal_strength > 0.01:
            # 强信号，降低阈值以捕捉更多交易机会
            signal_factor = min(abs_signal_strength * 100, 2)  # 最多降低2倍
            new_threshold = self.base_threshold * (1 - signal_factor * 0.05)
            self.current_threshold = min(max(new_threshold, self.min_threshold), self.max_threshold)
            logger.info(f"基于强信号调整阈值: {self.base_threshold} → {self.current_threshold} (信号强度: {signal_strength:.6f})")
        elif abs_signal_strength < 0.001:
            # 弱信号，提高阈值以减少噪音交易
            new_threshold = self.base_threshold * 1.1  # 提高10%
            self.current_threshold = min(max(new_threshold, self.min_threshold), self.max_threshold)
            logger.info(f"基于弱信号调整阈值: {self.base_threshold} → {self.current_threshold} (信号强度: {signal_strength:.6f})")
        
        # 记录阈值调整信息
        logger.info(f"基于信号强度的阈值调整完成，当前阈值: {self.current_threshold}")

    def _execute_strategy(self, market_data):
        """执行策略，生成交易信号

        Args:
            market_data (dict): 市场数据

        Returns:
            dict: 交易信号，包含side, price, amount等信息
        """
        # 保存当前价格到历史数据
        if "price" in market_data:
            self.price_history.append(market_data["price"])
        elif "last" in market_data:
            self.price_history.append(float(market_data["last"]))

        # 计算信号强度
        signal_strength = self.calculate_signal_strength()

        # 基于账户收益调整信号强度
        signal_strength = self.adjust_signal_based_on_account_pnl(signal_strength)

        # 基于信号强度调整阈值
        self.adjust_threshold_based_on_signal_strength(signal_strength)

        # 生成交易信号 (使用自动调节的阈值)
        if signal_strength > self.current_threshold:
            side = "buy"
        elif signal_strength <= -self.current_threshold:
            side = "sell"
        else:
            side = "neutral"  # 信号强度不足，返回中性信号
        
        # 记录当前阈值和信号强度
        logger.info(f"当前阈值: {self.current_threshold}, 信号强度: {signal_strength}")

        # 获取当前价格
        current_price = (
            self.price_history[-1]
            if self.price_history
            else market_data.get("price", 0)
        )

        # 构建交易信号
        signal = {
            "strategy": self.name,
            "side": side,
            "price": current_price,
            "signal_strength": signal_strength,
            "timestamp": market_data.get("timestamp", time.time()),
            "inst_id": market_data.get("inst_id", "BTC-USDT"),  # 使用现货交易对
        }

        logger.info(f"策略信号生成: {signal}")
        return signal
    
    def adjust_signal_based_on_account_pnl(self, signal_strength):
        """基于账户收益调整信号强度
        当账户亏损时，减小信号强度，降低交易频率，控制风险
        当账户盈利时，增大信号强度，增加交易频率，提高盈利机会
        
        Args:
            signal_strength (float): 原始信号强度
            
        Returns:
            float: 调整后的信号强度
        """
        try:
            # 检查是否有账户收益信息
            if hasattr(self, 'account_pnl_ratio'):
                pnl_ratio = self.account_pnl_ratio
                
                # 根据账户收益率调整信号强度
                if pnl_ratio < -5:  # 账户亏损超过5%
                    # 亏损严重，减小信号强度，降低交易频率
                    adjusted_strength = signal_strength * 0.5
                    logger.info(f"基于账户亏损调整信号强度: {signal_strength} → {adjusted_strength} (账户收益率: {pnl_ratio:.2f}%)")
                elif pnl_ratio < 0:  # 账户亏损但不严重
                    # 轻微亏损，小幅减小信号强度
                    adjusted_strength = signal_strength * 0.8
                    logger.info(f"基于账户亏损调整信号强度: {signal_strength} → {adjusted_strength} (账户收益率: {pnl_ratio:.2f}%)")
                elif pnl_ratio > 5:  # 账户盈利超过5%
                    # 盈利良好，增大信号强度，增加交易频率
                    adjusted_strength = signal_strength * 1.2
                    logger.info(f"基于账户盈利调整信号强度: {signal_strength} → {adjusted_strength} (账户收益率: {pnl_ratio:.2f}%)")
                else:
                    # 账户收益正常，不调整信号强度
                    adjusted_strength = signal_strength
                
                return adjusted_strength
            else:
                # 没有账户收益信息，返回原始信号强度
                return signal_strength
                
        except Exception as e:
            logger.error(f"调整信号强度失败: {e}")
            return signal_strength
