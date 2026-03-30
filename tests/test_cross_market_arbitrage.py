import asyncio
import time
import random
import sys
import os

# 添加当前目录到导入路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from strategies.cross_market_arbitrage_strategy import CrossMarketArbitrageStrategy

async def test_cross_market_arbitrage():
    """测试跨市场套利策略"""
    print("开始测试跨市场套利策略...")
    
    # 创建策略实例
    config = {
        "arbitrage_threshold": 0.5,
        "max_trade_amount": 10000,
        "min_trade_amount": 100,
        "exchanges": ["okx", "binance", "coinbase"],
        "trading_pairs": ["BTC/USDT", "ETH/USDT"],
        "polling_interval": 0.5,
        "max_position": 0.1,
        "fee_estimate": 0.1,
        "profit_threshold": 0.1
    }
    
    strategy = CrossMarketArbitrageStrategy(config=config)
    
    # 启动策略
    strategy.start()
    
    # 模拟运行一段时间
    print("策略启动，模拟运行30秒...")
    await asyncio.sleep(30)
    
    # 获取策略状态
    status = strategy.get_status()
    print("\n策略状态:")
    print(f"状态: {status['status']}")
    print(f"总交易次数: {status['total_trades']}")
    print(f"性能指标: {status['performance']}")
    print(f"活跃套利: {status['active_arbitrage']}")
    print(f"最近的套利机会: {len(status['recent_opportunities'])}")
    
    # 停止策略
    strategy.stop()
    print("\n策略停止")
    
    # 打印交易日志
    trade_logs = strategy.get_trade_logs()
    print(f"\n交易日志 ({len(trade_logs)}条):")
    for log in trade_logs:
        print(f"时间: {log['timestamp']}, 交易对: {log['inst_id']}, 利润: {log['profit']:.2f}")

async def test_price_detection():
    """测试价格差异检测功能"""
    print("\n\n测试价格差异检测功能...")
    
    # 创建策略实例
    strategy = CrossMarketArbitrageStrategy()
    
    # 模拟价格数据
    strategy.price_cache = {
        "okx": {
            "BTC/USDT": {"price": 45000, "timestamp": time.time()},
            "ETH/USDT": {"price": 3200, "timestamp": time.time()}
        },
        "binance": {
            "BTC/USDT": {"price": 45200, "timestamp": time.time()},
            "ETH/USDT": {"price": 3210, "timestamp": time.time()}
        },
        "coinbase": {
            "BTC/USDT": {"price": 44900, "timestamp": time.time()},
            "ETH/USDT": {"price": 3190, "timestamp": time.time()}
        }
    }
    
    # 测试套利机会检测
    opportunities = await strategy._find_arbitrage_opportunities()
    print(f"检测到 {len(opportunities)} 个套利机会:")
    for opportunity in opportunities:
        print(f"交易对: {opportunity['trading_pair']}, 买入交易所: {opportunity['buy_exchange']}, 卖出交易所: {opportunity['sell_exchange']}, 利润: {opportunity['net_profit_percent']:.2f}%")

async def test_performance_optimization():
    """测试性能优化"""
    print("\n\n测试性能优化...")
    
    # 创建策略实例
    strategy = CrossMarketArbitrageStrategy()
    
    # 测试价格更新性能
    start_time = time.time()
    await strategy._update_price_cache()
    end_time = time.time()
    print(f"价格更新耗时: {end_time - start_time:.4f}秒")
    
    # 测试套利机会检测性能
    start_time = time.time()
    opportunities = await strategy._find_arbitrage_opportunities()
    end_time = time.time()
    print(f"套利机会检测耗时: {end_time - start_time:.4f}秒")
    
    # 测试并行性能
    start_time = time.time()
    tasks = []
    for i in range(10):
        tasks.append(strategy._update_price_cache())
    await asyncio.gather(*tasks)
    end_time = time.time()
    print(f"并行执行10次价格更新耗时: {end_time - start_time:.4f}秒")

if __name__ == "__main__":
    asyncio.run(test_cross_market_arbitrage())
    asyncio.run(test_price_detection())
    asyncio.run(test_performance_optimization())
    print("\n测试完成!")