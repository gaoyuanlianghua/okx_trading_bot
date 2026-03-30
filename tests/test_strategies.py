"""
策略单元测试
"""

import pytest
from strategies.base_strategy import BaseStrategy
from strategies.dynamics_strategy import DynamicsStrategy
from strategies.combined_strategy import CombinedStrategy


class TestBaseStrategy:
    """测试基础策略"""
    
    @pytest.fixture
    def base_strategy(self):
        """创建基础策略实例"""
        config = {"test": "config"}
        return BaseStrategy(config=config)
    
    def test_initialization(self, base_strategy):
        """测试初始化"""
        assert base_strategy is not None
        assert base_strategy.name == "BaseStrategy"
    
    def test_execute(self, base_strategy):
        """测试执行方法"""
        market_data = {"price": 50000.0, "timestamp": 1234567890}
        signal = base_strategy.execute(market_data)
        assert signal is None
    
    def test_start_stop(self, base_strategy):
        """测试启动和停止"""
        base_strategy.start()
        assert base_strategy.is_running is True
        
        base_strategy.stop()
        assert base_strategy.is_running is False


class TestDynamicsStrategy:
    """测试Dynamics策略"""
    
    @pytest.fixture
    def dynamics_strategy(self):
        """创建Dynamics策略实例"""
        config = {
            "dynamics": {
                "ε": 0.85,  # 距离阈值
                "G_eff": 1.2e-3,  # 有效增益因子
                "position_size": 0.1,  # 仓位大小（百分比）
                "max_position": 0.5,  # 最大仓位（百分比）
                "stop_loss": 0.02,  # 止损比例
                "take_profit": 0.05,  # 止盈比例
                "min_order_size": 0.001,  # 最小订单大小
                "max_order_size": 0.1,  # 最大订单大小
                "order_timeout": 30,  # 订单超时时间（秒）
                "market_data_keys": {
                    "price": "last",
                    "timestamp": "ts",
                    "volume": "volCcy24h"
                },
                "risk_management": {
                    "max_drawdown": 0.1,  # 最大回撤
                    "max_leverage": 10,  # 最大杠杆
                    "max_position_percent": 0.5,  # 最大仓位百分比
                    "stop_loss_enabled": True,  # 是否启用止损
                    "take_profit_enabled": True  # 是否启用止盈
                },
                "backtesting": {
                    "initial_balance": 10000,  # 初始资金
                    "data_source": "okx",  # 数据来源
                    "timeframe": "1m",  # 时间粒度
                    "start_date": "2024-01-01",  # 开始日期
                    "end_date": "2024-01-31"  # 结束日期
                }
            }
        }
        return DynamicsStrategy(config=config)
    
    def test_initialization(self, dynamics_strategy):
        """测试初始化"""
        assert dynamics_strategy is not None
        assert dynamics_strategy.name == "DynamicsStrategy"
    
    def test_execute(self, dynamics_strategy):
        """测试执行方法"""
        market_data = {"price": 50000.0, "timestamp": 1234567890}
        signal = dynamics_strategy.execute(market_data)
        assert signal is not None
        assert "side" in signal
        assert "price" in signal
    
    def test_start_stop(self, dynamics_strategy):
        """测试启动和停止"""
        dynamics_strategy.start()
        assert dynamics_strategy.is_running is True
        
        dynamics_strategy.stop()
        assert dynamics_strategy.is_running is False


class TestCombinedStrategy:
    """测试组合策略"""
    
    @pytest.fixture
    def combined_strategy(self):
        """创建组合策略实例"""
        config = {
            "strategies": [
                {
                    "name": "DynamicsStrategy",
                    "config": {
                        "dynamics": {
                            "ε": 0.85,
                            "G_eff": 1.2e-3
                        }
                    },
                    "weight": 0.5
                }
            ],
            "signal_combination": "weighted_average",
            "min_confidence": 0.3
        }
        return CombinedStrategy(config=config)
    
    def test_initialization(self, combined_strategy):
        """测试初始化"""
        assert combined_strategy is not None
        assert combined_strategy.name == "CombinedStrategy"
    
    def test_execute(self, combined_strategy):
        """测试执行方法"""
        market_data = {"price": 50000.0, "timestamp": 1234567890}
        signal = combined_strategy.execute(market_data)
        assert signal is not None
        assert "side" in signal
        assert "price" in signal
    
    def test_start_stop(self, combined_strategy):
        """测试启动和停止"""
        combined_strategy.start()
        assert combined_strategy.is_running is True
        
        combined_strategy.stop()
        assert combined_strategy.is_running is False


if __name__ == "__main__":
    pytest.main([__file__])
