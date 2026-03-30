"""
API客户端单元测试
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, MagicMock
from core.api.okx_rest_client import OKXRESTClient
from core.api.okx_websocket_client import OKXWebSocketClient
from core.api.auth import OKXAuth


class TestOKXRESTClient:
    """测试OKX REST客户端"""
    
    @pytest.fixture
    def rest_client(self):
        """创建REST客户端实例"""
        return OKXRESTClient(is_test=True)
    
    async def test_get_server_time(self, rest_client):
        """测试获取服务器时间"""
        server_time = await rest_client.get_server_time()
        assert server_time is not None
    
    async def test_get_instruments(self, rest_client):
        """测试获取交易产品"""
        instruments = await rest_client.get_instruments("SWAP")
        assert isinstance(instruments, list)
    
    async def test_get_ticker(self, rest_client):
        """测试获取行情"""
        ticker = await rest_client.get_ticker("BTC-USDT-SWAP")
        assert ticker is not None
        assert "last" in ticker
    
    async def test_get_orderbook(self, rest_client):
        """测试获取订单簿"""
        orderbook = await rest_client.get_orderbook("BTC-USDT-SWAP")
        assert orderbook is not None
        assert "asks" in orderbook
        assert "bids" in orderbook
    
    async def test_get_candles(self, rest_client):
        """测试获取K线数据"""
        candles = await rest_client.get_candles("BTC-USDT-SWAP")
        assert isinstance(candles, list)
    
    async def test_batch_request(self, rest_client):
        """测试批量请求"""
        requests = [
            {
                "method": "GET",
                "endpoint": "/public/time",
                "auth_required": False
            },
            {
                "method": "GET",
                "endpoint": "/public/instruments",
                "params": {"instType": "SWAP"},
                "auth_required": False
            }
        ]
        results = await rest_client.batch_request(requests)
        assert len(results) == 2
        assert results[0] is not None
    
    async def test_cache_mechanism(self, rest_client):
        """测试缓存机制"""
        # 第一次请求，应该从API获取
        ticker1 = await rest_client.get_ticker("BTC-USDT-SWAP")
        assert ticker1 is not None
        
        # 第二次请求，应该从缓存获取
        ticker2 = await rest_client.get_ticker("BTC-USDT-SWAP")
        assert ticker2 is not None
        assert ticker1 == ticker2
    
    async def test_rate_limit(self, rest_client):
        """测试速率限制"""
        # 连续发送多个请求，应该不会触发速率限制错误
        for _ in range(5):
            ticker = await rest_client.get_ticker("BTC-USDT-SWAP")
            assert ticker is not None
    
    async def test_error_handling(self, rest_client):
        """测试错误处理"""
        # 测试不存在的产品
        ticker = await rest_client.get_ticker("NONEXISTENT-PRODUCT")
        assert ticker is None


class TestOKXWebSocketClient:
    """测试OKX WebSocket客户端"""
    
    @pytest.fixture
    def ws_client(self):
        """创建WebSocket客户端实例"""
        return OKXWebSocketClient(is_test=True)
    
    async def test_connect_public(self, ws_client):
        """测试连接公共WebSocket"""
        result = await ws_client.connect_public()
        assert result is True
        assert ws_client._public_connected is True
        
        # 清理
        await ws_client.close()
    
    async def test_subscribe(self, ws_client):
        """测试订阅频道"""
        await ws_client.connect_public()
        result = await ws_client.subscribe("tickers", "BTC-USDT-SWAP")
        assert result is True
        
        # 清理
        await ws_client.close()
    
    async def test_unsubscribe(self, ws_client):
        """测试取消订阅"""
        await ws_client.connect_public()
        await ws_client.subscribe("tickers", "BTC-USDT-SWAP")
        result = await ws_client.unsubscribe("tickers", "BTC-USDT-SWAP")
        assert result is True
        
        # 清理
        await ws_client.close()
    
    async def test_is_connected(self, ws_client):
        """测试连接状态"""
        assert ws_client.is_connected() is False
        await ws_client.connect_public()
        # 注意：私有连接未连接，所以整体连接状态仍为False
        assert ws_client.is_connected() is False
        
        # 清理
        await ws_client.close()


if __name__ == "__main__":
    asyncio.run(pytest.main([__file__]))
