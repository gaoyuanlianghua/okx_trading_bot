import os
import sys
import json
import hjson
import subprocess
import time
import logging
from strategies.base_strategy import BaseStrategy

logger = logging.getLogger("Strategy")

# 添加passivbot到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'passivbot', 'src'))

class PassivbotIntegrator(BaseStrategy):
    """passivbot策略集成器，用于将passivbot策略与OKX API客户端结合"""
    
    def __init__(self, api_client=None, config=None):
        """
        初始化passivbot集成器
        
        Args:
            api_client (OKXAPIClient): OKX API客户端实例
            config (dict, optional): 策略配置
        """
        super().__init__(api_client, config)
        
        self.config_path = config.get('config_path') if config else None
        self.api_keys_path = config.get('api_keys_path') if config else None
        if not self.api_keys_path:
            self.api_keys_path = os.path.join(os.path.dirname(__file__), 'passivbot', 'api-keys.json')
        
        # 默认配置
        self.default_config = {
            'broker': 'okx',
            'symbol': 'BTC-USDT-SWAP',
            'timeframe': '1h',
            'start_time': '2024-01-01',
            'end_time': '2024-12-31',
            'strategy': 'default'
        }
        
        # 交易统计
        self.trade_stats = {
            'daily_trades': 0,
            'daily_loss': 0,
            'consecutive_losses': 0,
            'last_reset_time': time.time()
        }
        
        # 订单参数验证配置
        self.order_param_config = {
            'min_order_sizes': {
                'BTC-USDT-SWAP': 0.001,
                'ETH-USDT-SWAP': 0.01
            },
            'max_order_sizes': {
                'BTC-USDT-SWAP': 100,
                'ETH-USDT-SWAP': 1000
            },
            'price_precisions': {
                'BTC-USDT-SWAP': 2,
                'ETH-USDT-SWAP': 2
            }
        }
        
        # 风险管理器（简化版）
        class SimpleRiskManager:
            def __init__(self, api_client=None, risk_params=None):
                self.api_client = api_client
                self.risk_params = risk_params or {}
            
            def assess_overall_risk(self):
                # 简化实现，返回基本风险评估
                return {
                    'is_account_healthy': True,
                    'account_balance': 10000  # 假设账户余额
                }
            
            def check_order_risk(self, order_info):
                # 简化实现，返回风险检查结果
                return True, "风险检查通过"
            
            def update_risk_params(self, **kwargs):
                self.risk_params.update(kwargs)
        
        self.risk_manager = SimpleRiskManager(api_client)
        
        logger.info("passivbot集成器初始化完成")
    
    def load_passivbot_config(self, config_path=None):
        """加载passivbot配置文件"""
        config_path = config_path or self.config_path
        if not config_path:
            logger.warning("未指定配置文件路径，使用默认配置")
            return self.default_config
        
        try:
            with open(config_path, 'r') as f:
                config = hjson.load(f)
            logger.info(f"成功加载配置文件: {config_path}")
            return config
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return self.default_config
    
    def setup_api_keys(self, api_keys=None):
        """设置API密钥文件"""
        if api_keys:
            try:
                with open(self.api_keys_path, 'w') as f:
                    json.dump(api_keys, f, indent=2)
                logger.info(f"成功写入API密钥到: {self.api_keys_path}")
                return True
            except Exception as e:
                logger.error(f"写入API密钥失败: {e}")
                return False
        
        # 如果没有提供API密钥，尝试使用环境变量创建
        try:
            api_keys = {
                'okx': {
                    'api_key': self.api_client.api_key,
                    'secret': self.api_client.api_secret,
                    'password': self.api_client.passphrase
                }
            }
            
            with open(self.api_keys_path, 'w') as f:
                json.dump(api_keys, f, indent=2)
            logger.info(f"使用环境变量创建API密钥文件: {self.api_keys_path}")
            return True
        except Exception as e:
            logger.error(f"使用环境变量创建API密钥文件失败: {e}")
            return False
    
    def download_market_data(self, symbol=None, timeframe='1h', start_time='2024-01-01', end_time=None):
        """下载市场数据用于回测"""
        symbol = symbol or self.default_config['symbol']
        
        logger.info(f"开始下载市场数据: {symbol}, {timeframe}, {start_time} → {end_time}")
        
        try:
            # 使用命令行调用passivbot的下载功能
            passivbot_script = os.path.join(os.path.dirname(__file__), 'passivbot', 'src', 'main.py')
            cmd = [
                sys.executable, passivbot_script,
                '--download-only',
                '--broker', 'okx',
                '--symbol', symbol,
                '--timeframe', timeframe,
                '--start-date', start_time,
                '--end-date', end_time or '',
                '--api-keys-path', self.api_keys_path
            ]
            
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"市场数据下载完成: {symbol}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"下载市场数据失败: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"下载市场数据失败: {e}")
            return False
    
    def run_backtest(self, config_path=None, symbol=None, timeframe='1h'):
        """运行回测"""
        symbol = symbol or self.default_config['symbol']
        config = self.load_passivbot_config(config_path)
        
        logger.info(f"开始回测: {symbol}, {timeframe}")
        
        try:
            # 使用命令行调用passivbot的回测功能
            passivbot_script = os.path.join(os.path.dirname(__file__), 'passivbot', 'src', 'main.py')
            cmd = [
                sys.executable, passivbot_script,
                '--backtest',
                '--broker', 'okx',
                '--symbol', symbol,
                '--timeframe', timeframe,
                '--config-path', config_path or '',
                '--api-keys-path', self.api_keys_path
            ]
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"回测完成: {symbol}")
            logger.debug(f"回测输出: {result.stdout}")
            return {"success": True, "output": result.stdout}
        except subprocess.CalledProcessError as e:
            logger.error(f"回测失败: {e.stderr}")
            return {"success": False, "error": e.stderr}
        except Exception as e:
            logger.error(f"回测失败: {e}")
            return {"success": False, "error": str(e)}
    
    def run_live_trading(self, config_path=None, symbol=None):
        """运行实盘交易"""
        symbol = symbol or self.default_config['symbol']
        config = self.load_passivbot_config(config_path)
        
        logger.info(f"开始实盘交易: {symbol}")
        
        try:
            # 使用命令行调用passivbot的实盘交易功能
            passivbot_script = os.path.join(os.path.dirname(__file__), 'passivbot', 'src', 'main.py')
            cmd = [
                sys.executable, passivbot_script,
                '--live',
                '--broker', 'okx',
                '--symbol', symbol,
                '--config-path', config_path or '',
                '--api-keys-path', self.api_keys_path
            ]
            
            # 以非阻塞方式启动实盘交易
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            logger.info(f"实盘交易运行中: {symbol}, PID: {process.pid}")
            return {"success": True, "pid": process.pid, "process": process}
        except Exception as e:
            logger.error(f"启动实盘交易失败: {e}")
            return {"success": False, "error": str(e)}
    
    def create_default_config(self, symbol='BTC-USDT-SWAP', output_path=None):
        """创建默认配置文件"""
        output_path = output_path or os.path.join(os.path.dirname(__file__), 'passivbot_config.hjson')
        
        # 默认passivbot配置模板
        default_config = {
            'okx': {
                symbol: {
                    'strategy': 'long_short',
                    'timeframe': '1h',
                    'leverage': 10,
                    'position_mode': 'hedge',
                    'long': {
                        'enabled': True,
                        'grid_span': 0.02,
                        'grid_levels': 50,
                        'max_position': 1.0,
                        'entry_amount': 0.001,
                        'profit_taking': 0.005,
                        'stop_loss': 0.05
                    },
                    'short': {
                        'enabled': True,
                        'grid_span': 0.02,
                        'grid_levels': 50,
                        'max_position': 1.0,
                        'entry_amount': 0.001,
                        'profit_taking': 0.005,
                        'stop_loss': 0.05
                    }
                }
            }
        }
        
        try:
            with open(output_path, 'w') as f:
                hjson.dump(default_config, f)
            logger.info(f"默认配置文件创建成功: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"创建默认配置文件失败: {e}")
            return None
    
    def optimize_strategy(self, symbol='BTC-USDT-SWAP', timeframe='1h', 
                        start_time='2024-01-01', end_time='2024-12-31'):
        """优化策略参数"""
        logger.info(f"开始优化策略: {symbol}, {timeframe}")
        
        try:
            # 使用命令行调用passivbot的优化功能
            passivbot_script = os.path.join(os.path.dirname(__file__), 'passivbot', 'src', 'main.py')
            cmd = [
                sys.executable, passivbot_script,
                '--optimize',
                '--broker', 'okx',
                '--symbol', symbol,
                '--timeframe', timeframe,
                '--start-date', start_time,
                '--end-date', end_time,
                '--api-keys-path', self.api_keys_path
            ]
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"策略优化完成: {symbol}")
            logger.debug(f"优化输出: {result.stdout}")
            return {"success": True, "output": result.stdout}
        except subprocess.CalledProcessError as e:
            logger.error(f"策略优化失败: {e.stderr}")
            return {"success": False, "error": e.stderr}
        except Exception as e:
            logger.error(f"策略优化失败: {e}")
            return {"success": False, "error": str(e)}
    
    def stop_trading(self, bot_instance):
        """停止交易机器人"""
        if bot_instance and isinstance(bot_instance, dict) and 'process' in bot_instance:
            try:
                # 尝试停止机器人进程
                process = bot_instance['process']
                process.terminate()
                process.wait(timeout=5)
                logger.info(f"交易机器人已停止，PID: {process.pid}")
                return True
            except subprocess.TimeoutExpired:
                process.kill()
                logger.info(f"交易机器人已强制停止，PID: {process.pid}")
                return True
            except Exception as e:
                logger.error(f"停止交易机器人失败: {e}")
                return False
        return False
    
    def execute(self, market_data):
        """执行策略，生成交易信号
        
        Args:
            market_data (dict): 市场数据
            
        Returns:
            dict: 交易信号，包含side, price, amount等信息
        """
        # 由于passivbot是独立运行的，这里返回None表示不生成交易信号
        # 实际的交易决策由passivbot独立处理
        logger.debug("Passivbot策略执行 - 由独立进程处理")
        return None
    
    def validate_order_params(self, order_info):
        """验证订单参数是否符合OKX API要求
        
        Args:
            order_info (dict): 订单信息
            
        Returns:
            tuple: (是否有效, 错误信息)
        """
        inst_id = order_info['inst_id']
        order_size = float(order_info['sz'])
        price = float(order_info['px'])
        
        # 检查订单大小
        min_size = self.order_param_config['min_order_sizes'].get(inst_id, 0.001)
        max_size = self.order_param_config['max_order_sizes'].get(inst_id, 100)
        
        if order_size < min_size:
            return False, f"订单大小小于最小限制: {min_size}"
        if order_size > max_size:
            return False, f"订单大小超过最大限制: {max_size}"
        
        # 检查价格精度
        price_precision = self.order_param_config['price_precisions'].get(inst_id, 2)
        if not self.is_price_valid(price, price_precision):
            return False, f"价格精度不符合要求，需要 {price_precision} 位小数"
        
        return True, "订单参数验证通过"
    
    def is_price_valid(self, price, precision):
        """检查价格是否符合精度要求
        
        Args:
            price (float): 价格
            precision (int): 精度（小数位数）
            
        Returns:
            bool: 是否有效
        """
        try:
            # 检查价格是否可以表示为指定精度的小数
            formatted_price = f"{price:.{precision}f}"
            return abs(float(formatted_price) - price) < 1e-9
        except Exception:
            return False
    
    def check_strategy_risk(self):
        """检查策略级别的风险
        
        Returns:
            tuple: (是否通过, 原因)
        """
        # 检查是否需要重置每日统计
        current_time = time.time()
        if current_time - self.trade_stats['last_reset_time'] > 86400:  # 24小时
            self.trade_stats['daily_trades'] = 0
            self.trade_stats['daily_loss'] = 0
            self.trade_stats['last_reset_time'] = current_time
        
        # 检查每日交易次数
        daily_trades = self.trade_stats['daily_trades']
        max_daily_trades = 100  # 默认最大值
        if daily_trades > max_daily_trades:
            logger.warning(f"每日交易次数超过限制: {daily_trades} > {max_daily_trades}")
            return False, "每日交易次数超过限制"
        
        return True, "策略风险检查通过"
    
    def update_trade_stats(self, trade_result):
        """更新交易统计
        
        Args:
            trade_result (dict): 交易结果
        """
        # 更新每日交易次数
        self.trade_stats['daily_trades'] += 1
        
        # 更新盈亏
        profit = trade_result.get('profit', 0)
        if profit < 0:
            self.trade_stats['daily_loss'] += abs(profit)
            self.trade_stats['consecutive_losses'] += 1
        else:
            self.trade_stats['consecutive_losses'] = 0
        
        logger.debug(f"交易统计更新: {self.trade_stats}")
    
    def run_live_trading(self, config_path=None, symbol=None):
        """运行实盘交易"""
        symbol = symbol or self.default_config['symbol']
        config = self.load_passivbot_config(config_path)
        
        # 策略风险检查
        is_strategy_safe, strategy_reason = self.check_strategy_risk()
        if not is_strategy_safe:
            logger.warning(f"⚠️ 策略风险检查失败: {strategy_reason}")
            return {"success": False, "error": strategy_reason}
        
        logger.info(f"开始实盘交易: {symbol}")
        
        try:
            # 使用命令行调用passivbot的实盘交易功能
            passivbot_script = os.path.join(os.path.dirname(__file__), 'passivbot', 'src', 'main.py')
            cmd = [
                sys.executable, passivbot_script,
                '--live',
                '--broker', 'okx',
                '--symbol', symbol,
                '--config-path', config_path or '',
                '--api-keys-path', self.api_keys_path
            ]
            
            # 以非阻塞方式启动实盘交易
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            logger.info(f"实盘交易运行中: {symbol}, PID: {process.pid}")
            return {"success": True, "pid": process.pid, "process": process}
        except Exception as e:
            logger.error(f"启动实盘交易失败: {e}")
            return {"success": False, "error": str(e)}

if __name__ == "__main__":
    # 测试passivbot集成器
    from core import OKXRESTClient
    
    try:
        # 创建API客户端
        api_client = OKXRESTClient(is_test=True)
        
        # 创建集成器
        integrator = PassivbotIntegrator(api_client)
        
        # 创建默认配置
        config_path = integrator.create_default_config()
        logger.info(f"创建的默认配置: {config_path}")
        
        # 测试加载配置
        config = integrator.load_passivbot_config(config_path)
        logger.info(f"加载的配置: {json.dumps(config, indent=2)}")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
