#!/usr/bin/env python3
"""
启动核互反动力学策略
"""

import logging
import sys
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

# 测试导入
logger.info("开始导入模块...")
try:
    import asyncio
    logger.info("成功导入asyncio")
except Exception as e:
    logger.error(f"导入asyncio失败: {e}")

try:
    from core.config.env_manager import env_manager
    logger.info("成功导入env_manager")
except Exception as e:
    logger.error(f"导入env_manager失败: {e}")

try:
    from core.api.okx_rest_client import OKXRESTClient
    logger.info("成功导入OKXRESTClient")
except Exception as e:
    logger.error(f"导入OKXRESTClient失败: {e}")

try:
    from core.api.okx_websocket_client import OKXWebSocketClient
    logger.info("成功导入OKXWebSocketClient")
except Exception as e:
    logger.error(f"导入OKXWebSocketClient失败: {e}")

try:
    from strategies.nuclear_dynamics_strategy import NuclearDynamicsStrategy
    logger.info("成功导入NuclearDynamicsStrategy")
except Exception as e:
    logger.error(f"导入NuclearDynamicsStrategy失败: {e}")

logger.info("模块导入完成")


class NuclearStrategyTrader:
    """核互反动力学策略交易器"""
    
    def __init__(self):
        self.rest_client = None
        self.ws_client = None
        self.strategy = None
        self.api_config = None
    
    async def setup(self):
        """设置交易环境"""
        try:
            logger.info("\n" + "=" * 60)
            logger.info("启动核互反动力学策略")
            logger.info("=" * 60)
            
            # 检查环境
            logger.info("检查环境...")
            env_info = env_manager.get_env_info()
            logger.info(f"环境信息: {env_info}")
            if not env_info['is_test']:
                logger.warning("⚠️  注意：当前不是模拟盘环境，将使用实盘交易！")
                # 自动继续实盘交易
                logger.info("自动继续在实盘环境中运行")
            else:
                logger.info("✅ 正在使用模拟盘环境")
            
            # 获取API配置
            logger.info("获取API配置...")
            self.api_config = env_manager.get_api_config()
            logger.info(f"API Key: {self.api_config['api_key'][:8]}...")
            logger.info(f"模拟盘模式: {self.api_config['is_test']}")
            
            # 创建REST客户端
            logger.info("创建REST客户端...")
            logger.info(f"API配置: {self.api_config}")
            try:
                self.rest_client = OKXRESTClient(
                    api_key=self.api_config['api_key'],
                    api_secret=self.api_config['api_secret'],
                    passphrase=self.api_config['passphrase'],
                    is_test=self.api_config['is_test']
                )
                logger.info("REST客户端创建成功")
            except Exception as e:
                logger.error(f"创建REST客户端失败: {e}")
                import traceback
                traceback.print_exc()
                return False
            
            # 等待时间同步完成
            logger.info("等待时间同步完成...")
            await asyncio.sleep(2)  # 等待2秒，确保时间同步完成
            
            # 测试API连接
            logger.info("\n测试API连接...")
            server_time = await self.rest_client.get_server_time()
            logger.info(f"服务器时间获取结果: {server_time}")
            if server_time:
                logger.info(f"✅ 服务器时间获取成功: {server_time}")
            else:
                logger.error("❌ API连接失败")
                return False
            
            # 测试行情数据
            logger.info("测试行情数据获取...")
            ticker = await self.rest_client.get_ticker('BTC-USDT')
            logger.info(f"行情数据获取结果: {ticker}")
            if ticker:
                logger.info(f"✅ 行情数据获取成功")
                logger.info(f"  BTC-USDT 最新价: {ticker.get('last')} USDT")
            else:
                logger.error("❌ 行情数据获取失败")
                return False
            
            # 创建策略实例
            logger.info("\n初始化核互反动力学策略...")
            strategy_config = {
                'strategy': {
                    'name': 'nuclear_dynamics_strategy',
                    'symbol': 'BTC-USDT',
                    'timeframe': '1m'
                },
                'params': {
                    'fall_threshold': 0.02,      # 下跌幅度阈值 (2%)
                    'drift_threshold': 0.001,     # 飘移判定最小变化 (0.1%)
                    'roc_period': 20,             # 角动量ROC周期
                    'pairing_half_life_window': 60, # 配对半衰期窗口
                    'phase_sync_threshold': 0.3,  # 相位同步阈值 (弧度)
                    'phase_lockout_threshold': 0.8, # 相位失锁阈值 (弧度)
                    'asymmetric_param_threshold': 0.2, # 非对称参数阈值
                    'atr_period': 14,             # ATR周期
                    'min_atr_price_ratio': 0.005, # 最低ATR/价格比 (0.5%)
                    'max_atr_price_ratio': 0.05,  # 最高ATR/价格比 (5%)
                    'max_risk_sss': 0.02,         # 最大单笔风险(SSS) (2%)
                    'max_risk_ss': 0.015,         # 最大单笔风险(SS) (1.5%)
                    'max_risk_s': 0.01,           # 最大单笔风险(S) (1%)
                },
                'risk': {
                    'max_leverage': 5,
                    'stop_loss': 0.03,  # 3%止损
                    'take_profit': 0.05, # 5%止盈
                    'max_position_value': 5000,  # USDT
                    'daily_loss_limit': 0.05
                }
            }
            
            self.strategy = NuclearDynamicsStrategy(
                config=strategy_config
            )
            logger.info("✅ 策略初始化成功")
            
            # 启动策略
            self.strategy.start()
            logger.info("✅ 策略启动成功")
            
            return True
        except Exception as e:
            logger.error(f"设置交易环境失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def run(self):
        """运行策略"""
        logger.info("\n" + "=" * 60)
        logger.info("开始运行核互反动力学策略")
        logger.info("=" * 60)
        
        try:
            # 持续运行
            while True:
                # 获取最新行情数据
                logger.info("\n获取最新行情数据...")
                ticker = await self.rest_client.get_ticker('BTC-USDT')
                
                logger.info(f"获取行情数据结果: {ticker}")
                
                if ticker:
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
                    logger.info(f"构建的策略数据: {strategy_data}")
                    
                    # 执行策略
                    logger.info("执行策略...")
                    signal = self.strategy.execute(strategy_data["market_data"])
                    
                    if signal and signal.get('side') != 'neutral' and signal.get('side') != 'hold':
                        logger.info(f"\n策略信号: {signal}")
                        
                        # 执行交易
                        side = signal.get('side')
                        price = signal.get('price')
                        inst_id = signal.get('inst_id', 'BTC-USDT')
                        
                        # 计算交易金额 (根据账户余额动态计算)
                        try:
                            # 获取账户余额
                            balance = await self.rest_client.get_account_balance()
                            usdt_balance = 0.0
                            if balance and isinstance(balance, dict):
                                details = balance.get('details', [])
                                for item in details:
                                    if item.get('ccy') == 'USDT':
                                        usdt_balance = float(item.get('availBal', 0) or 0)
                                        logger.info(f"✅ 账户USDT可用余额: {usdt_balance:.2f}")
                                        break
                            
                            # 获取当前价格
                            current_price = float(price)
                            
                            # 计算最小交易金额（根据交易对的币值）
                            if 'BTC' in inst_id:
                                min_amount = 0.00001 * current_price  # BTC最小交易单位 0.00001 (约0.762 USDT)
                            elif 'ETH' in inst_id:
                                min_amount = 0.0001 * current_price  # ETH最小交易单位 0.0001 (约0.235 USDT)
                            else:
                                min_amount = 1.0  # 其他交易对默认1 USDT
                            
                            # 根据余额的1%计算交易金额，最低为最小交易单位
                            if usdt_balance > 0:
                                calculated_amount = usdt_balance * 0.01  # 1% of balance
                                amount = max(min_amount, calculated_amount)  # 取最大值
                                amount = int(amount)  # 向下取整到整数
                                amount = max(1, amount)  # 确保至少1 USDT
                                logger.info(f"📏 计算交易金额: {amount} USDT (账户余额的1%，最小交易单位: {min_amount:.2f} USDT，向下取整)")
                            else:
                                amount = max(1.0, min_amount)  # 使用最小交易单位，至少1 USDT
                                amount = int(amount)  # 向下取整到整数
                                logger.warning(f"⚠️  无法获取账户余额，使用最小交易单位: {amount} USDT")
                        except Exception as e:
                            amount = 1.0  # 默认1 USDT
                            logger.error(f"❌ 获取账户余额失败: {e}")
                        
                        amount = str(amount)
                        
                        logger.info(f"📊 信号强度: {signal.get('signal_strength', 0):.2f}")
                        logger.info(f"📈 信号级别: {signal.get('signal_level', 'unknown')}")
                        logger.info(f"🎯 信号得分: {signal.get('signal_score', 0)}")
                        logger.info(f"💡 方向: {side}")
                        logger.info(f"💰 价格: {price}")
                        logger.info(f"📏 交易金额: {amount} USDT")
                        logger.info(f"📋 交易对: {inst_id}")
                        
                        # 下单
                        try:
                            # 对于卖出交易，不使用tgtCcy参数，因为BTC-USDT不支持
                            if side == 'buy':
                                order_id = await self.rest_client.place_order(
                                    inst_id=inst_id,
                                    side=side,
                                    ord_type='market',  # 市价单
                                    sz=amount,
                                    td_mode='cross',  # 全仓杠杆
                                    tgtCcy='quote_ccy'  # 按USDT金额下单
                                )
                            else:
                                # 卖出时，使用BTC数量而不是USDT金额
                                # 先获取当前价格，计算BTC数量
                                current_price = float(price)
                                btc_amount = 1 / current_price  # 1 USDT worth of BTC
                                # 确保BTC数量不小于最小订单金额 (0.0001 BTC)
                                min_btc_amount = 0.0001
                                if btc_amount < min_btc_amount:
                                    btc_amount = min_btc_amount
                                # 格式化BTC数量，保留4位小数
                                btc_amount_str = f"{btc_amount:.4f}"
                                # 构建订单参数，不包含tgtCcy
                                order_params = {
                                    'instId': inst_id,
                                    'tdMode': 'cross',
                                    'side': side,
                                    'ordType': 'market',
                                    'sz': btc_amount_str
                                }
                                logger.info(f"卖出订单参数: {order_params}")
                                order_id = await self.rest_client.place_order(
                                    inst_id=inst_id,
                                    side=side,
                                    ord_type='market',  # 市价单
                                    sz=btc_amount_str,  # BTC数量
                                    td_mode='cross',  # 全仓杠杆
                                    tgtCcy=''  # 卖出时不使用tgtCcy参数
                                )
                            
                            if order_id:
                                logger.info(f"✅ 下单成功，订单ID: {order_id}")
                            else:
                                logger.error("❌ 下单失败")
                        except Exception as e:
                            logger.error(f"❌ 下单异常: {e}")
                    else:
                        logger.info("策略信号: 中性 (无交易)")
                else:
                    logger.error("获取行情数据失败")
                
                # 等待一段时间再继续
                logger.info("\n等待下一次执行...")
                await asyncio.sleep(60)  # 每分钟执行一次
                
        except KeyboardInterrupt:
            logger.info("\n用户中断，停止策略")
        except Exception as e:
            logger.error(f"运行策略时出错: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 停止策略
            if self.strategy:
                self.strategy.stop()
            # 清理REST客户端
            if hasattr(self.rest_client, 'session') and self.rest_client.session:
                await self.rest_client.session.close()
            logger.info("策略已停止")


async def main():
    """主函数"""
    logger.info("开始执行主函数...")
    trader = NuclearStrategyTrader()
    
    # 设置交易环境
    logger.info("开始设置交易环境...")
    setup_success = await trader.setup()
    if not setup_success:
        logger.error("设置失败，退出")
        return
    logger.info("交易环境设置成功")
    
    # 运行策略
    logger.info("开始运行策略...")
    await trader.run()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
