import asyncio
import json
import time
import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Optional, Any
from core.utils.logger import get_logger
from core.analysis.technical_analyzer import TechnicalAnalyzer

logger = get_logger(__name__)

class EnhancedBacktester:
    def __init__(self):
        self.technical_analyzer = TechnicalAnalyzer()
        self.results = {}
    
    async def backtest_strategy(self, strategy, historical_data: List[Dict], config: Dict = None) -> Dict[str, Any]:
        """
        增强的回测功能
        
        Args:
            strategy: 策略实例
            historical_data: 历史数据
            config: 回测配置
            
        Returns:
            Dict: 回测结果
        """
        if not config:
            config = {
                'initial_balance': 10000.0,
                'fee': 0.001,
                'slippage': 0.0005,
                'risk_per_trade': 0.02,
                'max_positions': 1,
                'enable_visualization': True
            }
        
        start_time = time.time()
        logger.info(f"开始回测: {strategy.name}, 数据点: {len(historical_data)}")
        
        # 初始化回测状态
        balance = config['initial_balance']
        position = 0
        trades = []
        equity_curve = []
        drawdowns = []
        current_drawdown = 0
        max_equity = balance
        
        # 计算技术指标
        prices = [float(item['close']) for item in historical_data]
        high_prices = [float(item['high']) for item in historical_data]
        low_prices = [float(item['low']) for item in historical_data]
        
        # 计算技术指标
        indicators = {
            'rsi': self.technical_analyzer.calculate_rsi(prices),
            'macd': self.technical_analyzer.calculate_macd(prices),
            'bollinger': self.technical_analyzer.calculate_bollinger_bands(prices),
            'stochastic': self.technical_analyzer.calculate_stochastic_oscillator(high_prices, low_prices, prices),
            'atr': self.technical_analyzer.calculate_atr(high_prices, low_prices, prices)
        }
        
        # 执行回测
        for i, data in enumerate(historical_data):
            # 构建市场数据，包含技术指标
            market_data = {
                'price': float(data['close']),
                'high': float(data['high']),
                'low': float(data['low']),
                'volume': float(data.get('volume', 0)),
                'timestamp': data['timestamp'],
                'indicators': {
                    'rsi': indicators['rsi'][i],
                    'macd': indicators['macd']['histogram'][i],
                    'bollinger_upper': indicators['bollinger']['upper'][i],
                    'bollinger_middle': indicators['bollinger']['middle'][i],
                    'bollinger_lower': indicators['bollinger']['lower'][i],
                    'stochastic_k': indicators['stochastic']['k'][i],
                    'stochastic_d': indicators['stochastic']['d'][i],
                    'atr': indicators['atr'][i]
                }
            }
            
            # 执行策略
            signal = strategy.execute(market_data)
            
            # 处理信号
            if signal:
                side = signal.get('side')
                price = signal.get('price', market_data['price'])
                
                # 计算交易量（基于风险百分比）
                risk_amount = balance * config['risk_per_trade']
                position_size = risk_amount / (price * 0.01)  # 假设1%的止损
                
                # 应用滑点
                if side == 'buy':
                    executed_price = price * (1 + config['slippage'])
                else:
                    executed_price = price * (1 - config['slippage'])
                
                # 计算手续费
                fee = executed_price * position_size * config['fee']
                
                # 执行交易
                if side == 'buy' and position == 0:
                    # 开多仓
                    position = position_size
                    balance -= (executed_price * position_size) + fee
                    trades.append({
                        'timestamp': data['timestamp'],
                        'side': 'buy',
                        'price': executed_price,
                        'size': position_size,
                        'fee': fee,
                        'balance': balance,
                        'position': position
                    })
                elif side == 'sell' and position > 0:
                    # 平仓
                    profit = (executed_price * position) - (trades[-1]['price'] * position) - fee
                    balance += (executed_price * position) - fee
                    trades.append({
                        'timestamp': data['timestamp'],
                        'side': 'sell',
                        'price': executed_price,
                        'size': position,
                        'fee': fee,
                        'profit': profit,
                        'balance': balance,
                        'position': 0
                    })
                    position = 0
            
            # 计算当前权益
            if position > 0:
                current_equity = balance + (position * float(data['close']))
            else:
                current_equity = balance
            
            equity_curve.append(current_equity)
            
            # 计算最大回撤
            if current_equity > max_equity:
                max_equity = current_equity
                current_drawdown = 0
            else:
                current_drawdown = (max_equity - current_equity) / max_equity
            
            drawdowns.append(current_drawdown)
        
        # 计算回测指标
        final_balance = equity_curve[-1]
        total_return = (final_balance - config['initial_balance']) / config['initial_balance']
        max_drawdown = max(drawdowns)
        
        # 计算夏普比率（简化计算）
        returns = np.diff(equity_curve) / equity_curve[:-1]
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if len(returns) > 0 else 0
        
        # 计算胜率
        winning_trades = [t for t in trades if t.get('profit', 0) > 0]
        win_rate = len(winning_trades) / len(trades) if trades else 0
        
        # 计算平均盈亏比
        if trades:
            profits = [t.get('profit', 0) for t in trades if t.get('profit', 0) > 0]
            losses = [abs(t.get('profit', 0)) for t in trades if t.get('profit', 0) < 0]
            avg_win = np.mean(profits) if profits else 0
            avg_loss = np.mean(losses) if losses else 1
            profit_factor = avg_win / avg_loss
        else:
            profit_factor = 0
        
        # 生成回测报告
        report = {
            'strategy': strategy.name,
            'initial_balance': config['initial_balance'],
            'final_balance': final_balance,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(trades) - len(winning_trades),
            'equity_curve': equity_curve,
            'drawdown_curve': drawdowns,
            'trades': trades,
            'backtest_duration': time.time() - start_time,
            'data_points': len(historical_data)
        }
        
        # 保存结果
        self.results[strategy.name] = report
        
        # 生成可视化
        if config['enable_visualization']:
            await self._generate_visualization(report, strategy.name)
        
        logger.info(f"回测完成: {strategy.name}, 总收益: {total_return:.2%}, 最大回撤: {max_drawdown:.2%}")
        return report
    
    async def _generate_visualization(self, report: Dict[str, Any], strategy_name: str):
        """
        生成回测可视化
        
        Args:
            report: 回测结果
            strategy_name: 策略名称
        """
        try:
            # 创建图表
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
            
            # 权益曲线
            ax1.plot(report['equity_curve'], label='Equity Curve')
            ax1.set_title(f'{strategy_name} Backtest Results')
            ax1.set_ylabel('Equity')
            ax1.grid(True)
            ax1.legend()
            
            # 回撤曲线
            ax2.plot(report['drawdown_curve'], label='Drawdown', color='red')
            ax2.set_ylabel('Drawdown')
            ax2.set_xlabel('Time')
            ax2.grid(True)
            ax2.legend()
            
            # 保存图表
            filename = f'backtest_{strategy_name}_{int(time.time())}.png'
            plt.savefig(filename)
            plt.close()
            
            logger.info(f"回测可视化已保存: {filename}")
        except Exception as e:
            logger.error(f"生成可视化失败: {e}")
    
    async def backtest_multiple_strategies(self, strategies: List, historical_data: List[Dict], config: Dict = None) -> Dict[str, Dict]:
        """
        回测多个策略
        
        Args:
            strategies: 策略列表
            historical_data: 历史数据
            config: 回测配置
            
        Returns:
            Dict: 每个策略的回测结果
        """
        results = {}
        
        for strategy in strategies:
            result = await self.backtest_strategy(strategy, historical_data, config)
            results[strategy.name] = result
        
        # 生成策略比较报告
        await self._generate_strategy_comparison(results)
        
        return results
    
    async def _generate_strategy_comparison(self, results: Dict[str, Dict]):
        """
        生成策略比较报告
        
        Args:
            results: 多个策略的回测结果
        """
        try:
            # 创建比较数据
            strategy_names = list(results.keys())
            total_returns = [results[s]['total_return'] for s in strategy_names]
            max_drawdowns = [results[s]['max_drawdown'] for s in strategy_names]
            sharpe_ratios = [results[s]['sharpe_ratio'] for s in strategy_names]
            win_rates = [results[s]['win_rate'] for s in strategy_names]
            
            # 创建图表
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
            
            # 总收益比较
            ax1.bar(strategy_names, total_returns)
            ax1.set_title('Total Return')
            ax1.set_ylabel('Return')
            ax1.grid(True)
            
            # 最大回撤比较
            ax2.bar(strategy_names, max_drawdowns)
            ax2.set_title('Max Drawdown')
            ax2.set_ylabel('Drawdown')
            ax2.grid(True)
            
            # 夏普比率比较
            ax3.bar(strategy_names, sharpe_ratios)
            ax3.set_title('Sharpe Ratio')
            ax3.set_ylabel('Ratio')
            ax3.grid(True)
            
            # 胜率比较
            ax4.bar(strategy_names, win_rates)
            ax4.set_title('Win Rate')
            ax4.set_ylabel('Rate')
            ax4.grid(True)
            
            # 调整布局
            plt.tight_layout()
            
            # 保存图表
            filename = f'strategy_comparison_{int(time.time())}.png'
            plt.savefig(filename)
            plt.close()
            
            logger.info(f"策略比较报告已保存: {filename}")
        except Exception as e:
            logger.error(f"生成策略比较报告失败: {e}")
    
    def get_backtest_results(self, strategy_name: Optional[str] = None) -> Dict:
        """
        获取回测结果
        
        Args:
            strategy_name: 策略名称，None表示获取所有策略的结果
            
        Returns:
            Dict: 回测结果
        """
        if strategy_name:
            return self.results.get(strategy_name, {})
        return self.results
    
    def export_results(self, strategy_name: str, format: str = 'json') -> Optional[str]:
        """
        导出回测结果
        
        Args:
            strategy_name: 策略名称
            format: 导出格式，支持json和csv
            
        Returns:
            Optional[str]: 导出文件路径
        """
        if strategy_name not in self.results:
            logger.error(f"策略回测结果不存在: {strategy_name}")
            return None
        
        result = self.results[strategy_name]
        filename = f'backtest_{strategy_name}_{int(time.time())}.{format}'
        
        try:
            if format == 'json':
                with open(filename, 'w') as f:
                    json.dump(result, f, indent=2)
            elif format == 'csv':
                # 导出交易记录
                trades_df = pd.DataFrame(result['trades'])
                trades_df.to_csv(filename, index=False)
            
            logger.info(f"回测结果已导出: {filename}")
            return filename
        except Exception as e:
            logger.error(f"导出回测结果失败: {e}")
            return None
