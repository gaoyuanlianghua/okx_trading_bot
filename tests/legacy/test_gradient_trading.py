"""
测试梯度交易逻辑
验证0.20%跌幅买入条件
"""

import sys
sys.path.insert(0, '/root/okx_trading_bot')

from core.utils.profit_growth_manager import ProfitGrowthManager

def test_gradient_buy_logic():
    """测试梯度买入逻辑"""
    print("=" * 60)
    print("测试梯度交易买入逻辑")
    print("=" * 60)
    
    # 创建盈利增长管理器
    manager = ProfitGrowthManager(storage_file="./data/test_profit_growth_state.json")
    
    # 模拟上次卖出价格
    last_sell_price = 73000.0
    manager._last_sell_price = last_sell_price
    
    print(f"\n上次卖出价格: {last_sell_price} USDT")
    print(f"最小跌幅要求: 0.20%")
    print("-" * 60)
    
    # 测试不同跌幅情况
    test_cases = [
        (73000.0, "0% 跌幅 - 不应买入"),
        (72950.0, "0.07% 跌幅 - 不应买入"),
        (72900.0, "0.14% 跌幅 - 不应买入"),
        (72854.0, "0.20% 跌幅 - 刚好满足"),
        (72800.0, "0.27% 跌幅 - 应买入"),
        (72500.0, "0.68% 跌幅 - 应买入"),
        (72000.0, "1.37% 跌幅 - 应买入"),
    ]
    
    print("\n测试结果:")
    print("-" * 60)
    
    for current_price, description in test_cases:
        should_buy, reason = manager.should_buy(current_price, last_sell_price)
        status = "✅ 买入" if should_buy else "❌ 不买入"
        print(f"{description}")
        print(f"  当前价格: {current_price} USDT")
        print(f"  结果: {status}")
        print(f"  原因: {reason}")
        print()
    
    print("=" * 60)
    print("测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    test_gradient_buy_logic()
