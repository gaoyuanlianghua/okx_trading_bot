#!/usr/bin/env python3

import sys
sys.path.append('.')

from core.agents.strategy_agent import StrategyAgent
from core.agents.base_agent import AgentConfig
import asyncio

async def check_strategies():
    print("=== 检查策略状态 ===")
    
    # 创建策略智能体实例
    config = AgentConfig(agent_id='test', name='test')
    agent = StrategyAgent(config)
    
    print("初始策略列表:", list(agent._strategies.keys()))
    print("初始活跃策略:", agent._active_strategies)
    
    # 加载默认策略
    print("\n加载默认策略...")
    await agent._load_default_strategies()
    
    print("加载后策略列表:", list(agent._strategies.keys()))
    print("加载后活跃策略:", agent._active_strategies)
    
    # 激活NuclearDynamicsStrategy
    print("\n激活NuclearDynamicsStrategy...")
    result = await agent.activate_strategy('NuclearDynamicsStrategy')
    print("激活结果:", result)
    print("激活后活跃策略:", agent._active_strategies)
    
    # 检查策略是否存在
    if 'NuclearDynamicsStrategy' in agent._strategies:
        print("\n✅ NuclearDynamicsStrategy 存在于策略列表中")
    else:
        print("\n❌ NuclearDynamicsStrategy 不存在于策略列表中")
    
    # 清理
    await agent.stop()
    print("\n检查完成")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(check_strategies())
