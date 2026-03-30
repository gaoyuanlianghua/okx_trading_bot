import asyncio
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from typing import Dict, List, Optional, Any
from core.utils.logger import get_logger

logger = get_logger(__name__)

class PortfolioOptimizer:
    def __init__(self):
        self.strategies = {}
        self.historical_returns = {}
        self.risk_free_rate = 0.02
    
    def add_strategy(self, strategy_name: str, expected_return: float, volatility: float):
        """
        添加策略到投资组合
        
        Args:
            strategy_name: 策略名称
            expected_return: 预期收益率
            volatility: 波动率
        """
        self.strategies[strategy_name] = {
            'expected_return': expected_return,
            'volatility': volatility
        }
        logger.info(f"策略已添加到投资组合: {strategy_name}, 预期收益率: {expected_return:.4f}, 波动率: {volatility:.4f}")
    
    def set_correlation_matrix(self, correlation_matrix: Dict[str, Dict[str, float]]):
        """
        设置策略之间的相关系数矩阵
        
        Args:
            correlation_matrix: 相关系数矩阵
        """
        self.correlation_matrix = correlation_matrix
        logger.info("相关系数矩阵已设置")
    
    def calculate_portfolio_return(self, weights: Dict[str, float]) -> float:
        """
        计算投资组合的预期收益率
        
        Args:
            weights: 策略权重
            
        Returns:
            float: 预期收益率
        """
        portfolio_return = 0.0
        for strategy_name, weight in weights.items():
            portfolio_return += weight * self.strategies[strategy_name]['expected_return']
        return portfolio_return
    
    def calculate_portfolio_volatility(self, weights: Dict[str, float]) -> float:
        """
        计算投资组合的波动率
        
        Args:
            weights: 策略权重
            
        Returns:
            float: 波动率
        """
        portfolio_volatility = 0.0
        strategy_names = list(weights.keys())
        
        for i, strategy1 in enumerate(strategy_names):
            for j, strategy2 in enumerate(strategy_names):
                weight1 = weights[strategy1]
                weight2 = weights[strategy2]
                vol1 = self.strategies[strategy1]['volatility']
                vol2 = self.strategies[strategy2]['volatility']
                correlation = self.correlation_matrix.get(strategy1, {}).get(strategy2, 0)
                portfolio_volatility += weight1 * weight2 * vol1 * vol2 * correlation
        
        return np.sqrt(portfolio_volatility)
    
    def calculate_sharpe_ratio(self, weights: Dict[str, float]) -> float:
        """
        计算投资组合的夏普比率
        
        Args:
            weights: 策略权重
            
        Returns:
            float: 夏普比率
        """
        portfolio_return = self.calculate_portfolio_return(weights)
        portfolio_volatility = self.calculate_portfolio_volatility(weights)
        
        if portfolio_volatility == 0:
            return 0
        
        sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_volatility
        return sharpe_ratio
    
    def optimize_sharpe_ratio(self) -> Dict[str, float]:
        """
        优化投资组合以最大化夏普比率
        
        Returns:
            Dict: 最优权重
        """
        strategy_names = list(self.strategies.keys())
        n = len(strategy_names)
        
        # 目标函数：最小化负的夏普比率（等同于最大化夏普比率）
        def objective(weights):
            weight_dict = dict(zip(strategy_names, weights))
            return -self.calculate_sharpe_ratio(weight_dict)
        
        # 约束条件：权重和为1
        constraints = [{
            'type': 'eq',
            'fun': lambda weights: np.sum(weights) - 1
        }]
        
        # 边界条件：权重在0到1之间
        bounds = [(0, 1) for _ in range(n)]
        
        # 初始猜测
        initial_weights = np.ones(n) / n
        
        # 优化
        result = minimize(
            objective,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        if result.success:
            optimal_weights = dict(zip(strategy_names, result.x))
            logger.info(f"夏普比率优化完成，最优权重: {optimal_weights}")
            return optimal_weights
        else:
            logger.error(f"夏普比率优化失败: {result.message}")
            return dict(zip(strategy_names, initial_weights))
    
    def optimize_risk_parity(self) -> Dict[str, float]:
        """
        优化投资组合以实现风险平价
        
        Returns:
            Dict: 最优权重
        """
        strategy_names = list(self.strategies.keys())
        n = len(strategy_names)
        
        # 目标函数：最小化风险贡献的标准差
        def objective(weights):
            weight_dict = dict(zip(strategy_names, weights))
            portfolio_volatility = self.calculate_portfolio_volatility(weight_dict)
            
            # 计算每个策略的风险贡献
            risk_contributions = []
            for i, strategy in enumerate(strategy_names):
                weight = weights[i]
                vol = self.strategies[strategy]['volatility']
                correlation = np.array([
                    self.correlation_matrix.get(strategy, {}).get(s, 0)
                    for s in strategy_names
                ])
                risk_contribution = weight * vol * np.dot(weights, np.array([
                    self.strategies[s]['volatility'] for s in strategy_names
                ]) * correlation) / portfolio_volatility
                risk_contributions.append(risk_contribution)
            
            # 计算风险贡献的标准差
            return np.std(risk_contributions)
        
        # 约束条件：权重和为1
        constraints = [{
            'type': 'eq',
            'fun': lambda weights: np.sum(weights) - 1
        }]
        
        # 边界条件：权重在0到1之间
        bounds = [(0, 1) for _ in range(n)]
        
        # 初始猜测
        initial_weights = np.ones(n) / n
        
        # 优化
        result = minimize(
            objective,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        if result.success:
            optimal_weights = dict(zip(strategy_names, result.x))
            logger.info(f"风险平价优化完成，最优权重: {optimal_weights}")
            return optimal_weights
        else:
            logger.error(f"风险平价优化失败: {result.message}")
            return dict(zip(strategy_names, initial_weights))
    
    def optimize_return_for_risk(self, target_risk: float) -> Dict[str, float]:
        """
        在给定风险水平下最大化收益
        
        Args:
            target_risk: 目标风险水平
            
        Returns:
            Dict: 最优权重
        """
        strategy_names = list(self.strategies.keys())
        n = len(strategy_names)
        
        # 目标函数：最大化收益率
        def objective(weights):
            weight_dict = dict(zip(strategy_names, weights))
            return -self.calculate_portfolio_return(weight_dict)
        
        # 约束条件：权重和为1，波动率不超过目标风险
        constraints = [
            {
                'type': 'eq',
                'fun': lambda weights: np.sum(weights) - 1
            },
            {
                'type': 'ineq',
                'fun': lambda weights:
                    target_risk - self.calculate_portfolio_volatility(dict(zip(strategy_names, weights)))
            }
        ]
        
        # 边界条件：权重在0到1之间
        bounds = [(0, 1) for _ in range(n)]
        
        # 初始猜测
        initial_weights = np.ones(n) / n
        
        # 优化
        result = minimize(
            objective,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        if result.success:
            optimal_weights = dict(zip(strategy_names, result.x))
            logger.info(f"风险约束下的收益优化完成，最优权重: {optimal_weights}")
            return optimal_weights
        else:
            logger.error(f"风险约束下的收益优化失败: {result.message}")
            return dict(zip(strategy_names, initial_weights))
    
    def generate_efficient_frontier(self, points: int = 20) -> Dict[str, List[float]]:
        """
        生成有效前沿
        
        Args:
            points: 有效前沿上的点数量
            
        Returns:
            Dict: 有效前沿数据
        """
        returns = []
        volatilities = []
        weights_list = []
        
        # 计算最小风险组合
        min_risk_weights = self.optimize_min_risk()
        min_risk_volatility = self.calculate_portfolio_volatility(min_risk_weights)
        min_risk_return = self.calculate_portfolio_return(min_risk_weights)
        
        # 计算最大夏普比率组合
        max_sharpe_weights = self.optimize_sharpe_ratio()
        max_sharpe_volatility = self.calculate_portfolio_volatility(max_sharpe_weights)
        max_sharpe_return = self.calculate_portfolio_return(max_sharpe_weights)
        
        # 生成风险范围
        risk_range = np.linspace(min_risk_volatility, max_sharpe_volatility * 1.5, points)
        
        for risk in risk_range:
            weights = self.optimize_return_for_risk(risk)
            portfolio_return = self.calculate_portfolio_return(weights)
            portfolio_volatility = self.calculate_portfolio_volatility(weights)
            
            returns.append(portfolio_return)
            volatilities.append(portfolio_volatility)
            weights_list.append(weights)
        
        efficient_frontier = {
            'returns': returns,
            'volatilities': volatilities,
            'weights': weights_list
        }
        
        logger.info(f"有效前沿生成完成，包含 {points} 个点")
        return efficient_frontier
    
    def optimize_min_risk(self) -> Dict[str, float]:
        """
        优化投资组合以最小化风险
        
        Returns:
            Dict: 最优权重
        """
        strategy_names = list(self.strategies.keys())
        n = len(strategy_names)
        
        # 目标函数：最小化波动率
        def objective(weights):
            weight_dict = dict(zip(strategy_names, weights))
            return self.calculate_portfolio_volatility(weight_dict)
        
        # 约束条件：权重和为1
        constraints = [{
            'type': 'eq',
            'fun': lambda weights: np.sum(weights) - 1
        }]
        
        # 边界条件：权重在0到1之间
        bounds = [(0, 1) for _ in range(n)]
        
        # 初始猜测
        initial_weights = np.ones(n) / n
        
        # 优化
        result = minimize(
            objective,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        if result.success:
            optimal_weights = dict(zip(strategy_names, result.x))
            logger.info(f"最小风险优化完成，最优权重: {optimal_weights}")
            return optimal_weights
        else:
            logger.error(f"最小风险优化失败: {result.message}")
            return dict(zip(strategy_names, initial_weights))
    
    def backtest_portfolio(self, weights: Dict[str, float], historical_returns: Dict[str, List[float]]) -> Dict[str, Any]:
        """
        回测投资组合
        
        Args:
            weights: 策略权重
            historical_returns: 每个策略的历史收益率
            
        Returns:
            Dict: 回测结果
        """
        # 计算投资组合的历史收益率
        portfolio_returns = []
        for i in range(len(list(historical_returns.values())[0])):
            portfolio_return = 0
            for strategy_name, weight in weights.items():
                portfolio_return += weight * historical_returns[strategy_name][i]
            portfolio_returns.append(portfolio_return)
        
        # 计算回测指标
        total_return = np.prod([1 + r for r in portfolio_returns]) - 1
        volatility = np.std(portfolio_returns) * np.sqrt(252)
        sharpe_ratio = (np.mean(portfolio_returns) * 252 - self.risk_free_rate) / volatility
        
        # 计算最大回撤
        cumulative_returns = np.cumprod([1 + r for r in portfolio_returns])
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdowns = (cumulative_returns - running_max) / running_max
        max_drawdown = abs(np.min(drawdowns))
        
        backtest_result = {
            'total_return': total_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'cumulative_returns': cumulative_returns.tolist(),
            'drawdowns': drawdowns.tolist()
        }
        
        logger.info(f"投资组合回测完成，总收益: {total_return:.4f}, 波动率: {volatility:.4f}, 夏普比率: {sharpe_ratio:.4f}, 最大回撤: {max_drawdown:.4f}")
        return backtest_result
    
    def set_risk_free_rate(self, risk_free_rate: float):
        """
        设置无风险利率
        
        Args:
            risk_free_rate: 无风险利率
        """
        self.risk_free_rate = risk_free_rate
        logger.info(f"无风险利率已设置为: {risk_free_rate}")
