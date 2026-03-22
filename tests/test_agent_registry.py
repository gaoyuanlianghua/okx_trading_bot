"""
智能体注册表单元测试
"""

import unittest
import threading
from commons.agent_registry import AgentRegistry
from agents.base_agent import BaseAgent


class MockAgent(BaseAgent):
    """测试用的智能体类"""
    
    def __init__(self, agent_id, config=None):
        super().__init__(agent_id, config)
        self.start_called = False
        self.stop_called = False
    
    def start(self):
        super().start()
        self.start_called = True
    
    def stop(self):
        super().stop()
        self.stop_called = True


class TestAgentRegistry(unittest.TestCase):
    """测试智能体注册表功能"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.registry = AgentRegistry()
    
    def test_register_agent(self):
        """测试注册智能体"""
        agent = MockAgent("test_agent")
        result = self.registry.register_agent(agent)
        
        # 验证注册成功
        self.assertTrue(result)
        self.assertEqual(self.registry.get_agent("test_agent"), agent)
    
    def test_register_duplicate_agent(self):
        """测试注册重复智能体"""
        agent1 = MockAgent("test_agent")
        agent2 = MockAgent("test_agent")
        
        # 第一次注册成功
        result1 = self.registry.register_agent(agent1)
        self.assertTrue(result1)
        
        # 第二次注册失败
        result2 = self.registry.register_agent(agent2)
        self.assertFalse(result2)
        
        # 验证还是原来的智能体
        self.assertEqual(self.registry.get_agent("test_agent"), agent1)
    
    def test_unregister_agent(self):
        """测试注销智能体"""
        agent = MockAgent("test_agent")
        self.registry.register_agent(agent)
        
        # 注销智能体
        result = self.registry.unregister_agent("test_agent")
        
        # 验证注销成功
        self.assertTrue(result)
        self.assertIsNone(self.registry.get_agent("test_agent"))
        self.assertTrue(agent.stop_called)
    
    def test_unregister_nonexistent_agent(self):
        """测试注销不存在的智能体"""
        result = self.registry.unregister_agent("nonexistent_agent")
        self.assertFalse(result)
    
    def test_get_all_agents(self):
        """测试获取所有智能体"""
        agent1 = MockAgent("agent1")
        agent2 = MockAgent("agent2")
        
        self.registry.register_agent(agent1)
        self.registry.register_agent(agent2)
        
        agents = self.registry.get_all_agents()
        self.assertEqual(len(agents), 2)
        self.assertIn(agent1, agents)
        self.assertIn(agent2, agents)
    
    def test_get_agent_status(self):
        """测试获取智能体状态"""
        agent1 = MockAgent("agent1")
        agent2 = MockAgent("agent2")
        
        self.registry.register_agent(agent1)
        self.registry.register_agent(agent2)
        
        status = self.registry.get_agent_status()
        self.assertEqual(len(status), 2)
        self.assertIn("agent1", status)
        self.assertIn("agent2", status)
        self.assertEqual(status["agent1"]["status"], "空闲")
        self.assertEqual(status["agent2"]["status"], "空闲")
    
    def test_start_all_agents(self):
        """测试启动所有智能体"""
        agent1 = MockAgent("agent1")
        agent2 = MockAgent("agent2")
        
        self.registry.register_agent(agent1)
        self.registry.register_agent(agent2)
        
        # 启动所有智能体
        self.registry.start_all_agents()
        
        # 验证所有智能体都被启动
        self.assertTrue(agent1.start_called)
        self.assertTrue(agent2.start_called)
    
    def test_stop_all_agents(self):
        """测试停止所有智能体"""
        agent1 = MockAgent("agent1")
        agent2 = MockAgent("agent2")
        
        self.registry.register_agent(agent1)
        self.registry.register_agent(agent2)
        
        # 停止所有智能体
        self.registry.stop_all_agents()
        
        # 验证所有智能体都被停止
        self.assertTrue(agent1.stop_called)
        self.assertTrue(agent2.stop_called)
    
    def test_thread_safety(self):
        """测试线程安全性"""
        def register_agent(agent_id):
            agent = MockAgent(agent_id)
            self.registry.register_agent(agent)
        
        # 多线程注册智能体
        threads = []
        for i in range(10):
            thread = threading.Thread(
                target=register_agent,
                args=(f"agent_{i}",)
            )
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 验证所有智能体都被注册
        agents = self.registry.get_all_agents()
        self.assertEqual(len(agents), 10)


if __name__ == '__main__':
    unittest.main()
