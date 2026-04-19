#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查当前订单状态
"""

import asyncio
import os
import sys

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from scripts.schedule_api_logs import APILogScheduler

async def main():
    """主函数"""
    # 创建API日志调度器
    scheduler = APILogScheduler()
    
    # 获取当前未成交订单
    print("获取当前未成交订单...")
    orders = await scheduler.api_manager.get_orders_pending()
    print("当前未成交订单:", orders)
    print("未成交订单数量:", len(orders.get('orders', [])) if 'orders' in orders else 0)
    
    # 关闭API客户端
    await scheduler.api_manager.rest_client.session.close()

if __name__ == "__main__":
    # 运行主函数
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
