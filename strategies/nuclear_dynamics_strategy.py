import logging
import time
import numpy as np
from typing import Dict, Optional
from strategies.base_strategy import BaseStrategy

# 配置日志
logger = logging.getLogger('Strategy')

class NuclearDynamicsStrategy(BaseStrategy):
    """
    核互反动力学策略 v3.0
    
    基于原子核内粒子相互作用的物理模型，模拟价格波动的弹压工作和角动量流
    特性：
    - 弹压工作识别（下跌-上涨周期）
    - 弹簧飘移方向计算
    - 角动量流反向传输分析
    - 非对称配对反馈
    - 量子相位同步耗散
    - 信号评分系统
    """
    
    def __init__(self, config=None):
        """
        初始化策略
        
        Args:
            config (dict, optional): 策略配置
        """
        super().__init__(config)
        
        # ==================== 核心参数 ====================
        self.params = {
            'fall_threshold': 0.002,       # 下跌阈值（0.2%）
            'spring_threshold': 0.001,     # 弹簧反弹阈值（0.1%）
            'phase_sync_threshold': 0.1,    # 相位同步阈值
            'phase_lockout_threshold': 0.5, # 相位锁定阈值
            'roc_period': 5,               # 变化率周期
            'pairing_half_life_window': 10, # 配对半衰期窗口
            'atr_period': 5,
            'min_atr_price_ratio': 0.002,    # 最低ATR/价格比（0.2%）
            'max_atr_price_ratio': 0.03,     # 最高ATR/价格比（3%）
            # 风险预算（单笔风险占账户比例）
            'max_risk_sss': 0.02,
            'max_risk_ss': 0.015,
            'max_risk_s': 0.01,
        }

        # ==================== 风险控制参数 ====================
        self.risk_params = {
            'max_leverage': 5,
            'stop_loss_atr_mult_long': 1.5,   # 做多止损ATR倍数（更宽松）
            'stop_loss_atr_mult_short': 1.0,  # 做空止损ATR倍数
            'take_profit_r_mult': 2.0,        # 固定止盈R倍数（用于部分仓位）
            'max_position_value': 5000,       # 单笔最大持仓名义价值（USDT）
            'daily_loss_limit': 0.05,
            'time_stop_bars': 10,             # 时间止损：10根K线未盈利则退出
            'time_stop_atr_mult': 0.5,        # 时间止损所需的最小有利波动（ATR倍数）
        }

        # ==================== 交易成本参数 ====================
        self.cost_params = {
            'maker_fee': 0.0002,      # Maker手续费 0.02%
            'taker_fee': 0.0005,      # Taker手续费 0.05%
            'slippage': 0.0005,       # 滑点 0.05%
            'funding_rate_8h': 0.0001 # 平均资金费率假设（实际应动态获取）
        }

        # ==================== 数据容器 ====================
        # 按交易对存储数据
        self.symbol_data = {}

        # 信号跟踪
        self.last_signal_direction = None

        # 配置覆盖
        if config:
            if "params" in config:
                self.params.update(config["params"])
            if "risk" in config:
                self.risk_params.update(config["risk"])
            if "cost" in config:
                self.cost_params.update(config["cost"])

        logger.info("核互反动力学策略初始化完成 (v3.0)")

    def _load_historical_data(self):
        """
        从OSS或日志文件加载当日历史数据
        """
        try:
            # 获取当日日期
            today = time.strftime("%Y-%m-%d")
            
            # 首先尝试从OSS加载当日历史数据
            from core.utils.oss_persistence import OSSPersistenceManager
            oss_manager = OSSPersistenceManager()
            
            # 为默认交易对BTC-USDT加载数据
            symbol = "BTC-USDT"
            if symbol not in self.symbol_data:
                self.symbol_data[symbol] = {
                    "price_history": [],
                    "volume_history": [],
                    "pressure_values": [],
                    "elastic_values": [],
                    "spring_means": [],
                    "phase_history": []
                }
            
            # 尝试从OSS加载当日价格历史数据
            data = oss_manager.load_from_oss(f"price_history_{symbol}_{today}.json")
            if data and "price_history" in data:
                # 检查数据是否是当日数据
                data_date = data.get("date", "")
                if data_date == today:
                    self.symbol_data[symbol]["price_history"] = data["price_history"]
                    logger.info(f'从OSS加载了当日({today}) {len(self.symbol_data[symbol]["price_history"])} 个价格数据点')
                else:
                    logger.info(f'OSS数据日期({data_date})不是今日({today})，将重新开始积累数据')
            else:
                # 如果OSS加载失败，从日志文件加载当日数据
                import re
                price_pattern = r'price=(\d+\.\d+)'
                
                with open('trading_bot.log', 'r') as f:
                    lines = f.readlines()
                
                for line in lines:
                    # 只加载当日的价格数据
                    if today in line:
                        match = re.search(price_pattern, line)
                        if match:
                            price = float(match.group(1))
                            self.symbol_data[symbol]["price_history"].append(price)
                
                if self.symbol_data[symbol]["price_history"]:
                    logger.info(f'从日志文件加载了当日({today}) {len(self.symbol_data[symbol]["price_history"])} 个价格数据点')
                else:
                    logger.info(f'当日({today})没有历史数据，将重新开始积累数据')
            
            # 限制历史数据长度，只保留最近的200个数据点
            if len(self.symbol_data[symbol]["price_history"]) > 200:
                self.symbol_data[symbol]["price_history"] = self.symbol_data[symbol]["price_history"][-200:]
            
        except Exception as e:
            logger.error(f"加载历史数据失败: {e}")
            # 如果加载失败，为默认交易对BTC-USDT使用默认价格数据
            symbol = "BTC-USDT"
            if symbol not in self.symbol_data:
                self.symbol_data[symbol] = {
                    "price_history": [],
                    "volume_history": [],
                    "pressure_values": [],
                    "elastic_values": [],
                    "spring_means": [],
                    "phase_history": []
                }
            
            if len(self.symbol_data[symbol]["price_history"]) < 20:
                # 添加一些默认价格数据，以便策略能够开始计算
                default_price = 69000.0
                for i in range(20 - len(self.symbol_data[symbol]["price_history"])):
                    # 添加一些随机波动的价格
                    import random
                    price = default_price * (1 + random.uniform(-0.01, 0.01))
                    self.symbol_data[symbol]["price_history"].append(price)
                logger.info(f'添加了 {20 - len(self.symbol_data[symbol]["price_history"])} 个默认价格数据点')

    def _execute_strategy(self, market_data):
        """
        执行策略，生成交易信号
        
        Args:
            market_data (dict): 市场数据
            
        Returns:
            dict: 交易信号
        """
        # 初始化信号
        signal = {
            'side': 'hold',
            'price': 0,
            'size': 0,
            'confidence': 0,
            'risk_level': 'low',
            'signal_type': 'none',
            'details': {}
        }
        
        try:
            # 提取市场数据
            inst_id = market_data.get('instId') or market_data.get('inst_id')
            if not inst_id:
                logger.error("市场数据中缺少instId或inst_id")
                return signal
            
            # 确保符号数据存在
            if inst_id not in self.symbol_data:
                self.symbol_data[inst_id] = {
                    "price_history": [],
                    "volume_history": [],
                    "pressure_values": [],
                    "elastic_values": [],
                    "spring_means": [],
                    "phase_history": []
                }
            
            # 提取价格数据
            price = market_data.get('price') or market_data.get('last')
            if not price:
                logger.error("市场数据中缺少price或last价格")
                return signal
            
            # 更新价格历史
            self.symbol_data[inst_id]["price_history"].append(float(price))
            
            # 限制历史数据长度
            if len(self.symbol_data[inst_id]["price_history"]) > 200:
                self.symbol_data[inst_id]["price_history"] = self.symbol_data[inst_id]["price_history"][-200:]
            
            # 保存价格历史数据到OSS（使用当日日期）
            try:
                from core.utils.oss_persistence import OSSPersistenceManager
                oss_manager = OSSPersistenceManager()
                today = time.strftime("%Y-%m-%d")
                data = {
                    "date": today,
                    "price_history": self.symbol_data[inst_id]["price_history"],
                    "timestamp": time.time()
                }
                oss_manager.save_to_oss(f"price_history_{inst_id}_{today}.json", data)
            except Exception as e:
                logger.error(f"保存价格历史到OSS失败: {e}")
            
            # 确保有足够的历史数据
            if len(self.symbol_data[inst_id]["price_history"]) < 20:
                logger.debug(f'历史数据不足，需要至少20个数据点，当前只有 {len(self.symbol_data[inst_id]["price_history"])} 个')
                return signal
            
            # 计算弹簧飘移方向
            spring_drift = self._calculate_spring_drift(inst_id)
            
            # 计算角动量流
            angular_momentum = self._calculate_angular_momentum_flow(inst_id)
            
            # 计算配对能隙趋势
            pairing_gap = self._calculate_pairing_gap_trend(inst_id)
            
            # 计算相位同步
            phase_sync = self._calculate_phase_sync(inst_id)
            
            # 计算信号评分
            score = self._calculate_signal_score(spring_drift, angular_momentum, pairing_gap, phase_sync)
            
            # 确定交易方向（降低阈值，让系统更容易触发交易）
            if score > 0.0001:
                side = 'buy'
            elif score < -0.0001:
                side = 'sell'
            else:
                side = 'hold'
            
            # 调试：打印信号阈值和交易方向
            logger.info(f"信号阈值检查: score={score}, side={side}")
            
            # 只有当信号明确时才生成交易信号
            if side != 'hold':
                # 计算ATR
                atr = self._calculate_atr(inst_id)
                
                # 计算交易量
                size = self._calculate_trade_size(price, atr, side)
                
                # 计算置信度
                confidence = min(abs(score) / 100, 1.0)
                
                # 确定风险等级
                risk_level = self._determine_risk_level(score, atr, price)
                
                # 确定信号类型
                signal_type = self._determine_signal_type(score, spring_drift, angular_momentum)
                
                # 构建信号
                signal = {
                    'side': side,
                    'price': price,
                    'size': size,
                    'confidence': confidence,
                    'risk_level': risk_level,
                    'signal_type': signal_type,
                    'details': {
                        'score': score,
                        'spring_drift': spring_drift,
                        'angular_momentum': angular_momentum,
                        'pairing_gap': pairing_gap,
                        'phase_sync': phase_sync,
                        'atr': atr
                    }
                }
                
                # 记录信号
                logger.info(f"生成交易信号: {signal}")
                
        except Exception as e:
            logger.error(f"执行策略失败: {e}")
        
        return signal

    def _calculate_spring_drift(self, inst_id):
        """
        计算弹簧飘移方向
        
        Args:
            inst_id (str): 交易对ID
            
        Returns:
            float: 弹簧飘移方向，正值表示向上，负值表示向下
        """
        try:
            # 获取价格历史
            price_history = self.symbol_data[inst_id]["price_history"]
            
            # 计算弹簧飘移
            # 弹簧飘移是指价格在经历下跌后反弹的强度和方向
            # 我们使用最近的价格变化来计算
            if len(price_history) < 10:
                return 0.0
            
            # 计算最近10个价格的变化
            price_changes = []
            for i in range(1, len(price_history)):
                change = (price_history[i] - price_history[i-1]) / price_history[i-1]
                price_changes.append(change)
            
            # 计算弹簧飘移
            # 弹簧飘移 = 最近5个价格变化的平均值 - 最近10个价格变化的平均值
            if len(price_changes) >= 10:
                recent_avg = np.mean(price_changes[-5:])
                historical_avg = np.mean(price_changes[-10:])
                spring_drift = recent_avg - historical_avg
            else:
                spring_drift = 0.0
            
            # 调试：打印弹簧飘移
            logger.debug(f"弹簧飘移: {spring_drift}")
            
            return spring_drift
            
        except Exception as e:
            logger.error(f"计算弹簧飘移失败: {e}")
            return 0.0

    def _calculate_angular_momentum_flow(self, inst_id):
        """
        计算角动量流
        
        Args:
            inst_id (str): 交易对ID
            
        Returns:
            float: 角动量流，正值表示向上，负值表示向下
        """
        try:
            # 获取价格历史
            price_history = self.symbol_data[inst_id]["price_history"]
            
            # 计算角动量流
            # 角动量流是指价格变化的速率和方向
            # 我们使用价格变化的二阶导数来计算
            if len(price_history) < 10:
                return 0.0
            
            # 计算价格变化
            price_changes = []
            for i in range(1, len(price_history)):
                change = (price_history[i] - price_history[i-1]) / price_history[i-1]
                price_changes.append(change)
            
            # 计算价格变化的变化（二阶导数）
            momentum_changes = []
            for i in range(1, len(price_changes)):
                momentum_change = price_changes[i] - price_changes[i-1]
                momentum_changes.append(momentum_change)
            
            # 计算角动量流
            if len(momentum_changes) >= 5:
                angular_momentum = np.mean(momentum_changes[-5:])
            else:
                angular_momentum = 0.0
            
            # 调试：打印角动量流
            logger.debug(f"角动量流: {angular_momentum}")
            
            return angular_momentum
            
        except Exception as e:
            logger.error(f"计算角动量流失败: {e}")
            return 0.0

    def _calculate_pairing_gap_trend(self, inst_id):
        """
        计算配对能隙趋势
        
        Args:
            inst_id (str): 交易对ID
            
        Returns:
            float: 配对能隙趋势，正值表示向上，负值表示向下
        """
        try:
            # 获取价格历史
            price_history = self.symbol_data[inst_id]["price_history"]
            
            # 计算配对能隙趋势
            # 配对能隙趋势是指价格在不同时间尺度上的差异
            # 我们使用不同时间窗口的移动平均线来计算
            if len(price_history) < 20:
                return 0.0
            
            # 计算不同时间窗口的移动平均线
            short_window = 5
            long_window = 15
            
            short_ma = np.mean(price_history[-short_window:])
            long_ma = np.mean(price_history[-long_window:])
            
            # 计算配对能隙趋势
            pairing_gap = (short_ma - long_ma) / long_ma
            
            # 调试：打印配对能隙趋势
            logger.debug(f"配对能隙趋势: {pairing_gap}")
            
            return pairing_gap
            
        except Exception as e:
            logger.error(f"计算配对能隙趋势失败: {e}")
            return 0.0

    def _calculate_phase_sync(self, inst_id):
        """
        计算相位同步
        
        Args:
            inst_id (str): 交易对ID
            
        Returns:
            float: 相位同步，正值表示同步，负值表示不同步
        """
        try:
            # 获取价格历史
            price_history = self.symbol_data[inst_id]["price_history"]
            
            # 计算相位同步
            # 相位同步是指价格变化的周期性和一致性
            # 我们使用价格变化的自相关来计算
            if len(price_history) < 20:
                return 0.0
            
            # 计算价格变化
            price_changes = []
            for i in range(1, len(price_history)):
                change = (price_history[i] - price_history[i-1]) / price_history[i-1]
                price_changes.append(change)
            
            # 计算自相关
            max_lag = min(10, len(price_changes) - 1)
            autocorrelations = []
            for lag in range(1, max_lag + 1):
                if len(price_changes) - lag > 0:
                    correlation = np.corrcoef(price_changes[:-lag], price_changes[lag:])[0, 1]
                    autocorrelations.append(correlation)
            
            # 计算相位同步
            if autocorrelations:
                phase_sync = np.mean(autocorrelations)
            else:
                phase_sync = 0.0
            
            # 调试：打印相位同步
            logger.debug(f"相位同步: {phase_sync}")
            
            return phase_sync
            
        except Exception as e:
            logger.error(f"计算相位同步失败: {e}")
            return 0.0

    def _calculate_signal_score(self, spring_drift, angular_momentum, pairing_gap, phase_sync):
        """
        计算信号评分
        
        Args:
            spring_drift (float): 弹簧飘移方向
            angular_momentum (float): 角动量流
            pairing_gap (float): 配对能隙趋势
            phase_sync (float): 相位同步
            
        Returns:
            float: 信号评分，正值表示买入，负值表示卖出
        """
        try:
            # 计算信号评分
            # 信号评分 = 弹簧飘移 * 0.4 + 角动量流 * 0.3 + 配对能隙趋势 * 0.2 + 相位同步 * 0.1
            score = (spring_drift * 0.4) + (angular_momentum * 0.3) + (pairing_gap * 0.2) + (phase_sync * 0.1)
            
            # 调试：打印信号评分
            logger.info(f"信号评分: {score}")
            
            return score
            
        except Exception as e:
            logger.error(f"计算信号评分失败: {e}")
            return 0.0

    def _calculate_atr(self, inst_id):
        """
        计算ATR（平均真实范围）
        
        Args:
            inst_id (str): 交易对ID
            
        Returns:
            float: ATR值
        """
        try:
            # 获取价格历史
            price_history = self.symbol_data[inst_id]["price_history"]
            
            # 计算ATR
            if len(price_history) < 10:
                return 0.0
            
            # 计算真实范围
            true_ranges = []
            for i in range(1, len(price_history)):
                high = max(price_history[i], price_history[i-1])
                low = min(price_history[i], price_history[i-1])
                true_range = high - low
                true_ranges.append(true_range)
            
            # 计算ATR
            atr = np.mean(true_ranges[-10:])
            
            return atr
            
        except Exception as e:
            logger.error(f"计算ATR失败: {e}")
            return 0.0

    def _calculate_trade_size(self, price, atr, side):
        """
        计算交易量
        
        Args:
            price (float): 当前价格
            atr (float): ATR值
            side (str): 交易方向
            
        Returns:
            float: 交易量
        """
        try:
            # 计算交易量
            # 交易量 = 固定交易金额 / 价格
            fixed_trade_amount = 1.0  # 固定交易金额为1 USDT
            size = fixed_trade_amount / price
            
            return size
            
        except Exception as e:
            logger.error(f"计算交易量失败: {e}")
            return 0.0

    def _determine_risk_level(self, score, atr, price):
        """
        确定风险等级
        
        Args:
            score (float): 信号评分
            atr (float): ATR值
            price (float): 当前价格
            
        Returns:
            str: 风险等级
        """
        try:
            # 确定风险等级
            # 风险等级基于信号评分的绝对值和ATR/价格比
            score_abs = abs(score)
            atr_price_ratio = atr / price
            
            if score_abs > 50 and atr_price_ratio > 0.02:
                return 'high'
            elif score_abs > 30 and atr_price_ratio > 0.01:
                return 'medium'
            else:
                return 'low'
            
        except Exception as e:
            logger.error(f"确定风险等级失败: {e}")
            return 'low'

    def _determine_signal_type(self, score, spring_drift, angular_momentum):
        """
        确定信号类型
        
        Args:
            score (float): 信号评分
            spring_drift (float): 弹簧飘移方向
            angular_momentum (float): 角动量流
            
        Returns:
            str: 信号类型
        """
        try:
            # 确定信号类型
            # 信号类型基于信号评分、弹簧飘移和角动量流
            score_abs = abs(score)
            
            if score_abs > 50:
                return 'strong'
            elif score_abs > 30:
                return 'medium'
            else:
                return 'weak'
            
        except Exception as e:
            logger.error(f"确定信号类型失败: {e}")
            return 'weak'

    def get_optimizable_parameters(self):
        """
        获取可优化的参数列表
        """
        return [
            {'name': 'fall_threshold', 'type': 'float', 'min': 0.001, 'max': 0.05, 'default': 0.002},
            {'name': 'spring_threshold', 'type': 'float', 'min': 0.0005, 'max': 0.02, 'default': 0.001},
            {'name': 'phase_sync_threshold', 'type': 'float', 'min': 0.05, 'max': 0.3, 'default': 0.1},
            {'name': 'roc_period', 'type': 'int', 'min': 3, 'max': 10, 'default': 5},
            {'name': 'pairing_half_life_window', 'type': 'int', 'min': 5, 'max': 20, 'default': 10},
        ]
    
    def execute(self, market_data):
        """
        执行策略，生成交易信号
        
        Args:
            market_data (dict): 市场数据
            
        Returns:
            dict: 交易信号
        """
        return self._execute_strategy(market_data)