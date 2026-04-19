"""
策略运行器
整合测试脚本的功能，提供正式的策略运行支持
"""

import asyncio
import time
import logging
from typing import Optional, Dict, Any
from pathlib import Path

from core.config.env_manager import env_manager
from core.api.okx_rest_client import OKXRESTClient
from strategies.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class StrategyRunner:
    """策略运行器，负责策略的启动、执行和管理"""
    
    def __init__(self):
        self.rest_client: Optional[OKXRESTClient] = None
        self.strategy: Optional[BaseStrategy] = None
        self.is_running: bool = False
        self.execution_count: int = 0
    
    async def setup(self, strategy_class, strategy_config: Optional[Dict[str, Any]] = None):
        """
        设置策略运行环境
        
        Args:
            strategy_class: 策略类
            strategy_config: 策略配置
        """
        logger.info("=" * 60)
        logger.info("设置策略运行环境")
        logger.info("=" * 60)
        
        # 检查环境
        env_info = env_manager.get_env_info()
        if not env_info['is_test']:
            logger.warning("⚠️  注意：当前不是模拟盘环境，将使用实盘交易！")
        else:
            logger.info("✅ 正在使用模拟盘环境")
        
        # 获取API配置
        api_config = env_manager.get_api_config()
        logger.info(f"API Key: {api_config['api_key'][:8]}...")
        logger.info(f"模拟盘模式: {api_config['is_test']}")
        
        # 创建REST客户端
        logger.info("创建REST客户端...")
        self.rest_client = OKXRESTClient(
            api_key=api_config['api_key'],
            api_secret=api_config['api_secret'],
            passphrase=api_config['passphrase'],
            is_test=api_config['is_test']
        )
        logger.info("✅ REST客户端创建成功")
        
        # 测试API连接
        logger.info("测试API连接...")
        server_time = await self.rest_client.get_server_time()
        if server_time:
            logger.info(f"✅ 服务器时间获取成功: {server_time}")
        else:
            raise Exception("API连接失败")
        
        # 测试行情数据
        ticker = await self.rest_client.get_ticker('BTC-USDT')
        if ticker:
            logger.info(f"✅ 行情数据获取成功")
            logger.info(f"  BTC-USDT 最新价: {ticker.get('last')} USDT")
        else:
            raise Exception("行情数据获取失败")
        
        # 创建策略实例
        logger.info("初始化策略...")
        self.strategy = strategy_class(
            api_client=self.rest_client,
            config=strategy_config
        )
        logger.info("✅ 策略初始化成功")
        
        # 启动策略
        self.strategy.start()
        logger.info("✅ 策略启动成功")
        
        return True
    
    async def execute_once(self) -> Optional[Dict[str, Any]]:
        """
        执行一次策略
        
        Returns:
            策略信号，无信号返回None
        """
        if not self.strategy or not self.rest_client:
            raise Exception("策略未初始化，请先调用 setup()")
        
        self.execution_count += 1
        
        # 获取最新行情数据
        logger.debug(f"获取最新行情数据 (第{self.execution_count}次)...")
        ticker = await self.rest_client.get_ticker('BTC-USDT')
        
        if not ticker:
            logger.error("获取行情数据失败")
            return None
        
        # 构建策略数据
        strategy_data = {
            "market_data": {
                "last": ticker.get('last'),
                "high": ticker.get('high24h'),
                "low": ticker.get('low24h'),
                "volume": ticker.get('vol24h'),
                "timestamp": ticker.get('ts'),
                "inst_id": 'BTC-USDT'
            },
            "order_data": {
                "trade_history": [],
                "pending_orders": []
            }
        }
        
        # 执行策略
        logger.debug("执行策略...")
        signal = self.strategy.execute(strategy_data)
        
        if signal:
            self._log_signal(signal)
        
        return signal
    
    def _log_signal(self, signal: Dict[str, Any]):
        """
        记录策略信号
        
        Args:
            signal: 策略信号
        """
        if signal.get('side') != 'neutral':
            logger.info("\n" + "-" * 40)
            logger.info(f"策略信号: {signal}")
            logger.info(f"📊 信号强度: {signal.get('signal_strength', 0):.2f}")
            logger.info(f"📈 信号级别: {signal.get('signal_level', 'N/A')}")
            logger.info(f"🎯 信号得分: {signal.get('signal_score', 0)}")
            logger.info(f"💡 方向: {signal.get('side', 'neutral')}")
            logger.info(f"💰 价格: {signal.get('price', 0)}")
            logger.info("-" * 40 + "\n")
        else:
            logger.info("策略信号: 中性 (无交易)")
    
    async def run_continuous(self, interval: int = 60):
        """
        持续运行策略
        
        Args:
            interval: 执行间隔（秒）
        """
        if not self.strategy:
            raise Exception("策略未初始化，请先调用 setup()")
        
        self.is_running = True
        logger.info("\n" + "=" * 60)
        logger.info(f"开始持续运行策略（每{interval}秒执行一次）")
        logger.info("按 Ctrl+C 停止策略")
        logger.info("=" * 60)
        
        try:
            while self.is_running:
                try:
                    await self.execute_once()
                except Exception as e:
                    logger.error(f"执行策略时出错: {e}")
                    import traceback
                    traceback.print_exc()
                
                if self.is_running:
                    logger.info(f"等待下一次执行 ({interval}秒)...")
                    await asyncio.sleep(interval)
                    
        except KeyboardInterrupt:
            logger.info("用户中断，停止策略")
            self.is_running = False
        except Exception as e:
            logger.error(f"运行策略时出错: {e}")
            import traceback
            traceback.print_exc()
            self.is_running = False
        finally:
            await self.stop()
    
    async def stop(self):
        """停止策略"""
        if self.strategy:
            self.strategy.stop()
            logger.info("策略已停止")
        
        if self.rest_client and hasattr(self.rest_client, 'session') and self.rest_client.session:
            await self.rest_client.session.close()
        
        self.is_running = False


async def main():
    """示例主函数"""
    from strategies.nuclear_dynamics_strategy import NuclearDynamicsStrategy
    
    runner = StrategyRunner()
    
    try:
        # 设置策略
        strategy_config = {
            'strategy': {
                'name': 'nuclear_dynamics_strategy',
                'symbol': 'BTC-USDT',
                'timeframe': '1m'
            }
        }
        
        await runner.setup(NuclearDynamicsStrategy, strategy_config)
        
        # 持续运行策略
        await runner.run_continuous(interval=60)
        
    except Exception as e:
        logger.error(f"启动策略失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('strategy_runner.log'),
            logging.StreamHandler()
        ]
    )
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
