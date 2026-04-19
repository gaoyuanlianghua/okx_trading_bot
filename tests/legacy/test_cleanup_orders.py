#!/usr/bin/env python3
"""
测试订单清理功能
"""

import asyncio
from scripts.schedule_api_logs import APILogScheduler

async def test_cleanup_orders():
    # 初始化API日志调度器
    scheduler = APILogScheduler()
    
    # 模拟有未完成的订单
    scheduler.pending_orders = ['test_order_id_1', 'test_order_id_2']
    print(f"清理前的未完成订单: {scheduler.pending_orders}")
    
    # 清理已完成的订单
    await scheduler._cleanup_completed_orders()
    print(f"清理后的未完成订单: {scheduler.pending_orders}")
    
    # 测试获取持仓信息
    from core.utils.profit_growth_manager import profit_growth_manager
    profit_growth_manager.sync_with_api()
    stats = profit_growth_manager.get_stats()
    print(f"持仓状态: {stats['position_type']}")
    print(f"平均买入价格: {stats['avg_buy_price']}")
    print(f"平均卖出价格: {stats['avg_sell_price']}")

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_cleanup_orders())
    loop.close()
