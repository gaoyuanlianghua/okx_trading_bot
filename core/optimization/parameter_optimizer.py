"""
智能参数优化器

基于历史数据和实时市场情况自动优化策略参数
"""

import time
import numpy as np
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
import asyncio

from core.utils.logger import get_logger
from core.backtesting.strategy_backtester import StrategyBacktester

logger = get_logger(__name__)


@dataclass
class OptimizationResult:
    """优化结果"""
    best_params: Dict[str, Any]
    best_score: float
    iterations: int
    execution_time: float
    history: List[Dict[str, Any]]


class ParameterOptimizer:
    """
    智能参数优化器
    
    基于历史数据和实时市场情况自动优化策略参数
    """
    
    def __init__(self, strategy_class, backtester: StrategyBacktester = None):
        """
        初始化参数优化器
        
        Args:
            strategy_class: 策略类
            backtester: 回测器
        """
        self.strategy_class = strategy_class
        self.backtester = backtester or StrategyBacktester()
        self.optimization_history = []
    
    def optimize_parameters(self, 
                           historical_data: List[Dict], 
                           param_space: Dict[str, List],
                           objective_function: Callable = None,
                           max_iterations: int = 100,
                           method: str = "grid") -> OptimizationResult:
        """
        优化策略参数
        
        Args:
            historical_data: 历史数据
            param_space: 参数空间
            objective_function: 目标函数
            max_iterations: 最大迭代次数
            method: 优化方法 (grid, random, bayesian)
            
        Returns:
            OptimizationResult: 优化结果
        """
        start_time = time.time()
        history = []
        best_score = -float('inf')
        best_params = {}
        
        # 生成参数组合
        param_combinations = self._generate_param_combinations(param_space, method, max_iterations)
        
        # 评估每个参数组合
        for i, params in enumerate(param_combinations):
            if i >= max_iterations:
                break
            
            # 创建策略实例
            strategy = self.strategy_class(config={"dynamics": params})
            
            # 回测策略
            result = self.backtester.backtest(strategy, historical_data)
            
            # 计算得分
            score = self._calculate_score(result, objective_function)
            
            # 记录结果
            history.append({
                "params": params,
                "score": score,
                "result": result
            })
            
            # 更新最佳参数
            if score > best_score:
                best_score = score
                best_params = params
                logger.info(f"找到更好的参数组合: {params}, 得分: {score}")
            
            # 打印进度
            if (i + 1) % 10 == 0:
                logger.info(f"优化进度: {i + 1}/{min(len(param_combinations), max_iterations)}")
        
        execution_time = time.time() - start_time
        
        # 保存优化历史
        self.optimization_history.append({
            "timestamp": time.time(),
            "method": method,
            "iterations": len(history),
            "best_params": best_params,
            "best_score": best_score,
            "execution_time": execution_time
        })
        
        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            iterations=len(history),
            execution_time=execution_time,
            history=history
        )
    
    def _generate_param_combinations(self, param_space: Dict[str, List], method: str, max_iterations: int) -> List[Dict[str, Any]]:
        """
        生成参数组合
        
        Args:
            param_space: 参数空间
            method: 优化方法
            max_iterations: 最大迭代次数
            
        Returns:
            List[Dict[str, Any]]: 参数组合列表
        """
        if method == "grid":
            return self._generate_grid_combinations(param_space, max_iterations)
        elif method == "random":
            return self._generate_random_combinations(param_space, max_iterations)
        elif method == "bayesian":
            return self._generate_bayesian_combinations(param_space, max_iterations)
        else:
            raise ValueError(f"不支持的优化方法: {method}")
    
    def _generate_grid_combinations(self, param_space: Dict[str, List], max_iterations: int) -> List[Dict[str, Any]]:
        """
        生成网格参数组合
        
        Args:
            param_space: 参数空间
            max_iterations: 最大迭代次数
            
        Returns:
            List[Dict[str, Any]]: 参数组合列表
        """
        import itertools
        
        # 获取所有参数的可能值
        param_values = [param_space[key] for key in param_space]
        param_names = list(param_space.keys())
        
        # 生成所有组合
        combinations = []
        for values in itertools.product(*param_values):
            if len(combinations) >= max_iterations:
                break
            params = dict(zip(param_names, values))
            combinations.append(params)
        
        return combinations
    
    def _generate_random_combinations(self, param_space: Dict[str, List], max_iterations: int) -> List[Dict[str, Any]]:
        """
        生成随机参数组合
        
        Args:
            param_space: 参数空间
            max_iterations: 最大迭代次数
            
        Returns:
            List[Dict[str, Any]]: 参数组合列表
        """
        combinations = []
        param_names = list(param_space.keys())
        
        for _ in range(max_iterations):
            params = {}
            for name in param_names:
                values = param_space[name]
                if isinstance(values, list):
                    params[name] = np.random.choice(values)
                elif isinstance(values, tuple) and len(values) == 2:
                    # 连续参数范围
                    min_val, max_val = values
                    params[name] = np.random.uniform(min_val, max_val)
            combinations.append(params)
        
        return combinations
    
    def _generate_bayesian_combinations(self, param_space: Dict[str, List], max_iterations: int) -> List[Dict[str, Any]]:
        """
        生成贝叶斯优化参数组合
        
        Args:
            param_space: 参数空间
            max_iterations: 最大迭代次数
            
        Returns:
            List[Dict[str, Any]]: 参数组合列表
        """
        # 尝试导入bayesian-optimization库
        try:
            from bayes_opt import BayesianOptimization
        except ImportError:
            logger.warning("bayesian-optimization库未安装，使用随机搜索代替")
            return self._generate_random_combinations(param_space, max_iterations)
        
        # 构建参数边界
        pbounds = {}
        for name, values in param_space.items():
            if isinstance(values, tuple) and len(values) == 2:
                pbounds[name] = values
            elif isinstance(values, list) and len(values) > 1:
                # 对于离散参数，使用最小值和最大值作为边界
                pbounds[name] = (min(values), max(values))
            else:
                pbounds[name] = (0, 1)  # 默认边界
        
        # 定义目标函数
        def target(**params):
            # 对于离散参数，四舍五入到最近的可能值
            for name in param_space:
                if isinstance(param_space[name], list):
                    values = param_space[name]
                    params[name] = min(values, key=lambda x: abs(x - params[name]))
            
            # 创建策略实例
            strategy = self.strategy_class(config={"dynamics": params})
            
            # 回测策略
            result = self.backtester.backtest(strategy, [])  # 这里需要实际的历史数据
            
            # 计算得分
            return self._calculate_score(result)
        
        # 运行贝叶斯优化
        optimizer = BayesianOptimization(
            f=target,
            pbounds=pbounds,
            random_state=42,
        )
        
        optimizer.maximize(
            init_points=10,
            n_iter=max_iterations - 10,
        )
        
        # 提取最佳参数
        combinations = []
        for res in optimizer.res:
            params = res["params"]
            # 对于离散参数，四舍五入到最近的可能值
            for name in param_space:
                if isinstance(param_space[name], list):
                    values = param_space[name]
                    params[name] = min(values, key=lambda x: abs(x - params[name]))
            combinations.append(params)
        
        return combinations
    
    def _calculate_score(self, result: Dict[str, Any], objective_function: Callable = None) -> float:
        """
        计算策略得分
        
        Args:
            result: 回测结果
            objective_function: 目标函数
            
        Returns:
            float: 得分
        """
        if objective_function:
            return objective_function(result)
        
        # 默认目标函数：最大化夏普比率，同时考虑最大回撤
        sharpe_ratio = result.get("sharpe_ratio", 0)
        max_drawdown = result.get("max_drawdown", 1)
        win_rate = result.get("win_rate", 0)
        
        # 计算综合得分
        score = sharpe_ratio * 0.5 + (1 - max_drawdown) * 0.3 + win_rate * 0.2
        
        return score
    
    async def optimize_parameters_async(self, 
                                       historical_data: List[Dict], 
                                       param_space: Dict[str, List],
                                       objective_function: Callable = None,
                                       max_iterations: int = 100,
                                       method: str = "grid") -> OptimizationResult:
        """
        异步优化策略参数
        
        Args:
            historical_data: 历史数据
            param_space: 参数空间
            objective_function: 目标函数
            max_iterations: 最大迭代次数
            method: 优化方法
            
        Returns:
            OptimizationResult: 优化结果
        """
        # 在线程池中执行同步优化
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self.optimize_parameters,
            historical_data,
            param_space,
            objective_function,
            max_iterations,
            method
        )
        return result
    
    def get_optimization_history(self) -> List[Dict[str, Any]]:
        """
        获取优化历史
        
        Returns:
            List[Dict[str, Any]]: 优化历史
        """
        return self.optimization_history
    
    def analyze_parameter_importance(self, history: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        分析参数重要性
        
        Args:
            history: 优化历史
            
        Returns:
            Dict[str, float]: 参数重要性
        """
        if not history:
            return {}
        
        # 提取参数和得分
        params = list(history[0]["params"].keys())
        importance = {param: 0.0 for param in params}
        
        # 计算每个参数对得分的影响
        for param in params:
            # 按参数值分组，计算得分的方差
            param_values = {}
            for item in history:
                value = item["params"][param]
                if value not in param_values:
                    param_values[value] = []
                param_values[value].append(item["score"])
            
            # 计算方差
            if len(param_values) > 1:
                variances = []
                for scores in param_values.values():
                    if len(scores) > 1:
                        variances.append(np.var(scores))
                if variances:
                    importance[param] = np.mean(variances)
        
        # 归一化重要性
        total = sum(importance.values())
        if total > 0:
            for param in importance:
                importance[param] /= total
        
        return importance


# 全局参数优化器实例
parameter_optimizer = ParameterOptimizer(None)