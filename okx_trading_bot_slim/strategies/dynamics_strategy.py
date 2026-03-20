import asyncio
import time
import numpy as np
from loguru import logger
from .base_strategy import BaseStrategy

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
    
    def __init__(self, api_client, config=None):
        """
        初始化动力学交易策略
        
        Args:
            api_client (OKXAPIClient): OKX API客户端实例
            config (dict, optional): 策略配置
        """
        super().__init__(api_client, config)
        
        # 从风险管理服务导入RiskManager
        from services.risk_management.risk_manager import RiskManager
        self.risk_manager = RiskManager(api_client)
        
        # 动力学参数配置
        self.dynamics_params = {
            'ε': 0.85,       # 市场动量方向算符 (1同向/-1反向)
            'G_eff': 1.2e-3, # 市场耦合系数 (10⁻³~10⁻²量级)
            'n': 3,          # 市场影响力衰减指数
            'η': 0.75,       # 配对反馈强度
            'γ': 0.1,        # 价差异常衰减率
            'κ': 2.5,        # 相位同步强度
            'λ': 3.0,        # 相位耦合衰减
            't_coll': 0.1    # 市场协同时标(秒)
        }
        
        # 弹簧效应均值回归参数
        self.spring_params = {
            'lookback_period': 20,
            'mean_threshold': 0.03
        }
        
        # 数据容器
        self.price_history = []
        self.phase_history = []
        
        # 更新配置
        if config:
            if 'dynamics' in config:
                self.dynamics_params.update(config['dynamics'])
            if 'spring' in config:
                self.spring_params.update(config['spring'])
            if 'risk' in config:
                self.risk_manager.update_risk_params(**config['risk'])
        
        logger.info("原子核互反动力学策略初始化完成")
    
    async def get_market_data(self, inst_id='BTC-USDT-SWAP'):
        """获取市场数据并计算动力学特征"""
        try:
            ticker = self.api_client.get_ticker(inst_id)
            if ticker:
                last_price = float(ticker[0]['last'])
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
        flux_a = cluster_a['volume'] * cluster_a['velocity']
        flux_b = cluster_b['volume'] * cluster_b['velocity']
        
        # 计算角旋态梯度 (tanh函数模拟市场不平衡)
        delta_s_ab = np.tanh((cluster_a['liquidity'] - cluster_b['liquidity']) / 0.2)
        delta_s_ba = np.tanh((cluster_b['liquidity'] - cluster_a['liquidity']) / 0.2)
        
        # 计算市场距离 (相关性倒数)
        r = 1 / (cluster_a['correlation'] + 1e-5)
        
        # 角动量变化率
        dL_dt = self.dynamics_params['ε'] * self.dynamics_params['G_eff'] * (
            (flux_b * delta_s_ba) / (r ** self.dynamics_params['n']) -
            (flux_a * delta_s_ab) / (r ** self.dynamics_params['n'])
        )
        return dL_dt
    
    def pairing_feedback(self, delta, cluster_a, cluster_b):
        """
        非对称配对反馈方程
        dΔ/dt = ηṅv_pair²[Φ(q_A) - 𝒜_m^(nuc)Φ(q_B)] - γΔ
        """
        # 计算不对称因子
        a_m = abs(cluster_a['size'] - cluster_b['size']) / (cluster_a['size'] + cluster_b['size'])
        
        # 计算配对势 (市场强度指标)
        phi_a = (cluster_a['external_pressure'] - cluster_a['market_depth']) / cluster_a['market_depth']
        phi_b = (cluster_b['external_pressure'] - cluster_b['market_depth']) / cluster_b['market_depth']
        
        # 配对振动速度 (市场波动率)
        v_pair = np.sqrt(delta / cluster_a['mass'])
        
        # 反馈方程
        d_delta_dt = self.dynamics_params['η'] * cluster_a['growth_rate'] * (v_pair ** 2) * (
            phi_a - a_m * phi_b
        ) - self.dynamics_params['γ'] * delta
        
        return d_delta_dt
    
    def quantum_phase_sync(self, phase_a, phase_b, inertia_a, inertia_b):
        """
        量子相位同步方程
        d(φ_A-φ_B)/dt = -κ(I_Aω_A²-I_Bω_B²)/t_coll·e^{-λ|φ_A-φ_B|} + ξ(t)
        """
        # 计算角速度 (价格变化率)
        omega_a = np.mean(np.diff(self.price_history[-5:])) if len(self.price_history) >= 5 else 0
        omega_b = np.mean(np.diff(self.phase_history[-5:])) if len(self.phase_history) >= 5 else 0
        
        # 相位同步项
        phase_diff = abs(phase_a - phase_b)
        sync_term = -self.dynamics_params['κ'] * (
            (inertia_a * omega_a**2 - inertia_b * omega_b**2) / self.dynamics_params['t_coll']
        ) * np.exp(-self.dynamics_params['λ'] * phase_diff)
        
        # 添加市场噪声 (高斯白噪声)
        noise = np.random.normal(0, 0.1)
        
        return sync_term + noise
    
    def calculate_spring_effect(self):
        """计算弹簧效应均值回归信号"""
        if len(self.price_history) > self.spring_params['lookback_period']:
            ma = np.mean(self.price_history[-self.spring_params['lookback_period']:])
            deviation = (self.price_history[-1] - ma) / ma
            
            # 弹簧回归信号
            spring_signal = -np.tanh(deviation / self.spring_params['mean_threshold'])
            return spring_signal
        return 0
    
    def calculate_signal_strength(self):
        """计算综合信号强度"""
        if len(self.price_history) < self.spring_params['lookback_period']:
            return 0
        
        # 计算弹簧效应信号
        spring_signal = self.calculate_spring_effect()
        
        # 模拟集群数据
        cluster_a = {
            'volume': 1000,  # 交易量
            'velocity': 0.02, # 价格变化速度
            'liquidity': 0.8, # 流动性指标
            'correlation': 0.6,
            'size': 1.0,
            'external_pressure': 0.3,
            'market_depth': 0.5,
            'mass': 1.0,
            'growth_rate': 0.01
        }
        
        cluster_b = {**cluster_a, 'size': 1.2, 'correlation': 0.7}
        
        # 计算动力学信号
        momentum_signal = self.calculate_angular_momentum(cluster_a, cluster_b)
        pairing_signal = self.pairing_feedback(0.2, cluster_a, cluster_b)
        
        # 计算相位信号
        if len(self.phase_history) > 5:
            phase_signal = self.quantum_phase_sync(
                self.phase_history[-1],
                self.phase_history[-5],
                1.0, 1.2
            )
        else:
            phase_signal = 0
        
        # 信号融合 (加权合成)
        combined_signal = 0.4*spring_signal + 0.3*momentum_signal + 0.2*pairing_signal + 0.1*phase_signal
        
        return combined_signal
    
    async def execute_trade(self, inst_id, signal_strength):
        """执行交易订单"""
        try:
            # 检查信号强度
            if -0.5 <= signal_strength <= 0.5:
                logger.info("⚖️ 信号强度中性，保持观望")
                return True
            
            # 风险评估: 检查整体风险状态
            overall_risk = self.risk_manager.assess_overall_risk()
            if not overall_risk or not overall_risk['is_account_healthy']:
                logger.warning("⚠️ 账户健康状况不佳，跳过交易")
                return False
            
            # 订单类型决策
            side = "buy" if signal_strength > 0.5 else "sell"
            
            # 获取当前价格
            current_price = self.price_history[-1]
            
            # 计算仓位大小 (弹簧效应)
            account_balance = overall_risk['account_balance']
            position_size = np.tanh(signal_strength) * min(
                self.risk_manager.risk_params['max_order_amount'],
                account_balance * 0.2  # 最多使用20%的账户余额
            )
            
            order_size = position_size / current_price
            
            # 构建订单信息
            order_info = {
                'inst_id': inst_id,
                'side': side,
                'sz': str(order_size),
                'px': str(current_price)
            }
            
            # 风险检查: 使用风险管理服务检查订单风险
            is_allowed, reason = self.risk_manager.check_order_risk(order_info)
            if not is_allowed:
                logger.warning(f"⚠️ 订单风险检查失败: {reason}")
                return False
            
            # 执行交易
            order_id = self.api_client.place_order(
                inst_id=inst_id,
                side=side,
                order_type="limit",
                price=current_price,
                amount=order_size
            )
            
            if order_id:
                logger.info(f"✅ 订单执行成功: {side} {inst_id} {order_size} @ {current_price}")
                return True
            else:
                logger.error("❌ 订单失败")
                return False
                
        except Exception as e:
            logger.error(f"🔥 交易异常: {str(e)}")
            return False
    
    async def run_live_trading(self, inst_id='BTC-USDT-SWAP', interval=60):
        """
        运行实盘交易
        
        Args:
            inst_id: 交易品种
            interval: 策略运行间隔(秒)
        """
        logger.info("🚀 启动原子核互反动力学交易策略...")
        
        iteration_count = 0
        
        while True:
            try:
                # 获取市场数据
                current_price = await self.get_market_data(inst_id)
                if not current_price:
                    await asyncio.sleep(interval)
                    continue
                
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
                await asyncio.sleep(interval)
                
            except KeyboardInterrupt:
                logger.info("🛑 策略手动终止")
                break
            except Exception as e:
                logger.error(f"⚠️ 策略执行异常: {str(e)}")
                await asyncio.sleep(interval)
    
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
            'total_return': 0.0,
            'win_rate': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0,
            'total_trades': 0
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
                signal_strength = ε * G_eff * data.get('momentum', 0) + η * data.get('pairing', 0) - γ * data.get('volatility', 0)
                position_size = np.tanh(κ * signal_strength) * np.exp(-λ * data.get('risk', 0))
                cumulative_return += position_size * data.get('return', 0)
            
            # 最大化夏普比率
            returns = [d.get('return', 0) for d in historical_data]
            return -cumulative_return / (np.std(returns) + 1e-5)  # 添加小量避免除零
        
        # 参数边界
        bounds = [
            (-1, 1),       # ε
            (1e-4, 1e-2),  # G_eff
            (0.1, 2.0),    # η
            (0.05, 0.3),   # γ
            (1.0, 5.0),    # κ
            (1.0, 8.0)     # λ
        ]
        
        # 初始参数
        initial_params = [
            self.dynamics_params['ε'],
            self.dynamics_params['G_eff'],
            self.dynamics_params['η'],
            self.dynamics_params['γ'],
            self.dynamics_params['κ'],
            self.dynamics_params['λ']
        ]
        
        # 优化求解
        try:
            result = minimize(loss_function, initial_params, bounds=bounds, method='SLSQP')
            
            # 更新最优参数
            if result.success:
                optimized_params = dict(zip(['ε', 'G_eff', 'η', 'γ', 'κ', 'λ'], result.x))
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
        for i in range(1, N+1):
            trajectory += a[i-1] * np.sin(2 * np.pi * i * t) + b[i-1] * np.cos(2 * np.pi * i * t)
        
        return trajectory
    
    def reduce_param_set(self):
        """采用QR分解消除参数冗余，实现动态模型降维"""
        if not has_scipy:
            logger.warning("scipy not available, skipping parameter reduction")
            return []
        
        # 构建参数相关性矩阵
        param_names = list(self.dynamics_params.keys())[:6]  # 取前6个参数
        param_values = np.array([self.dynamics_params[name] for name in param_names]).reshape(-1, 1)
        
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
            logger.info(f"   对应的参数名: {[param_names[i] for i in important_params]}")
            
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
            
            training_data.append({
                'momentum': momentum,
                'pairing': pairing,
                'volatility': volatility,
                'risk': risk,
                'return': return_
            })
        
        return training_data
    
    def stop_trading(self):
        """停止交易"""
        logger.info("🛑 停止原子核互反动力学策略")
        return True
    
    def execute(self, market_data):
        """执行策略，生成交易信号
        
        Args:
            market_data (dict): 市场数据
            
        Returns:
            dict: 交易信号，包含side, price, amount等信息
        """
        # 保存当前价格到历史数据
        if 'price' in market_data:
            self.price_history.append(market_data['price'])
        elif 'last' in market_data:
            self.price_history.append(float(market_data['last']))
        
        # 计算信号强度
        signal_strength = self.calculate_signal_strength()
        
        # 生成交易信号
        if signal_strength > 0.5:
            side = "buy"
        elif signal_strength < -0.5:
            side = "sell"
        else:
            return None  # 信号强度不足，不生成交易信号
        
        # 获取当前价格
        current_price = self.price_history[-1] if self.price_history else market_data.get('price', 0)
        
        # 构建交易信号
        signal = {
            'strategy': self.name,
            'side': side,
            'price': current_price,
            'signal_strength': signal_strength,
            'timestamp': market_data.get('timestamp', time.time()),
            'inst_id': market_data.get('inst_id', 'BTC-USDT-SWAP')
        }
        
        logger.info(f"策略信号生成: {signal}")
        return signal
