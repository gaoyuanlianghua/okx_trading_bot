#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能体管理器
负责管理不同的智能体，协调智能体之间的通信
"""

import asyncio
from typing import Dict, Any, List, Optional
from core.api.api_manager import APIManager


class AgentManager:
    """智能体管理器"""
    
    def __init__(self, api_manager: APIManager):
        self.api_manager = api_manager
        self.agents = {}
        self.register_agents()
    
    def register_agents(self):
        """注册智能体"""
        try:
            # 确保API客户端已经初始化
            if not self.api_manager.rest_client:
                print("API客户端未初始化，尝试初始化...")
                # 尝试初始化API客户端
                self.api_manager._initialize_client()
                if not self.api_manager.rest_client:
                    print("API客户端初始化失败，无法注册智能体")
                    # 注册失败，使用占位智能体
                    self.agents['coordinator'] = None
                    self.agents['order'] = None
                    self.agents['account_sync'] = None
                    return
            
            # 注册不同的智能体
            from core.agents.coordinator_agent import CoordinatorAgent
            from core.agents.order_agent import OrderAgent
            from core.agents.account_sync_agent import AccountSyncAgent
            from core.agents.base_agent import AgentConfig
            
            # 为每个智能体创建单独的配置
            coordinator_config = AgentConfig(name="Coordinator")
            order_config = AgentConfig(name="Order")
            account_sync_config = AgentConfig(name="AccountSync")
            
            # 为每个智能体提供正确的参数
            self.agents['coordinator'] = CoordinatorAgent(coordinator_config)
            self.agents['order'] = OrderAgent(order_config, rest_client=self.api_manager.rest_client)
            self.agents['account_sync'] = AccountSyncAgent(account_sync_config, rest_client=self.api_manager.rest_client)
            
            print(f"已注册 {len(self.agents)} 个智能体")
        except Exception as e:
            print(f"注册智能体失败: {e}")
            import traceback
            traceback.print_exc()
            # 如果注册失败，使用占位智能体
            self.agents['coordinator'] = None
            self.agents['order'] = None
            self.agents['account_sync'] = None
    
    async def start_agents(self):
        """启动所有智能体"""
        for agent_name, agent in self.agents.items():
            if agent and hasattr(agent, 'start'):
                try:
                    # 检查智能体是否有stop方法，如果有，先停止
                    if hasattr(agent, 'stop'):
                        try:
                            await agent.stop()
                        except Exception as e:
                            print(f"停止智能体 {agent_name} 失败: {e}")
                    
                    # 启动智能体
                    await agent.start()
                    print(f"智能体 {agent_name} 启动成功")
                    
                    # 为智能体注册消息处理器
                    if hasattr(agent, 'process_api_data'):
                        # 注册消息处理器，处理所有类型的消息
                        async def message_handler(message):
                            try:
                                # 从消息中提取数据类型和数据
                                data_type = message.get('type', 'unknown')
                                data = message.get('data', {})
                                await agent.process_api_data(data_type, data)
                            except Exception as e:
                                print(f"智能体 {agent_name} 处理消息失败: {e}")
                        
                        # 为不同类型的消息注册处理器
                        self.api_manager.register_message_handler(agent_name, 'balance', message_handler)
                        self.api_manager.register_message_handler(agent_name, 'positions', message_handler)
                        self.api_manager.register_message_handler(agent_name, 'ticker', message_handler)
                        self.api_manager.register_message_handler(agent_name, 'orders', message_handler)
                        self.api_manager.register_message_handler(agent_name, 'order_placed', message_handler)
                        self.api_manager.register_message_handler(agent_name, 'order_cancelled', message_handler)
                        self.api_manager.register_message_handler(agent_name, 'order_error', message_handler)
                        print(f"为智能体 {agent_name} 注册消息处理器成功")
                except Exception as e:
                    print(f"智能体 {agent_name} 启动失败: {e}")
                    import traceback
                    traceback.print_exc()
    
    async def _start_agents(self):
        """启动所有智能体"""
        for agent_name, agent in self.agents.items():
            if agent and hasattr(agent, 'start'):
                try:
                    await agent.start()
                    print(f"智能体 {agent_name} 启动成功")
                except Exception as e:
                    print(f"智能体 {agent_name} 启动失败: {e}")
                    import traceback
                    traceback.print_exc()
    
    def get_agent(self, agent_name: str):
        """获取智能体"""
        return self.agents.get(agent_name)
    
    async def distribute_api_data(self, data_type: str, data: Dict[str, Any]):
        """分发API数据给不同的智能体"""
        # 使用 API 管理器的消息分发功能
        await self.api_manager.distribute_message(data_type, data)
        
        # 同时保持原来的直接分发方式，确保兼容性
        for agent_name, agent in self.agents.items():
            try:
                if hasattr(agent, 'process_api_data'):
                    await agent.process_api_data(data_type, data)
            except Exception as e:
                print(f"分发API数据给智能体 {agent_name} 失败: {e}")
    
    async def process_agent_request(self, agent_name: str, request_type: str, **kwargs):
        """处理智能体的请求"""
        agent = self.get_agent(agent_name)
        if not agent:
            print(f"智能体 {agent_name} 不存在")
            return None
        
        try:
            if request_type == 'get_account_balance':
                return await self.api_manager.get_account_balance()
            elif request_type == 'get_positions':
                return await self.api_manager.get_positions()
            elif request_type == 'get_ticker':
                instrument_id = kwargs.get('instrument_id', 'BTC-USDT')
                return await self.api_manager.get_ticker(instrument_id)
            elif request_type == 'get_orders_pending':
                return await self.api_manager.get_orders_pending()
            elif request_type == 'place_order':
                return await self.api_manager.place_order(**kwargs)
            elif request_type == 'cancel_order':
                instrument_id = kwargs.get('instrument_id', 'BTC-USDT')
                order_id = kwargs.get('order_id')
                if not order_id:
                    print("订单ID不能为空")
                    return False
                return await self.api_manager.cancel_order(instrument_id, order_id)
            else:
                print(f"未知的请求类型: {request_type}")
                return None
        except Exception as e:
            print(f"处理智能体请求失败: {e}")
            return None
    
    async def run_all_agents(self):
        """运行所有智能体"""
        tasks = []
        for agent_name, agent in self.agents.items():
            if hasattr(agent, 'run'):
                tasks.append(agent.run())
        
        if tasks:
            await asyncio.gather(*tasks)
    
    def get_api_timestamp(self) -> Optional[float]:
        """获取API时间戳"""
        return self.api_manager.get_api_timestamp()
