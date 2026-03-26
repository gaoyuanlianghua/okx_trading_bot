import unittest
from unittest.mock import Mock, patch
from agents.market_data_agent import MarketDataAgent
import time

class TestMarketDataAgent(unittest.TestCase):
    """测试市场数据智能体"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建模拟的agent_registry
        self.mock_agent_registry = Mock()
        
        # 创建市场数据智能体
        self.agent = MarketDataAgent("market_data_agent", {
            "update_interval": 0.1,
            "cache_ttl": 5
        })
        
        # 注入模拟的agent_registry
        self.agent.agent_registry = self.mock_agent_registry
    
    def test_init(self):
        """测试初始化"""
        self.assertEqual(self.agent.agent_id, "market_data_agent")
        self.assertEqual(self.agent.status, "idle")
        self.assertEqual(self.agent.update_interval, 0.1)
        self.assertEqual(self.agent.cache_ttl, 5)
        self.assertIsInstance(self.agent.subscribed_symbols, set)
        self.assertIsInstance(self.agent.data_cache, dict)
        self.assertIsInstance(self.agent.cache_timestamp, dict)
        self.assertIsInstance(self.agent.last_market_data, dict)
    
    @patch('agents.market_data_agent.MarketDataService')
    @patch('okx_api_client.OKXAPIClient')
    def test_start(self, mock_api_client_class, mock_market_service_class):
        """测试启动"""
        # 模拟OKXAPIClient和MarketDataService
        mock_api_client = Mock()
        mock_market_service = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_market_service_class.return_value = mock_market_service
        
        self.agent.start()
        
        self.assertEqual(self.agent.status, "running")
        self.assertTrue(self.agent.is_running)
        self.assertIsNotNone(self.agent.market_data_service)
    
    @patch('agents.market_data_agent.MarketDataService')
    @patch('okx_api_client.OKXAPIClient')
    def test_stop(self, mock_api_client_class, mock_market_service_class):
        """测试停止"""
        # 先启动
        mock_api_client = Mock()
        mock_market_service = Mock()
        mock_api_client_class.return_value = mock_api_client
        mock_market_service_class.return_value = mock_market_service
        
        self.agent.start()
        self.assertEqual(self.agent.status, "running")
        
        # 再停止
        self.agent.stop()
        self.assertEqual(self.agent.status, "stopped")
        self.assertFalse(self.agent.is_running)
    
    def test_subscribe_symbol(self):
        """测试订阅交易对"""
        self.agent.subscribe_symbol("BTC-USDT-SWAP")
        self.assertIn("BTC-USDT-SWAP", self.agent.subscribed_symbols)
    
    def test_unsubscribe_symbol(self):
        """测试取消订阅交易对"""
        self.agent.subscribe_symbol("BTC-USDT-SWAP")
        self.agent.unsubscribe_symbol("BTC-USDT-SWAP")
        self.assertNotIn("BTC-USDT-SWAP", self.agent.subscribed_symbols)
    
    def test_get_subscribed_symbols(self):
        """测试获取已订阅的交易对列表"""
        self.agent.subscribe_symbol("BTC-USDT-SWAP")
        self.agent.subscribe_symbol("ETH-USDT-SWAP")
        
        symbols = self.agent.get_subscribed_symbols()
        self.assertEqual(len(symbols), 2)
        self.assertIn("BTC-USDT-SWAP", symbols)
        self.assertIn("ETH-USDT-SWAP", symbols)
    
    def test_is_cache_valid(self):
        """测试缓存有效性检查"""
        # 测试缓存不存在
        self.assertFalse(self.agent._is_cache_valid("BTC-USDT-SWAP"))
        
        # 添加缓存
        self.agent._update_cache("BTC-USDT-SWAP", {"price": 50000})
        # 缓存应该有效
        self.assertTrue(self.agent._is_cache_valid("BTC-USDT-SWAP"))
        
        # 模拟缓存过期
        self.agent.cache_timestamp["BTC-USDT-SWAP"] = time.time() - 10
        # 缓存应该无效
        self.assertFalse(self.agent._is_cache_valid("BTC-USDT-SWAP"))
    
    def test_update_cache(self):
        """测试更新缓存"""
        market_data = {"price": 50000, "volume": 1000}
        self.agent._update_cache("BTC-USDT-SWAP", market_data)
        
        self.assertEqual(self.agent.data_cache["BTC-USDT-SWAP"], market_data)
        self.assertIn("BTC-USDT-SWAP", self.agent.cache_timestamp)
    
    def test_has_data_changed(self):
        """测试数据变化检测"""
        # 第一次获取数据，应该返回True
        market_data = {"price": 50000, "volume": 1000, "change": 0.01, "change_pct": 0.1}
        self.assertTrue(self.agent._has_data_changed("BTC-USDT-SWAP", market_data))
        
        # 更新上次数据
        self.agent.last_market_data["BTC-USDT-SWAP"] = market_data.copy()
        
        # 数据不变，应该返回False
        self.assertFalse(self.agent._has_data_changed("BTC-USDT-SWAP", market_data))
        
        # 数据变化，应该返回True
        new_data = {"price": 50001, "volume": 1000, "change": 0.01, "change_pct": 0.1}
        self.assertTrue(self.agent._has_data_changed("BTC-USDT-SWAP", new_data))
    
    def test_process_message(self):
        """测试处理消息"""
        # 测试订阅消息
        message = {
            'type': 'subscribe_symbol',
            'symbol': 'BTC-USDT-SWAP'
        }
        self.agent.process_message(message)
        self.assertIn("BTC-USDT-SWAP", self.agent.subscribed_symbols)
        
        # 测试取消订阅消息
        message = {
            'type': 'unsubscribe_symbol',
            'symbol': 'BTC-USDT-SWAP'
        }
        self.agent.process_message(message)
        self.assertNotIn("BTC-USDT-SWAP", self.agent.subscribed_symbols)
    
    def test_get_market_data(self):
        """测试获取市场数据"""
        # 模拟市场数据服务
        mock_market_service = Mock()
        mock_market_service.get_real_time_ticker.return_value = [{
            'last': '50000',
            'open24h': '49000',
            'high24h': '51000',
            'low24h': '48000',
            'vol24h': '1000000',
            'change24h': '1000',
            'change24h': '0.02'
        }]
        
        self.agent.market_data_service = mock_market_service
        
        data = self.agent.get_market_data("BTC-USDT-SWAP")
        self.assertIsNotNone(data)
        self.assertEqual(data['symbol'], "BTC-USDT-SWAP")
        self.assertEqual(data['price'], 50000)
        self.assertEqual(data['open'], 49000)
    
    def test_get_market_data_without_service(self):
        """测试没有市场数据服务时获取数据"""
        self.agent.market_data_service = None
        data = self.agent.get_market_data("BTC-USDT-SWAP")
        self.assertIsNone(data)
    
    def test_on_agent_status_changed(self):
        """测试处理智能体状态变化事件"""
        event_data = {
            'agent_id': 'test_agent',
            'status': 'running'
        }
        # 这个方法主要是日志记录，没有返回值，所以我们只测试它不会抛出异常
        try:
            self.agent.on_agent_status_changed(event_data)
            success = True
        except Exception:
            success = False
        self.assertTrue(success)
    
    def test_process_get_market_data_message(self):
        """测试处理获取市场数据消息"""
        # 模拟市场数据服务
        mock_market_service = Mock()
        mock_market_service.get_real_time_ticker.return_value = [{
            'last': '50000',
            'open24h': '49000',
            'high24h': '51000',
            'low24h': '48000',
            'vol24h': '1000000',
            'change24h': '1000',
            'change24h': '0.02'
        }]
        
        self.agent.market_data_service = mock_market_service
        
        # 模拟发送消息的方法
        mock_send_message = Mock()
        self.agent.send_message = mock_send_message
        
        # 测试获取市场数据消息
        message = {
            'type': 'get_market_data',
            'symbol': 'BTC-USDT-SWAP',
            'sender': 'test_agent'
        }
        
        self.agent.process_message(message)
        
        # 验证发送了响应消息
        mock_send_message.assert_called_once()
        args, kwargs = mock_send_message.call_args
        self.assertEqual(args[0], 'test_agent')
        self.assertEqual(args[1]['type'], 'market_data_response')
        self.assertEqual(args[1]['symbol'], 'BTC-USDT-SWAP')

if __name__ == '__main__':
    unittest.main()