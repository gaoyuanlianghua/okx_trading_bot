#!/usr/bin/env python3
"""
重置初始权益脚本
"""

import sys
sys.path.append("/root/okx_trading_bot")

from core.agents.order_agent import OrderAgent
from core.agents.base_agent import AgentConfig
import asyncio

async def reset_initial_balance():
    """重置初始权益"""
    print("开始重置初始权益...")
    
    # 创建订单智能体配置
    order_config = AgentConfig(name="Order", description="订单管理智能体")
    
    # 创建订单智能体
    order_agent = OrderAgent(
        config=order_config,
        exchange_name="okx",
        api_key="c6637a95-ca47-4e23-8c0f-c1803d71b392",
        api_secret="528F306447BAFA6CBB15579522473A95",
        passphrase="Gy528329818.123",
        is_test=False
    )
    
    # 初始化智能体
    await order_agent._initialize()
    
    try:
        # 获取当前账户余额
        balance = await order_agent.rest_client.get_account_balance()
        
        if balance and isinstance(balance, dict):
            # 从顶级字段获取账户总权益
            total_eq_str = balance.get('totalEq', 0)
            try:
                usdt_total_eq = float(total_eq_str)
            except (ValueError, TypeError):
                usdt_total_eq = 0.0
            
            # 重置初始权益为当前总权益
            order_agent._initial_balance = usdt_total_eq
            
            print(f"✅ 初始权益已重置为: {usdt_total_eq:.6f} USDT")
            print(f"当前账户总权益: {usdt_total_eq:.6f} USDT")
            
            # 计算新的收益率
            total_return = 0.0  # 重置后收益率为0
            print(f"重置后收益率: {total_return * 100:.2f}%")
            
        else:
            print("❌ 无法获取账户余额")
            
    except Exception as e:
        print(f"❌ 重置初始权益出错: {e}")
    finally:
        # 清理
        await order_agent._cleanup()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(reset_initial_balance())
    loop.close()
