import unittest
from unittest.mock import Mock, patch
from agents.decision_coordination_agent import DecisionCoordinationAgent
import time

class TestDecisionCoordinationAgent(unittest.TestCase):
    """测试决策协调智能体"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建模拟的agent_registry
        self.mock_agent_registry = Mock()
        
        # 创建决策协调智能体
        self.agent = DecisionCoordinationAgent("decision_coordination_agent")
        
        # 注入模拟的agent_registry
        self.agent.agent_registry = self.mock_agent_registry
    
    def test_init(self):
        """测试初始化"""
        self.assertEqual(self.agent.agent_id, "decision_coordination_agent")
        self.assertEqual(self.agent.status, "idle")
        self.assertIsInstance(self.agent.system_state, dict)
        self.assertIsInstance(self.agent.agent_status_cache, dict)
        self.assertIsInstance(self.agent.agent_capabilities, dict)
        self.assertIsInstance(self.agent.resource_allocation, dict)
        self.assertIsInstance(self.agent.fault_recovery_history, list)
        self.assertIsInstance(self.agent.collaboration_rules, dict)
        self.assertIsInstance(self.agent.decision_history, list)
    
    def test_start(self):
        """测试启动"""
        self.agent.start()
        self.assertEqual(self.agent.status, "running")
        self.assertTrue(self.agent.system_state["is_running"])
    
    def test_stop(self):
        """测试停止"""
        self.agent.start()
        self.agent.stop()
        self.assertEqual(self.agent.status, "stopped")
        self.assertFalse(self.agent.system_state["is_running"])
    
    def test_update_system_state(self):
        """测试更新系统状态"""
        # 模拟智能体列表
        mock_agent1 = Mock()
        mock_agent1.status = "running"
        mock_agent2 = Mock()
        mock_agent2.status = "idle"
        
        self.mock_agent_registry.get_all_agents.return_value = [mock_agent1, mock_agent2]
        
        # 调用方法
        self.agent.update_system_state()
        
        # 验证结果
        self.assertEqual(self.agent.system_state["total_agents"], 2)
        self.assertEqual(self.agent.system_state["running_agents"], 1)
    
    def test_check_system_health(self):
        """测试检查系统健康状况"""
        # 模拟智能体列表
        mock_agent1 = Mock()
        mock_agent1.status = "running"
        mock_agent2 = Mock()
        mock_agent2.status = "error"
        mock_agent2.agent_id = "test_agent"
        
        self.mock_agent_registry.get_all_agents.return_value = [mock_agent1, mock_agent2]
        
        # 调用方法
        with patch.object(self.agent, 'handle_agent_error') as mock_handle_error:
            self.agent.check_system_health()
            mock_handle_error.assert_called_once_with(mock_agent2)
    
    def test_handle_agent_error(self):
        """测试处理智能体错误"""
        # 模拟智能体
        mock_agent = Mock()
        mock_agent.agent_id = "test_agent"
        
        # 调用方法
        with patch('time.sleep') as mock_sleep:
            self.agent.handle_agent_error(mock_agent)
            mock_agent.stop.assert_called_once()
            # 现在使用简单重启策略，sleep时间为1秒
            mock_sleep.assert_called_once_with(1)
            mock_agent.start.assert_called_once()
    
    def test_on_agent_status_changed(self):
        """测试处理智能体状态变化事件"""
        # 模拟事件数据
        event_data = {
            'agent_id': 'market_data_agent',
            'status': 'running'
        }
        
        # 调用方法
        with patch.object(self.agent, 'update_system_state') as mock_update_state:
            self.agent.on_agent_status_changed(event_data)
            self.assertEqual(self.agent.agent_status_cache['market_data_agent'], 'running')
            mock_update_state.assert_called_once()
    
    def test_on_market_data_updated(self):
        """测试处理市场数据更新事件"""
        # 模拟事件数据
        event_data = {
            'symbol': 'BTC/USDT'
        }
        
        # 调用方法
        self.agent.on_market_data_updated(event_data)
        self.assertIn('BTC/USDT', self.agent.system_state["active_symbols"])
    
    def test_add_symbol_subscription(self):
        """测试添加交易对订阅"""
        # 模拟智能体
        mock_market_agent = Mock()
        self.mock_agent_registry.get_agent.return_value = mock_market_agent
        
        # 调用方法
        self.agent.add_symbol_subscription('BTC/USDT')
        self.assertIn('BTC/USDT', self.agent.system_state["active_symbols"])
    
    def test_remove_symbol_subscription(self):
        """测试移除交易对订阅"""
        # 添加交易对
        self.agent.system_state["active_symbols"].add('BTC/USDT')
        
        # 模拟智能体
        mock_market_agent = Mock()
        self.mock_agent_registry.get_agent.return_value = mock_market_agent
        
        # 调用方法
        self.agent.remove_symbol_subscription('BTC/USDT')
        self.assertNotIn('BTC/USDT', self.agent.system_state["active_symbols"])
    
    def test_activate_strategy(self):
        """测试激活策略"""
        # 模拟智能体
        mock_strategy_agent = Mock()
        self.mock_agent_registry.get_agent.return_value = mock_strategy_agent
        
        # 调用方法
        self.agent.activate_strategy('test_strategy')
        mock_strategy_agent.receive_message.assert_called_once()
    
    def test_deactivate_strategy(self):
        """测试停用策略"""
        # 模拟智能体
        mock_strategy_agent = Mock()
        self.mock_agent_registry.get_agent.return_value = mock_strategy_agent
        
        # 调用方法
        self.agent.deactivate_strategy('test_strategy')
        mock_strategy_agent.receive_message.assert_called_once()
    
    def test_get_system_state(self):
        """测试获取系统状态"""
        state = self.agent.get_system_state()
        self.assertIsInstance(state, dict)
        self.assertEqual(state["is_running"], False)
    
    def test_get_agent_status(self):
        """测试获取智能体状态"""
        # 设置智能体状态
        self.agent.agent_status_cache['test_agent'] = 'running'
        
        # 调用方法
        status = self.agent.get_agent_status('test_agent')
        self.assertEqual(status, 'running')
    
    def test_process_message(self):
        """测试处理消息"""
        # 测试获取系统状态消息
        message = {
            'type': 'get_system_state',
            'sender': 'test_agent'
        }
        
        # 模拟智能体
        mock_test_agent = Mock()
        self.mock_agent_registry.get_agent.return_value = mock_test_agent
        
        # 调用方法
        self.agent.process_message(message)
        mock_test_agent.receive_message.assert_called_once()
    
    def test_calculate_system_load(self):
        """测试计算系统负载"""
        # 设置系统状态
        self.agent.system_state["active_symbols"] = {'BTC/USDT', 'ETH/USDT'}
        self.agent.system_state["running_agents"] = 3
        self.agent.system_state["active_strategies"] = 2
        
        # 调用方法
        load = self.agent._calculate_system_load()
        self.assertGreaterEqual(load, 0.0)
        self.assertLessEqual(load, 1.0)
    

    
    def test_execute_emergency_recovery(self):
        """测试执行紧急恢复措施"""
        # 模拟智能体
        mock_order_agent = Mock()
        mock_strategy_agent = Mock()
        
        # 设置mock返回值
        def mock_get_agent(agent_id):
            if agent_id == "order_agent":
                return mock_order_agent
            elif agent_id == "strategy_execution_agent":
                return mock_strategy_agent
            return None
        
        self.mock_agent_registry.get_agent.side_effect = mock_get_agent
        
        # 调用方法
        with patch('time.sleep') as mock_sleep:
            self.agent._execute_emergency_recovery()
            # 验证订单智能体收到暂停交易消息
            self.assertEqual(mock_order_agent.receive_message.call_count, 1)
            # 验证策略执行智能体收到停用所有策略消息
            self.assertEqual(mock_strategy_agent.receive_message.call_count, 1)
            # 验证系统健康度被重置
            self.assertEqual(self.agent.system_state["system_health"], 1.0)

if __name__ == '__main__':
    unittest.main()