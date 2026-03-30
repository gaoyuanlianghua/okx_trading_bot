import asyncio
import numpy as np
import pandas as pd
import scipy.stats as stats
from typing import Dict, List, Optional, Any
from core.utils.logger import get_logger

logger = get_logger(__name__)

class AdvancedRiskManager:
    def __init__(self):
        self.historical_returns = []
        self.position_size = 0
        self.risk_parameters = {
            'var_confidence': 0.95,
            'max_position_size': 0.1,  # 最大仓位占总资金的比例
            'max_drawdown': 0.2,  # 最大回撤
            'risk_per_trade': 0.02,  # 每笔交易的风险比例
            'leverage_limit': 5,  # 最大杠杆
            'stop_loss_pct': 0.01,  # 止损百分比
            'take_profit_pct': 0.02  # 止盈百分比
        }
    
    def set_risk_parameters(self, params: Dict[str, float]):
        """
        设置风险参数
        
        Args:
            params: 风险参数字典
        """
        self.risk_parameters.update(params)
        logger.info(f"风险参数已更新: {params}")
    
    def calculate_var(self, returns: List[float], confidence: float = 0.95, method: str = 'parametric') -> float:
        """
        计算风险价值(VaR)
        
        Args:
            returns: 收益率序列
            confidence: 置信水平
            method: 计算方法 ('parametric', 'historical', 'monte_carlo')
            
        Returns:
            float: VaR值
        """
        if not returns:
            return 0.0
        
        if method == 'parametric':
            # 参数法（正态分布假设）
            mean = np.mean(returns)
            std = np.std(returns)
            var = mean - std * stats.norm.ppf(1 - confidence)
        elif method == 'historical':
            # 历史模拟法
            sorted_returns = np.sort(returns)
            var_index = int(len(sorted_returns) * (1 - confidence))
            var = -sorted_returns[var_index]
        elif method == 'monte_carlo':
            # 蒙特卡洛模拟法
            mean = np.mean(returns)
            std = np.std(returns)
            simulations = np.random.normal(mean, std, 10000)
            sorted_simulations = np.sort(simulations)
            var_index = int(len(sorted_simulations) * (1 - confidence))
            var = -sorted_simulations[var_index]
        else:
            raise ValueError(f"不支持的VaR计算方法: {method}")
        
        logger.debug(f"计算VaR: {var:.4f}, 方法: {method}, 置信水平: {confidence}")
        return var
    
    def calculate_cvar(self, returns: List[float], confidence: float = 0.95) -> float:
        """
        计算条件风险价值(CVaR)
        
        Args:
            returns: 收益率序列
            confidence: 置信水平
            
        Returns:
            float: CVaR值
        """
        if not returns:
            return 0.0
        
        sorted_returns = np.sort(returns)
        var_index = int(len(sorted_returns) * (1 - confidence))
        cvar = -np.mean(sorted_returns[:var_index])
        
        logger.debug(f"计算CVaR: {cvar:.4f}, 置信水平: {confidence}")
        return cvar
    
    def perform_stress_test(self, portfolio_value: float, stress_scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        执行压力测试
        
        Args:
            portfolio_value: 投资组合价值
            stress_scenarios: 压力情景列表
            
        Returns:
            Dict: 压力测试结果
        """
        results = []
        
        for scenario in stress_scenarios:
            name = scenario['name']
            price_change = scenario['price_change']
            
            # 计算压力情景下的损失
            loss = portfolio_value * price_change
            
            results.append({
                'scenario': name,
                'price_change': price_change,
                'loss': loss,
                'loss_percentage': price_change
            })
        
        # 计算最大损失和平均损失
        losses = [r['loss'] for r in results]
        max_loss = min(losses)  # 损失为负数，所以最小值是最大损失
        avg_loss = np.mean(losses)
        
        stress_test_result = {
            'scenarios': results,
            'max_loss': max_loss,
            'average_loss': avg_loss,
            'portfolio_value': portfolio_value
        }
        
        logger.info(f"压力测试完成，最大损失: {max_loss:.2f}, 平均损失: {avg_loss:.2f}")
        return stress_test_result
    
    def generate_stress_scenarios(self) -> List[Dict[str, Any]]:
        """
        生成标准压力情景
        
        Returns:
            List[Dict]: 压力情景列表
        """
        return [
            {'name': '2008年金融危机', 'price_change': -0.35},
            {'name': '2020年新冠疫情', 'price_change': -0.30},
            {'name': '2022年加密货币崩盘', 'price_change': -0.60},
            {'name': '正常波动', 'price_change': -0.10},
            {'name': '极端波动', 'price_change': -0.40}
        ]
    
    def calculate_position_size(self, account_balance: float, entry_price: float, stop_loss_price: float) -> float:
        """
        计算最优仓位大小
        
        Args:
            account_balance: 账户余额
            entry_price: 入场价格
            stop_loss_price: 止损价格
            
        Returns:
            float: 仓位大小
        """
        # 计算每单位的风险
        risk_per_unit = abs(entry_price - stop_loss_price)
        
        # 计算最大可承受损失
        max_loss = account_balance * self.risk_parameters['risk_per_trade']
        
        # 计算仓位大小
        position_size = max_loss / risk_per_unit
        
        # 检查是否超过最大仓位限制
        max_position_value = account_balance * self.risk_parameters['max_position_size']
        max_position_size = max_position_value / entry_price
        
        position_size = min(position_size, max_position_size)
        
        logger.debug(f"计算仓位大小: {position_size:.4f}, 账户余额: {account_balance:.2f}, 入场价格: {entry_price:.2f}, 止损价格: {stop_loss_price:.2f}")
        return position_size
    
    def check_risk_limits(self, position_size: float, entry_price: float, account_balance: float) -> Dict[str, Any]:
        """
        检查风险限制
        
        Args:
            position_size: 仓位大小
            entry_price: 入场价格
            account_balance: 账户余额
            
        Returns:
            Dict: 风险检查结果
        """
        position_value = position_size * entry_price
        leverage = position_value / account_balance
        
        checks = {
            'position_size': {
                'value': position_size,
                'limit': account_balance * self.risk_parameters['max_position_size'] / entry_price,
                'passed': position_size <= account_balance * self.risk_parameters['max_position_size'] / entry_price
            },
            'leverage': {
                'value': leverage,
                'limit': self.risk_parameters['leverage_limit'],
                'passed': leverage <= self.risk_parameters['leverage_limit']
            },
            'position_value': {
                'value': position_value,
                'limit': account_balance * self.risk_parameters['max_position_size'],
                'passed': position_value <= account_balance * self.risk_parameters['max_position_size']
            }
        }
        
        all_passed = all(check['passed'] for check in checks.values())
        
        result = {
            'checks': checks,
            'all_passed': all_passed
        }
        
        if not all_passed:
            logger.warning(f"风险检查失败: {result}")
        
        return result
    
    def update_historical_returns(self, returns: List[float]):
        """
        更新历史收益率
        
        Args:
            returns: 收益率序列
        """
        self.historical_returns.extend(returns)
        # 保持历史数据的长度
        if len(self.historical_returns) > 1000:
            self.historical_returns = self.historical_returns[-1000:]
        
        logger.debug(f"历史收益率已更新，当前数据点: {len(self.historical_returns)}")
    
    def get_risk_metrics(self) -> Dict[str, float]:
        """
        获取风险指标
        
        Returns:
            Dict: 风险指标
        """
        if not self.historical_returns:
            return {
                'var_95': 0.0,
                'cvar_95': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'volatility': 0.0
            }
        
        returns = np.array(self.historical_returns)
        volatility = np.std(returns)
        sharpe_ratio = np.mean(returns) / volatility * np.sqrt(252) if volatility > 0 else 0
        
        # 计算最大回撤
        cumulative_returns = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdowns = (cumulative_returns - running_max) / running_max
        max_drawdown = abs(np.min(drawdowns))
        
        var_95 = self.calculate_var(self.historical_returns, 0.95)
        cvar_95 = self.calculate_cvar(self.historical_returns, 0.95)
        
        metrics = {
            'var_95': var_95,
            'cvar_95': cvar_95,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'volatility': volatility
        }
        
        logger.debug(f"风险指标: {metrics}")
        return metrics
    
    async def monitor_risk(self, portfolio_value: float, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        监控风险
        
        Args:
            portfolio_value: 投资组合价值
            positions: 持仓列表
            
        Returns:
            Dict: 风险监控结果
        """
        # 计算总风险暴露
        total_exposure = sum(position['size'] * position['current_price'] for position in positions)
        
        # 计算杠杆
        leverage = total_exposure / portfolio_value
        
        # 执行压力测试
        stress_scenarios = self.generate_stress_scenarios()
        stress_test_result = self.perform_stress_test(portfolio_value, stress_scenarios)
        
        # 获取风险指标
        risk_metrics = self.get_risk_metrics()
        
        # 检查风险限制
        risk_limits_check = {
            'leverage': leverage <= self.risk_parameters['leverage_limit'],
            'max_drawdown': risk_metrics['max_drawdown'] <= self.risk_parameters['max_drawdown'],
            'total_exposure': total_exposure <= portfolio_value * self.risk_parameters['max_position_size']
        }
        
        # 生成风险警报
        alerts = []
        if not risk_limits_check['leverage']:
            alerts.append(f"杠杆过高: {leverage:.2f}, 限制: {self.risk_parameters['leverage_limit']}")
        if not risk_limits_check['max_drawdown']:
            alerts.append(f"最大回撤过高: {risk_metrics['max_drawdown']:.2f}, 限制: {self.risk_parameters['max_drawdown']}")
        if not risk_limits_check['total_exposure']:
            alerts.append(f"总风险暴露过高: {total_exposure:.2f}, 限制: {portfolio_value * self.risk_parameters['max_position_size']:.2f}")
        
        monitor_result = {
            'portfolio_value': portfolio_value,
            'total_exposure': total_exposure,
            'leverage': leverage,
            'risk_metrics': risk_metrics,
            'stress_test': stress_test_result,
            'risk_limits_check': risk_limits_check,
            'alerts': alerts
        }
        
        if alerts:
            logger.warning(f"风险警报: {alerts}")
        
        return monitor_result
