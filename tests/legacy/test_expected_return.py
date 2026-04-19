#!/usr/bin/env python3
# 测试修改后的预期收益率计算逻辑

def calculate_expected_return(side, order_price, current_price):
    """计算预期收益率"""
    if side == "buy":
        # 做多：预期价格上涨，订单价格低于当前价格时收益为正
        expected_return = (current_price - order_price) / order_price
    else:  # sell
        # 做空：预期价格下跌，订单价格高于当前价格时收益为正
        expected_return = (order_price - current_price) / order_price
    
    # 确保收益率为正数
    expected_return = max(0, expected_return)
    
    return expected_return

# 测试用例
current_price = 69000.0

# 测试做多
print("测试做多:")
print(f"当前价格: {current_price} USDT")
print(f"订单价格 68000 USDT, 预期收益率: {calculate_expected_return('buy', 68000, current_price):.4f} ({calculate_expected_return('buy', 68000, current_price)*100:.2f}%)")
print(f"订单价格 69000 USDT, 预期收益率: {calculate_expected_return('buy', 69000, current_price):.4f} ({calculate_expected_return('buy', 69000, current_price)*100:.2f}%)")
print(f"订单价格 70000 USDT, 预期收益率: {calculate_expected_return('buy', 70000, current_price):.4f} ({calculate_expected_return('buy', 70000, current_price)*100:.2f}%)")

# 测试做空
print("\n测试做空:")
print(f"当前价格: {current_price} USDT")
print(f"订单价格 68000 USDT, 预期收益率: {calculate_expected_return('sell', 68000, current_price):.4f} ({calculate_expected_return('sell', 68000, current_price)*100:.2f}%)")
print(f"订单价格 69000 USDT, 预期收益率: {calculate_expected_return('sell', 69000, current_price):.4f} ({calculate_expected_return('sell', 69000, current_price)*100:.2f}%)")
print(f"订单价格 70000 USDT, 预期收益率: {calculate_expected_return('sell', 70000, current_price):.4f} ({calculate_expected_return('sell', 70000, current_price)*100:.2f}%)")
