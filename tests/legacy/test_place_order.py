#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手动触发测试挂单任务
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
    
    # 手动触发测试挂单任务
    print("手动触发测试挂单任务...")
    await scheduler.place_test_order()
    print("测试挂单任务执行完成")
    
    # 等待撤单任务执行
    print("等待撤单任务执行...")
    await asyncio.sleep(65)  # 等待65秒，确保撤单任务有足够的时间执行
    print("撤单任务执行完成")

if __name__ == "__main__":
    # 运行主函数
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
