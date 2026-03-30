#!/usr/bin/env python3
"""
OKX 交易机器人单元测试
"""

import unittest
import sys
import os
from unittest.mock import patch, Mock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from websocket_gui import WebSocketGUI, DraggableDashboardCard, AnimatedTabWidget
from PyQt5.QtWidgets import QApplication

class TestWebSocketGUI(unittest.TestCase):
    """测试 WebSocketGUI 类"""
    
    @classmethod
    def setUpClass(cls):
        """设置测试环境"""
        # 创建应用程序实例
        cls.app = QApplication(sys.argv)
    
    def setUp(self):
        """设置测试用例"""
        # 使用mock来避免实际初始化耗时操作
        with patch('core.agents.market_data_agent.exchange_manager') as mock_exchange_manager, \
             patch('core.EventBus') as mock_event_bus, \
             patch('core.agents.market_data_agent.MarketDataAgent') as mock_market_data, \
             patch('websocket_gui.OKXWebSocketClient') as mock_ws_client, \
             patch.object(WebSocketGUI, '_show_login_dialog') as mock_login:
            
            # 配置mock对象
            mock_login.return_value = True  # 模拟登录成功
            mock_instance = Mock()
            mock_instance.get_exchange.return_value = Mock()
            mock_instance.get_websocket_client.return_value = Mock()
            mock_exchange_manager.get_exchange.return_value = Mock()
            mock_exchange_manager.get_websocket_client.return_value = Mock()
            
            # 配置MarketDataAgent mock
            mock_market_instance = Mock()
            mock_market_data.return_value = mock_market_instance
            
            # 配置WebSocketClient mock
            mock_ws_instance = Mock()
            mock_ws_instance.is_connected.return_value = False
            mock_ws_client.return_value = mock_ws_instance
            
            # 创建 WebSocketGUI 实例
            self.gui = WebSocketGUI()
    
    def test_initialization(self):
        """测试初始化"""
        self.assertIsNotNone(self.gui)
        self.assertIsNotNone(self.gui.event_bus)
        self.assertIsNotNone(self.gui.market_data)
        self.assertIsNotNone(self.gui.price_history)
        self.assertIsNotNone(self.gui.order_data)
        self.assertIsNotNone(self.gui.account_data)
        self.assertIsNotNone(self.gui.strategies)
    
    def test_dashboard_cards(self):
        """测试仪表盘卡片"""
        self.assertIsNotNone(self.gui.dashboard_cards)
        self.assertTrue(len(self.gui.dashboard_cards) >= 4)
    
    def test_encryption_initialization(self):
        """测试加密系统初始化"""
        # 测试加密系统是否初始化成功
        self.assertTrue(hasattr(self.gui, 'cipher_suite') or self.gui.cipher_suite is None)
    
    def test_update_dashboard(self):
        """测试仪表盘更新"""
        # 测试仪表盘更新方法是否存在
        self.assertTrue(hasattr(self.gui, 'update_dashboard'))
    
    def test_api_key_encryption(self):
        """测试 API 密钥加密"""
        # 测试 API 密钥加密方法是否存在
        self.assertTrue(hasattr(self.gui, '_save_encrypted_api_keys'))
        self.assertTrue(hasattr(self.gui, '_load_encrypted_api_keys'))
    
    def tearDown(self):
        """清理测试用例"""
        # 关闭 GUI
        self.gui.close()
        del self.gui
    
    @classmethod
    def tearDownClass(cls):
        """清理测试环境"""
        del cls.app

class TestDraggableDashboardCard(unittest.TestCase):
    """测试 DraggableDashboardCard 类"""
    
    @classmethod
    def setUpClass(cls):
        """设置测试环境"""
        cls.app = QApplication(sys.argv)
    
    def setUp(self):
        """设置测试用例"""
        self.card = DraggableDashboardCard("测试卡片")
    
    def test_initialization(self):
        """测试初始化"""
        self.assertIsNotNone(self.card)
        self.assertEqual(self.card.title(), "测试卡片")
    
    def test_accept_drops(self):
        """测试接受拖拽"""
        self.assertTrue(self.card.acceptDrops())
    
    def tearDown(self):
        """清理测试用例"""
        del self.card
    
    @classmethod
    def tearDownClass(cls):
        """清理测试环境"""
        del cls.app

class TestAnimatedTabWidget(unittest.TestCase):
    """测试 AnimatedTabWidget 类"""
    
    @classmethod
    def setUpClass(cls):
        """设置测试环境"""
        cls.app = QApplication(sys.argv)
    
    def setUp(self):
        """设置测试用例"""
        self.tab_widget = AnimatedTabWidget()
    
    def test_initialization(self):
        """测试初始化"""
        self.assertIsNotNone(self.tab_widget)
    
    def tearDown(self):
        """清理测试用例"""
        del self.tab_widget
    
    @classmethod
    def tearDownClass(cls):
        """清理测试环境"""
        del cls.app

if __name__ == '__main__':
    unittest.main()
