#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动力学策略测试脚本
用于测试原子核互反动力学策略的实盘交易功能
"""

import asyncio
import json
import logging
from datetime import datetime
from strategies.dynamics_strategy import DynamicsStrategy
from okx_api_client import OKXAPIClient

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/test_dynamics_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def test_dynamics_strategy():
    """测试动力学策略"""
    logger.info("🚀 开始测试动力学策略")
    
    try:
        # 加载配置文件
        config_path = "d:\\Projects\\okx_trading_bot\\config\\okx_config.json"
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # 初始化API客户端
        api_client = OKXAPIClient(
            api_key=config['api']['api_key'],
            api_secret=config['api']['api_secret'],
            passphrase=config['api']['passphrase'],
            is_test=config['api']['is_test'],
            api_url=config['api']['api_url']
        )
        
        # 初始化动力学策略
        dynamics_config = config.get('dynamics_strategy', {})
        strategy = DynamicsStrategy(api_client, dynamics_config)
        
        # 测试参数优化
        logger.info("🔄 测试参数优化...")
        training_data = strategy.generate_training_data(50)
        strategy.optimize_dynamics_params(training_data)
        
        # 测试参数降维
        logger.info("🔄 测试参数降维...")
        strategy.reduce_param_set()
        
        # 测试激励轨迹生成
        logger.info("📈 测试激励轨迹生成...")
        trajectory = [strategy.excitation_trajectory(t) for t in range(10)]
        logger.info(f"激励轨迹示例: {trajectory[:5]}")
        
        # 测试获取市场数据
        logger.info("📊 测试获取市场数据...")
        current_price = await strategy.get_market_data('BTC-USDT-SWAP')
        logger.info(f"当前BTC价格: {current_price}")
        
        # 测试信号计算
        logger.info("📡 测试信号计算...")
        if len(strategy.price_history) > strategy.spring_params['lookback_period']:
            signal_strength = strategy.calculate_signal_strength()
            logger.info(f"信号强度: {signal_strength}")
        
        # 测试运行实盘策略（5个周期）
        logger.info("🧪 测试实盘策略运行...")
        for i in range(5):
            logger.info(f"\n--- 周期 {i+1}/5 ---")
            current_price = await strategy.get_market_data('BTC-USDT-SWAP')
            if current_price:
                signal_strength = strategy.calculate_signal_strength()
                logger.info(f"信号强度: {signal_strength}")
                
                # 只在信号强度足够大时执行交易
                if abs(signal_strength) > 0.8:
                    await strategy.execute_trade('BTC-USDT-SWAP', signal_strength)
            await asyncio.sleep(2)  # 缩短间隔用于测试
        
        logger.info("✅ 动力学策略测试完成")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        asyncio.run(test_dynamics_strategy())
    except KeyboardInterrupt:
        logger.info("🛑 测试手动终止")
