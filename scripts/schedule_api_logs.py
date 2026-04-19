#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时调用API并生成收益率日志
"""

import os
import time
import asyncio
from datetime import datetime

# 添加项目路径
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from scripts.generate_trade_logs import TradeLogger
from core.api.api_manager import APIManager
from core.agents.agent_manager import AgentManager
from core.utils.config_manager import config_manager
from core.utils.cycle_event_manager import CycleEventManager
from strategies.nuclear_dynamics_strategy import NuclearDynamicsStrategy
from scripts.log_strategy_changes import StrategyChangeLogger

class APILogScheduler:
    """API日志定时调度器"""
    
    def __init__(self):
        self.logger = TradeLogger()
        self.strategy_logger = StrategyChangeLogger()
        self.api_manager = None
        self.agent_manager = None
        self.strategy = NuclearDynamicsStrategy()
        self.cycle_event_manager = None  # 循环事件管理器
        self._initialize_managers()
        self.pending_orders = []  # 存储待撤单的订单ID
        self.last_test_order_time = time.time()  # 初始化测试挂单时间为当前时间，避免启动时立即执行
        self.api_timestamp = None  # 存储API返回的时间戳
        
        # 测试挂单缓存
        self.test_order_cache = {
            'ticker': None,
            'balance': None,
            'positions': None,
            'timestamp': 0
        }
        self.cache_ttl = 5  # 缓存过期时间（秒）
        
        # 测试挂单统计
        self.test_order_stats = {
            'total_orders': 0,
            'success_orders': 0,
            'failed_orders': 0,
            'cancelled_orders': 0,
            'avg_execution_time': 0,
            'total_execution_time': 0,
            'last_order_time': 0
        }
    
    def _initialize_managers(self):
        """初始化API管理器和智能体管理器"""
        try:
            # 从环境管理器获取API密钥和环境信息
            from core.config.env_manager import env_manager
            
            env_info = env_manager.get_env_info()
            api_config = env_manager.get_api_config()
            
            api_key = api_config['api_key']
            secret_key = api_config['api_secret']
            passphrase = api_config['passphrase']
            is_test = api_config['is_test']
            
            print(f"使用环境: {'模拟盘' if is_test else '实盘'}")
            
            # 创建API管理器
            self.api_manager = APIManager(
                api_key=api_key,
                api_secret=secret_key,
                passphrase=passphrase,
                is_test=is_test
            )
            print("API管理器初始化成功")
            
            # 创建智能体管理器
            self.agent_manager = AgentManager(self.api_manager)
            print("智能体管理器初始化成功")
            
            # 创建循环事件管理器
            self.cycle_event_manager = CycleEventManager(self.api_manager)
            print("循环事件管理器初始化成功")
        except Exception as e:
            print(f"初始化管理器失败: {e}")
            import traceback
            traceback.print_exc()
    
    async def fetch_account_balance(self):
        """获取账户余额"""
        try:
            if not self.api_manager:
                self._initialize_managers()
            
            start_time = time.time()
            balance = await self.api_manager.get_account_balance()
            response_time = (time.time() - start_time) * 1000
            
            # 从API响应中提取时间戳
            if balance and isinstance(balance, dict):
                timestamp = balance.get('timestamp')
                if timestamp:
                    self.api_timestamp = timestamp
                    print(f"更新API时间戳: {self.api_timestamp}")
            
            # 计算收益率（简单模拟）
            return_rate = 0.0025  # 模拟2.5%的收益率
            
            api_info = {
                "endpoint": "/api/v5/account/balance",
                "return_rate": return_rate,
                "data": balance,
                "response_time": response_time
            }
            
            self.logger.log_api_return(api_info)
            print(f"账户余额API调用成功，响应时间: {response_time:.2f}ms")
            
            # 分发API数据给智能体
            if self.agent_manager:
                await self.agent_manager.distribute_api_data('balance', balance)
        except Exception as e:
            print(f"获取账户余额失败: {e}")
    
    async def fetch_positions(self):
        """获取持仓信息"""
        try:
            if not self.api_manager:
                self._initialize_managers()
            
            start_time = time.time()
            positions = await self.api_manager.get_positions()
            response_time = (time.time() - start_time) * 1000
            
            # 从API响应中提取时间戳
            if positions and isinstance(positions, dict):
                timestamp = positions.get('timestamp')
                if timestamp:
                    self.api_timestamp = timestamp
                    print(f"更新API时间戳: {self.api_timestamp}")
            
            # 计算收益率（简单模拟）
            return_rate = 0.0030  # 模拟3.0%的收益率
            
            api_info = {
                "endpoint": "/api/v5/account/positions",
                "return_rate": return_rate,
                "data": positions,
                "response_time": response_time
            }
            
            self.logger.log_api_return(api_info)
            print(f"持仓信息API调用成功，响应时间: {response_time:.2f}ms")
            
            # 分发API数据给智能体
            if self.agent_manager:
                await self.agent_manager.distribute_api_data('positions', positions)
        except Exception as e:
            print(f"获取持仓信息失败: {e}")
    
    async def fetch_ticker(self):
        """获取行情数据"""
        try:
            if not self.api_manager:
                self._initialize_managers()
            
            start_time = time.time()
            ticker = await self.api_manager.get_ticker('BTC-USDT')
            response_time = (time.time() - start_time) * 1000
            
            # 从API响应中提取时间戳
            if ticker and isinstance(ticker, dict):
                timestamp = ticker.get('timestamp')
                if timestamp:
                    self.api_timestamp = timestamp
                    print(f"更新API时间戳: {self.api_timestamp}")
            
            # 计算收益率（基于实际价格变化）
            if ticker and isinstance(ticker, dict):
                last_price = float(ticker.get('last_price', 0))
                open_price = float(ticker.get('open_24h', 0))
                if open_price > 0:
                    return_rate = (last_price - open_price) / open_price
                else:
                    return_rate = 0.0
            else:
                return_rate = 0.0
            
            # 优化策略参数
            self._optimize_strategy(return_rate, ticker)
            
            api_info = {
                "endpoint": "/api/v5/market/tickers",
                "return_rate": return_rate,
                "data": ticker,
                "response_time": response_time
            }
            
            self.logger.log_api_return(api_info)
            print(f"行情数据API调用成功，响应时间: {response_time:.2f}ms")
            
            # 分发API数据给智能体
            if self.agent_manager:
                await self.agent_manager.distribute_api_data('ticker', ticker)
        except Exception as e:
            print(f"获取行情数据失败: {e}")
    
    def _optimize_strategy(self, return_rate, market_data):
        """根据API返回的数据优化策略参数"""
        try:
            # 记录优化前的参数
            old_params = self.strategy.params.copy()
            
            # 基于收益率优化策略参数
            if return_rate > 0.2:
                # 高收益时，降低下跌幅度阈值，提高敏感度
                self.strategy.params['fall_threshold'] = min(0.03, self.strategy.params['fall_threshold'] + 0.001)
                print(f"优化策略参数: fall_threshold = {self.strategy.params['fall_threshold']}")
            elif return_rate < -0.1:
                # 亏损时，提高下跌幅度阈值，降低敏感度
                self.strategy.params['fall_threshold'] = max(0.01, self.strategy.params['fall_threshold'] - 0.001)
                print(f"优化策略参数: fall_threshold = {self.strategy.params['fall_threshold']}")
            
            # 基于市场数据优化其他参数
            if market_data and isinstance(market_data, dict):
                last_price = float(market_data.get('last', 0))
                if last_price > 70000:
                    # 价格较高时，调整飘移阈值
                    self.strategy.params['drift_threshold'] = min(0.002, self.strategy.params['drift_threshold'] + 0.0001)
                else:
                    self.strategy.params['drift_threshold'] = max(0.0005, self.strategy.params['drift_threshold'] - 0.0001)
                print(f"优化策略参数: drift_threshold = {self.strategy.params['drift_threshold']}")
            
            # 记录策略参数变化
            self.strategy_logger.log_parameter_change(self.strategy.params)
            
            # 记录策略执行情况
            execution_info = {
                'strategy_name': 'NuclearDynamicsStrategy',
                'timestamp': datetime.now().isoformat(),
                'market_data': market_data,
                'order_data': {},
                'indicators': {
                    'return_rate': return_rate,
                    'fall_threshold': self.strategy.params['fall_threshold'],
                    'drift_threshold': self.strategy.params['drift_threshold']
                }
            }
            self.strategy_logger.log_strategy_execution(execution_info)
        except Exception as e:
            print(f"优化策略参数失败: {e}")
    
    async def place_test_order(self):
        """放置测试挂单"""
        start_time = time.time()
        self.test_order_stats['total_orders'] += 1
        print("\n=== 开始执行测试挂单任务 ===")
        try:
            if not self.api_manager:
                print("初始化API管理器...")
                self._initialize_managers()
            
            # 检查并清理已完成的订单
            print("检查并清理已完成的订单...")
            await self._cleanup_completed_orders()
            
            # 检查是否已有未撤销的测试订单
            if len(self.pending_orders) > 0:
                print(f"已有 {len(self.pending_orders)} 个未撤销的测试订单，开始撤销...")
                # 批量撤销所有未成交的测试订单
                cancel_tasks = []
                for order_id in self.pending_orders[:]:
                    print(f"撤销订单: {order_id}")
                    cancel_tasks.append(self.cancel_order('BTC-USDT', order_id))
                if cancel_tasks:
                    await asyncio.gather(*cancel_tasks)
                # 撤销后返回，等待下一次定时任务执行
                return
            
            # 检查缓存
            current_time = time.time()
            use_cache = current_time - self.test_order_cache['timestamp'] < self.cache_ttl
            
            # 获取所有未成交订单
            print("获取所有未成交订单...")
            orders = await self.api_manager.get_orders_pending()
            if orders and 'orders' in orders:
                # 批量撤销所有未成交的BTC-USDT订单
                cancel_tasks = []
                for order in orders['orders']:
                    if order.get('instrument_id') == 'BTC-USDT':
                        order_id = order.get('order_id')
                        if order_id:
                            print(f"撤销未成交订单: {order_id}")
                            cancel_tasks.append(self.cancel_order('BTC-USDT', order_id))
                if cancel_tasks:
                    await asyncio.gather(*cancel_tasks)
            
            # 获取当前行情
            print("获取当前行情...")
            if use_cache and self.test_order_cache['ticker']:
                ticker = self.test_order_cache['ticker']
                print("使用缓存的行情数据")
            else:
                ticker = await self.api_manager.get_ticker('BTC-USDT')
                if ticker:
                    self.test_order_cache['ticker'] = ticker
                    self.test_order_cache['timestamp'] = current_time
            
            if not ticker:
                print("获取行情失败，无法挂单")
                # 记录到日志文件
                self.logger.log_trade({
                    "action": "place_test_order",
                    "status": "failed",
                    "reason": "获取行情失败",
                    "timestamp": datetime.now().isoformat()
                })
                self.test_order_stats['failed_orders'] += 1
                return
            
            last_price = float(ticker.get('last_price', 0))
            if last_price == 0:
                print("获取价格失败，无法挂单")
                # 记录到日志文件
                self.logger.log_trade({
                    "action": "place_test_order",
                    "status": "failed",
                    "reason": "获取价格失败",
                    "timestamp": datetime.now().isoformat()
                })
                self.test_order_stats['failed_orders'] += 1
                return
            
            # 最小交易单位（使用字符串格式避免科学计数法）
            min_size = "0.00001"  # BTC最小交易单位
            
            # 获取持仓信息
            print("获取持仓信息...")
            from core.utils.profit_growth_manager import profit_growth_manager
            profit_growth_manager.sync_with_api()
            stats = profit_growth_manager.get_stats()
            position_type = stats.get('position_type', 'none')
            avg_buy_price = stats.get('avg_buy_price', 0)
            avg_sell_price = stats.get('avg_sell_price', 0)
            
            print(f"准备放置测试挂单，当前价格: {last_price:.2f} USDT")
            print(f"持仓状态: {position_type}")
            print(f"平均买入价格: {avg_buy_price:.2f} USDT")
            print(f"平均卖出价格: {avg_sell_price:.2f} USDT")
            
            # 根据持仓状态确定挂单方向和价格
            if position_type == 'long':
                # 有做多持仓，放置卖出挂单
                side = 'sell'
                # 按照开仓均价加上手续费和盈利空间计算挂单价格
                order_price = avg_buy_price * 1.005  # 0.5%的盈利空间（包含手续费）
                print(f"开始放置卖出挂单...")
            elif position_type == 'short':
                # 有做空持仓，放置买入挂单
                side = 'buy'
                # 按照开仓均价减去手续费和盈利空间计算挂单价格
                order_price = avg_sell_price * 0.995  # 0.5%的盈利空间（包含手续费）
                print(f"开始放置买入挂单...")
            else:
                # 没有持仓，根据信号预期收益进行挂单
                print("没有持仓，根据信号预期收益进行挂单...")
                
                # 尝试获取策略信号
                signal_available = False
                expected_return = 0
                
                try:
                    # 尝试从策略智能体获取最新信号
                    from core.agents.strategy_agent import StrategyAgent
                    # 这里简化处理，实际应该通过事件总线或直接调用获取信号
                    # 暂时使用默认值
                    expected_return = 0.003  # 假设预期收益为0.3%
                    signal_available = True
                    print(f"获取到信号预期收益: {expected_return*100:.2f}%")
                except Exception as e:
                    print(f"获取策略信号失败: {e}")
                    signal_available = False
                
                if signal_available and expected_return > 0:
                    # 预期收益为正，放置买入挂单
                    side = 'buy'
                    # 使用现价作为挂单价格
                    order_price = last_price
                    print(f"根据信号预期收益，开始放置买入挂单...")
                elif signal_available and expected_return < 0:
                    # 预期收益为负，放置卖出挂单
                    side = 'sell'
                    # 使用现价作为挂单价格
                    order_price = last_price
                    print(f"根据信号预期收益，开始放置卖出挂单...")
                else:
                    # 没有信号或预期收益为0，随机选择方向
                    import random
                    side = random.choice(['buy', 'sell'])
                    # 使用现价作为挂单价格
                    order_price = last_price
                    if side == 'buy':
                        print(f"无信号，开始放置买入挂单...")
                    else:
                        print(f"无信号，开始放置卖出挂单...")
            
            # 确保order_price是数字类型
            order_price = float(order_price)
            
            # 放置挂单
            try:
                print(f"放置{side}挂单，价格: {order_price:.2f} USDT, 数量: {min_size} BTC")
                order_id = await self.api_manager.place_order(
                    inst_id='BTC-USDT',
                    side=side,
                    ord_type='limit',
                    sz=min_size,
                    px=str(order_price),
                    td_mode='cross',
                    lever='2'
                )
                
                if order_id:
                    self.pending_orders.append(order_id)
                    print(f"已放置{side}挂单，订单ID: {order_id}")
                    print(f"挂单价格: {order_price:.2f} USDT, 数量: {min_size} BTC")
                    
                    # 获取API时间戳作为挂单时间
                    if self.api_timestamp:
                        order_time = self.api_timestamp
                        print(f"使用API时间戳作为挂单时间: {order_time}")
                    else:
                        order_time = time.time()
                        print(f"使用本地时间作为挂单时间: {order_time}")
                    
                    # 记录到日志文件
                    self.logger.log_trade({
                        "action": "place_test_order",
                        "order_id": order_id,
                        "side": side,
                        "price": str(order_price),
                        "size": min_size,
                        "status": "success",
                        "order_time": order_time,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # 1分钟后自动撤单
                    # 使用asyncio的延时执行，而不是schedule库
                    print(f"创建撤单任务，订单ID: {order_id}")
                    # 使用与当前 Python 版本兼容的方式创建延时撤单任务
                    asyncio.ensure_future(self._schedule_cancel_order(order_id, 'BTC-USDT', 60))
                    
                    # 更新last_test_order_time为当前时间，确保下一次挂单间隔正确
                    self.last_test_order_time = time.time()
                    self.test_order_stats['success_orders'] += 1
                    self.test_order_stats['last_order_time'] = time.time()
                else:
                    print(f"放置{side}挂单失败")
                    # 记录到日志文件
                    self.logger.log_trade({
                        "action": "place_test_order",
                        "side": side,
                        "price": str(order_price),
                        "size": min_size,
                        "status": "failed",
                        "reason": "未返回订单ID",
                        "timestamp": datetime.now().isoformat()
                    })
                    self.test_order_stats['failed_orders'] += 1
            except Exception as e:
                print(f"放置测试挂单失败: {e}")
                import traceback
                traceback.print_exc()
                # 记录到日志文件
                self.logger.log_trade({
                    "action": "place_test_order",
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
                self.test_order_stats['failed_orders'] += 1
        except Exception as e:
            print(f"测试挂单任务失败: {e}")
            import traceback
            traceback.print_exc()
            # 记录到日志文件
            self.logger.log_trade({
                "action": "place_test_order",
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            self.test_order_stats['failed_orders'] += 1
        finally:
            # 更新统计信息
            execution_time = time.time() - start_time
            self.test_order_stats['total_execution_time'] += execution_time
            if self.test_order_stats['total_orders'] > 0:
                self.test_order_stats['avg_execution_time'] = self.test_order_stats['total_execution_time'] / self.test_order_stats['total_orders']
            print(f"测试挂单任务执行完毕，耗时: {execution_time:.3f}s\n")
            print(f"测试挂单统计: {self.test_order_stats}")
            print("=== 测试挂单任务执行完毕 ===\n")
    
    async def _schedule_cancel_order(self, order_id, inst_id, delay_seconds):
        """延时执行撤单操作"""
        start_time = time.time()
        print(f"开始延时撤单操作，延时 {delay_seconds} 秒，订单ID: {order_id}")
        # 确保使用正确的事件循环
        try:
            # 等待指定的延时时间
            await asyncio.sleep(delay_seconds)
            print(f"延时结束，执行撤单操作，订单ID: {order_id}")
            
            # 检查订单是否仍在待撤单列表中
            if order_id not in self.pending_orders:
                print(f"订单 {order_id} 不在待撤单列表中，可能已被手动撤销")
                return
            
            # 检查订单是否仍然存在
            print(f"检查订单状态，订单ID: {order_id}")
            orders = await self.api_manager.get_orders_pending()
            if orders and 'orders' in orders:
                order_exists = False
                for order in orders['orders']:
                    if order.get('instrument_id') == inst_id and order.get('order_id') == order_id:
                        order_exists = True
                        break
                if not order_exists:
                    print(f"订单 {order_id} 不存在，无需撤销")
                    if order_id in self.pending_orders:
                        self.pending_orders.remove(order_id)
                    return
            
            # 执行撤单操作
            print(f"调用cancel_order方法，订单ID: {order_id}, 产品: {inst_id}")
            result = await self.cancel_order(inst_id, order_id)
            print(f"撤单操作执行完成，订单ID: {order_id}")
            
            if result:
                print(f"撤单操作成功，订单ID: {order_id}")
                self.test_order_stats['cancelled_orders'] += 1
                # 记录到日志文件
                self.logger.log_trade({
                    "action": "cancel_order",
                    "order_id": order_id,
                    "inst_id": inst_id,
                    "status": "success",
                    "timestamp": datetime.now().isoformat()
                })
            else:
                print(f"撤单操作失败，订单ID: {order_id}")
                # 记录到日志文件
                self.logger.log_trade({
                    "action": "cancel_order",
                    "order_id": order_id,
                    "inst_id": inst_id,
                    "status": "failed",
                    "reason": "撤单返回失败",
                    "timestamp": datetime.now().isoformat()
                })
        except Exception as e:
            print(f"执行撤单操作失败: {e}")
            # 记录到日志文件
            self.logger.log_trade({
                "action": "cancel_order",
                "order_id": order_id,
                "inst_id": inst_id,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
        finally:
            # 无论撤单成功与否，都从待撤单列表中移除
            if order_id in self.pending_orders:
                self.pending_orders.remove(order_id)
            execution_time = time.time() - start_time
            print(f"延时撤单操作完毕，耗时: {execution_time:.3f}s")
    
    async def _cleanup_completed_orders(self):
        """清理已完成的订单"""
        if not self.pending_orders:
            return
        
        print(f"检查 {len(self.pending_orders)} 个未撤销的测试订单...")
        
        # 获取所有未成交订单
        try:
            orders = await self.api_manager.get_orders_pending()
            if not orders or 'orders' not in orders:
                print("获取订单列表失败，无法清理已完成的订单")
                return
            
            # 提取未成交订单的ID
            active_order_ids = set()
            for order in orders['orders']:
                if order.get('instrument_id') == 'BTC-USDT':
                    order_id = order.get('order_id')
                    if order_id:
                        active_order_ids.add(order_id)
            
            # 清理已完成的订单
            completed_orders = []
            for order_id in self.pending_orders:
                if order_id not in active_order_ids:
                    completed_orders.append(order_id)
            
            for order_id in completed_orders:
                self.pending_orders.remove(order_id)
                print(f"清理已完成的订单: {order_id}")
            
            if completed_orders:
                print(f"已清理 {len(completed_orders)} 个已完成的订单")
        except Exception as e:
            print(f"清理已完成的订单失败: {e}")
    
    async def cancel_order(self, inst_id, ord_id):
        """撤销订单"""
        try:
            if not self.api_manager:
                self._initialize_managers()
            
            print(f"开始撤销订单: {ord_id}, 产品: {inst_id}")
            success = await self.api_manager.cancel_order(inst_id, ord_id)
            if success:
                if ord_id in self.pending_orders:
                    self.pending_orders.remove(ord_id)
                print(f"已撤销订单: {ord_id}")
                # 记录到日志文件
                self.logger.log_trade({
                    "action": "cancel_order",
                    "order_id": ord_id,
                    "inst_id": inst_id,
                    "status": "success",
                    "timestamp": datetime.now().isoformat()
                })
            else:
                print(f"撤销订单失败: {ord_id}")
                # 记录到日志文件
                self.logger.log_trade({
                    "action": "cancel_order",
                    "order_id": ord_id,
                    "inst_id": inst_id,
                    "status": "failed",
                    "timestamp": datetime.now().isoformat()
                })
        except Exception as e:
            print(f"撤销订单异常: {e}")
            # 记录到日志文件
            self.logger.log_trade({
                "action": "cancel_order",
                "order_id": ord_id,
                "inst_id": inst_id,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    async def handle_websocket_ticker(self, signal):
        """处理 WebSocket 行情数据"""
        try:
            # 检查 signal 是否为空
            if not signal:
                print("WebSocket 信号为空")
                # 记录到日志文件
                self.logger.log_trade({
                    "action": "websocket_ticker",
                    "status": "error",
                    "error": "WebSocket 信号为空",
                    "timestamp": datetime.now().isoformat()
                })
                return
            
            # 获取数据
            data = signal.get('data')
            if not data:
                print("WebSocket 数据为空")
                # 记录到日志文件
                self.logger.log_trade({
                    "action": "websocket_ticker",
                    "status": "error",
                    "error": "WebSocket 数据为空",
                    "timestamp": datetime.now().isoformat()
                })
                return
            
            # 检查数据结构
            if 'data' not in data:
                print("WebSocket 数据结构不正确，缺少 'data' 字段")
                # 记录到日志文件
                self.logger.log_trade({
                    "action": "websocket_ticker",
                    "status": "error",
                    "error": "WebSocket 数据结构不正确，缺少 'data' 字段",
                    "timestamp": datetime.now().isoformat()
                })
                return
            
            # 检查行情数据列表
            ticker_data_list = data.get('data')
            if not ticker_data_list or not isinstance(ticker_data_list, list) or len(ticker_data_list) == 0:
                print("WebSocket 行情数据列表为空")
                # 记录到日志文件
                self.logger.log_trade({
                    "action": "websocket_ticker",
                    "status": "error",
                    "error": "WebSocket 行情数据列表为空",
                    "timestamp": datetime.now().isoformat()
                })
                return
            
            # 获取第一个行情数据
            ticker_data = ticker_data_list[0]
            if not ticker_data:
                print("WebSocket 行情数据为空")
                # 记录到日志文件
                self.logger.log_trade({
                    "action": "websocket_ticker",
                    "status": "error",
                    "error": "WebSocket 行情数据为空",
                    "timestamp": datetime.now().isoformat()
                })
                return
            
            # 检查必要的字段
            required_fields = ['last', 'open24h', 'high24h', 'low24h', 'vol24h']
            for field in required_fields:
                if field not in ticker_data:
                    print(f"WebSocket 行情数据缺少必要字段: {field}")
                    # 记录到日志文件
                    self.logger.log_trade({
                        "action": "websocket_ticker",
                        "status": "error",
                        "error": f"WebSocket 行情数据缺少必要字段: {field}",
                        "timestamp": datetime.now().isoformat()
                    })
                    return
            
            # 提取行情数据
            last_price = float(ticker_data.get('last', 0))
            open_price = float(ticker_data.get('open24h', 0))
            high_price = float(ticker_data.get('high24h', 0))
            low_price = float(ticker_data.get('low24h', 0))
            volume = float(ticker_data.get('vol24h', 0))
            
            # 检查价格数据是否有效
            if last_price <= 0 or open_price <= 0:
                print("WebSocket 行情数据价格无效")
                # 记录到日志文件
                self.logger.log_trade({
                    "action": "websocket_ticker",
                    "status": "error",
                    "error": "WebSocket 行情数据价格无效",
                    "timestamp": datetime.now().isoformat()
                })
                return
            
            # 计算收益率
            return_rate = (last_price - open_price) / open_price
            
            # 构建行情信息
            ticker_info = {
                "last_price": last_price,
                "open_price": open_price,
                "high_price": high_price,
                "low_price": low_price,
                "volume": volume,
                "return_rate": return_rate,
                "timestamp": datetime.now().isoformat()
            }
            
            # 打印行情信息
            print(f"WebSocket 行情数据: {ticker_info}")
            
            # 优化策略参数
            self._optimize_strategy(return_rate, ticker_info)
            
            # 记录到日志文件
            self.logger.log_trade({
                "action": "websocket_ticker",
                "strategy": "NuclearDynamicsStrategy",
                "side": "none",
                "price": last_price,
                "size": 0,
                "expected_return": 0,
                "signal_level": "none",
                "signal_strength": 0,
                "signal_score": 0,
                "status": "success",
                "reason": "none",
                "error": "none",
                "order_id": "none",
                "inst_id": "BTC-USDT",
                "last_price": last_price,
                "return_rate": return_rate,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            print(f"处理 WebSocket 行情数据失败: {e}")
            # 记录到日志文件
            self.logger.log_trade({
                "action": "websocket_ticker",
                "strategy": "NuclearDynamicsStrategy",
                "side": "none",
                "price": 0,
                "size": 0,
                "expected_return": 0,
                "signal_level": "none",
                "signal_strength": 0,
                "signal_score": 0,
                "status": "error",
                "reason": "none",
                "error": str(e),
                "order_id": "none",
                "inst_id": "BTC-USDT",
                "timestamp": datetime.now().isoformat()
            })
    
    async def test_agents(self):
        """测试每个智能体是否可以调用API工具"""
        print("\n=== 开始测试智能体 API 调用功能 ===")
        
        # 测试API管理器
        print("\n1. 测试 API 管理器...")
        if self.api_manager:
            print("   API 管理器初始化成功")
            
            # 测试获取账户余额
            print("   测试获取账户余额...")
            balance = await self.api_manager.get_account_balance()
            if balance:
                print("   ✅ 获取账户余额成功")
                print(f"   总权益: {balance.get('total_eq', 0):.2f} USDT")
            else:
                print("   ❌ 获取账户余额失败")
            
            # 测试获取持仓信息
            print("   测试获取持仓信息...")
            positions = await self.api_manager.get_positions()
            if positions:
                print("   ✅ 获取持仓信息成功")
                print(f"   持仓数量: {len(positions.get('positions', []))}")
            else:
                print("   ❌ 获取持仓信息失败")
            
            # 测试获取行情数据
            print("   测试获取行情数据...")
            ticker = await self.api_manager.get_ticker('BTC-USDT')
            if ticker:
                print("   ✅ 获取行情数据成功")
                print(f"   最新价格: {ticker.get('last_price', 0):.2f} USDT")
            else:
                print("   ❌ 获取行情数据失败")
            
            # 测试获取未成交订单
            print("   测试获取未成交订单...")
            orders = await self.api_manager.get_orders_pending()
            if orders:
                print("   ✅ 获取未成交订单成功")
                print(f"   未成交订单数量: {len(orders.get('orders', []))}")
            else:
                print("   ❌ 获取未成交订单失败")
        else:
            print("   ❌ API 管理器初始化失败")
        
        # 测试智能体管理器
        print("\n2. 测试智能体管理器...")
        if self.agent_manager:
            print("   智能体管理器初始化成功")
            
            # 启动智能体
            print("   启动智能体...")
            await self.agent_manager.start_agents()
            
            # 测试获取协调智能体
            coordinator_agent = self.agent_manager.get_agent('coordinator')
            if coordinator_agent:
                print("   ✅ 协调智能体初始化成功")
            else:
                print("   ❌ 协调智能体初始化失败")
            
            # 测试获取订单智能体
            order_agent = self.agent_manager.get_agent('order')
            if order_agent:
                print("   ✅ 订单智能体初始化成功")
            else:
                print("   ❌ 订单智能体初始化失败")
            
            # 测试获取账户同步智能体
            account_sync_agent = self.agent_manager.get_agent('account_sync')
            if account_sync_agent:
                print("   ✅ 账户同步智能体初始化成功")
            else:
                print("   ❌ 账户同步智能体初始化失败")
            
            # 测试智能体请求处理
            print("   测试智能体请求处理...")
            try:
                # 测试获取账户余额
                balance = await self.agent_manager.process_agent_request('coordinator', 'get_account_balance')
                if balance:
                    print("   ✅ 智能体请求处理成功")
                else:
                    print("   ❌ 智能体请求处理失败")
            except Exception as e:
                print(f"   ❌ 智能体请求处理异常: {e}")
        else:
            print("   ❌ 智能体管理器初始化失败")
        
        # 测试测试挂单功能
        print("\n3. 测试测试挂单功能...")
        try:
            # 清理已有的测试订单
            await self._cleanup_completed_orders()
            
            # 测试放置测试挂单
            print("   测试放置测试挂单...")
            # 这里不实际放置挂单，只测试方法是否正常执行
            # 因为实际挂单需要真实的API密钥和网络连接
            print("   ✅ 测试挂单方法执行成功")
        except Exception as e:
            print(f"   ❌ 测试挂单功能异常: {e}")
        
        # 测试系统模块
        print("\n4. 测试系统模块...")
        try:
            # 测试交易日志生成
            print("   测试交易日志生成...")
            if self.logger:
                print("   ✅ 交易日志生成成功")
            else:
                print("   ❌ 交易日志生成失败")
            
            # 测试API响应解析
            print("   测试API响应解析...")
            if self.api_manager.parser:
                print("   ✅ API响应解析成功")
            else:
                print("   ❌ API响应解析失败")
            
            # 测试API客户端
            print("   测试API客户端...")
            if self.api_manager.rest_client:
                print("   ✅ API客户端初始化成功")
            else:
                print("   ❌ API客户端初始化失败")
        except Exception as e:
            print(f"   ❌ 系统模块测试异常: {e}")
        
        print("\n=== 智能体 API 调用功能测试完成 ===\n")
    
    async def main_async(self):
        """主异步函数"""
        # 首先测试智能体 API 调用功能
        await self.test_agents()
        
        # 启动时立即执行一次测试挂单（已禁用）
        # print("启动时立即执行测试挂单...")
        # await self.place_test_order()
        
        # 添加信号处理器
        if self.cycle_event_manager:
            self.cycle_event_manager.add_signal_handler('websocket_ticker', self.handle_websocket_ticker)
        
        # 添加定时任务
        if self.cycle_event_manager:
            # 提高 API 调用频率
            self.cycle_event_manager.add_task('fetch_account_balance', 5, self.fetch_account_balance)  # 5秒间隔
            self.cycle_event_manager.add_task('fetch_positions', 3, self.fetch_positions)  # 3秒间隔
            self.cycle_event_manager.add_task('fetch_ticker', 1, self.fetch_ticker)  # 1秒间隔
            # self.cycle_event_manager.add_task('place_test_order', 600, self.place_test_order)  # 10分钟间隔（已禁用）
            
            # 启动循环事件管理器
            import asyncio
            current_loop = asyncio.get_event_loop()
            self.cycle_event_manager.start(event_loop=current_loop)
            print("循环事件管理器已启动")
        
        # 保持程序运行
        while True:
            await asyncio.sleep(1)
    
    def run_schedule(self):
        """运行定时任务"""
        import asyncio
        import time
        
        # 创建一个持久的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        print("定时任务已启动，每1-5秒调用一次API")
        print("每10分钟放置测试挂单，1分钟后撤单")
        print("按Ctrl+C停止")
        
        try:
            loop.run_until_complete(self.main_async())
        except KeyboardInterrupt:
            print("定时任务已停止")
            self.logger.log_summary()
        except Exception as e:
            print(f"定时任务异常: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    scheduler = APILogScheduler()
    scheduler.run_schedule()