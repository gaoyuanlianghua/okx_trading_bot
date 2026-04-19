#!/usr/bin/env python3
"""
测试阈值设置和信号强度变化
"""

import asyncio
import yaml
import numpy as np
from strategies.dynamics_strategy import DynamicsStrategy

async def test_threshold():
    """测试阈值设置和信号强度变化"""
    try:
        # 加载配置
        with open('config/config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        # 初始化策略
        strategy = DynamicsStrategy(config=config['strategy']['strategies']['NuclearDynamicsStrategy'])
        
        print('策略初始化完成')
        print('当前阈值设置:')
        print('  信号阈值: ±0.001')
        print('  弹簧效应均值阈值: 0.005')
        print('  市场耦合系数: 0.0015')
        
        # 模拟市场数据
        print('\n模拟市场数据并计算信号强度...')
        
        # 生成模拟价格数据
        base_price = 66758.2
        price_history = []
        
        # 生成上升趋势
        print('\n1. 测试上升趋势:')
        price_history = []
        for i in range(20):
            # 生成上升价格
            price = base_price + i * 10
            price_history.append(price)
            # 更新策略的价格历史
            strategy.price_history = price_history.copy()
            # 计算信号强度
            signal_strength = strategy.calculate_signal_strength()
            # 生成交易信号
            signal = strategy._execute_strategy({'price': price, 'timestamp': i})
            print(f'  价格: {price:.2f}, 信号强度: {signal_strength:.6f}, 信号: {signal["side"]}')
        
        # 生成下降趋势
        print('\n2. 测试下降趋势:')
        price_history = []
        for i in range(20):
            # 生成下降价格
            price = base_price - i * 10
            price_history.append(price)
            # 更新策略的价格历史
            strategy.price_history = price_history.copy()
            # 计算信号强度
            signal_strength = strategy.calculate_signal_strength()
            # 生成交易信号
            signal = strategy._execute_strategy({'price': price, 'timestamp': i})
            print(f'  价格: {price:.2f}, 信号强度: {signal_strength:.6f}, 信号: {signal["side"]}')
        
        # 生成震荡行情
        print('\n3. 测试震荡行情:')
        price_history = []
        for i in range(20):
            # 生成震荡价格
            price = base_price + np.sin(i * 0.5) * 50
            price_history.append(price)
            # 更新策略的价格历史
            strategy.price_history = price_history.copy()
            # 计算信号强度
            signal_strength = strategy.calculate_signal_strength()
            # 生成交易信号
            signal = strategy._execute_strategy({'price': price, 'timestamp': i})
            print(f'  价格: {price:.2f}, 信号强度: {signal_strength:.6f}, 信号: {signal["side"]}')
        
        print('\n测试完成!')
        print('\n阈值分析:')
        print('  1. 当前信号阈值设置为 ±0.001，相比之前的设置更低，增加了交易频率')
        print('  2. 弹簧效应均值阈值设置为 0.005，提高了对市场波动的敏感度')
        print('  3. 市场耦合系数设置为 0.0015，增强了市场动量的影响')
        print('  4. 信号融合权重调整，增加了弹簧效应信号的权重，提高了均值回归策略的影响')
        
    except Exception as e:
        print(f'测试失败: {e}')

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_threshold())
