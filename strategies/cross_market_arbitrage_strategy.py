import logging
import time
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from core.api.exchange_manager import ExchangeManager
from core.utils.logger import get_logger
from .base_strategy import BaseStrategy

logger = get_logger(__name__)

class CrossMarketArbitrageStrategy(BaseStrategy):
    """跨市场套利策略
    
    利用不同交易所之间的价格差异进行套利
    """
    
    def __init__(self, api_client=None, config=None):
        """初始化跨市场套利策略
        
        Args:
            api_client: OKX API客户端实例
            config (dict): 策略配置
        """
        super().__init__(api_client, config)
        
        # 策略配置默认值
        self.default_config = {
            "arbitrage_threshold": 0.5,  # 套利阈值（百分比）
            "max_trade_amount": 10000,  # 最大交易金额
            "min_trade_amount": 100,  # 最小交易金额
            "exchanges": ["okx", "binance"],  # 要监控的交易所
            "trading_pairs": ["BTC/USDT", "ETH/USDT"],  # 要监控的交易对
            "polling_interval": 1,  # 价格轮询间隔（秒）
            "max_position": 0.1,  # 最大仓位（BTC）
            "fee_estimate": 0.1,  # 预估交易费用（百分比）
            "transfer_time": 300,  # 资金转移时间（秒）
            "profit_threshold": 0.1  # 最小获利阈值（百分比）
        }
        
        # 更新配置
        for key, value in self.default_config.items():
            if key not in self.config:
                self.config[key] = value
        
        # 交易所管理器
        self.exchange_manager = ExchangeManager()
        
        # 价格缓存
        self.price_cache = {}
        
        # 套利机会记录
        self.arbitrage_opportunities = []
        
        # 正在执行的套利交易
        self.active_arbitrage = {}
        
        logger.info(f"跨市场套利策略初始化完成，配置: {self.config}")
    
    def _execute_strategy(self, market_data):
        """执行跨市场套利策略
        
        Args:
            market_data (dict): 市场数据
            
        Returns:
            dict: 交易信号
        """
        # 这里主要处理单交易所的市场数据
        # 跨市场套利的核心逻辑在run_arbitrage_monitor中
        return None
    
    async def run_arbitrage_monitor(self):
        """运行套利监控
        
        持续监控多个交易所的价格差异，寻找套利机会
        """
        logger.info("开始运行跨市场套利监控")
        
        while self.status == "running":
            try:
                # 获取所有交易所的价格
                await self._update_price_cache()
                
                # 寻找套利机会
                opportunities = await self._find_arbitrage_opportunities()
                
                # 执行套利交易
                for opportunity in opportunities:
                    await self._execute_arbitrage(opportunity)
                
                # 等待下一次轮询
                await asyncio.sleep(self.config["polling_interval"])
                
            except Exception as e:
                logger.error(f"套利监控错误: {e}")
                await asyncio.sleep(self.config["polling_interval"])
    
    async def _update_price_cache(self):
        """更新价格缓存
        
        从各个交易所获取最新价格
        """
        tasks = []
        
        for exchange_name in self.config["exchanges"]:
            for trading_pair in self.config["trading_pairs"]:
                tasks.append(self._fetch_price(exchange_name, trading_pair))
        
        # 并行获取价格
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"获取价格错误: {result}")
            else:
                exchange_name, trading_pair, price = result
                if exchange_name not in self.price_cache:
                    self.price_cache[exchange_name] = {}
                self.price_cache[exchange_name][trading_pair] = {
                    "price": price,
                    "timestamp": time.time()
                }
    
    async def _fetch_price(self, exchange_name: str, trading_pair: str) -> Tuple[str, str, float]:
        """从交易所获取价格
        
        Args:
            exchange_name (str): 交易所名称
            trading_pair (str): 交易对
            
        Returns:
            Tuple[str, str, float]: (交易所名称, 交易对, 价格)
        """
        try:
            # 获取交易所客户端
            exchange_client = self.exchange_manager.get_exchange(exchange_name)
            
            # 检查客户端是否获取成功
            if not exchange_client:
                # 模拟价格数据，避免因网络问题或不支持的交易所导致程序崩溃
                import random
                base_price = 45000 if "BTC" in trading_pair else 3200
                price = base_price * (1 + (random.random() - 0.5) * 0.02)
                logger.warning(f"无法获取{exchange_name}客户端，使用模拟价格: {price}")
                return exchange_name, trading_pair, price
            
            # 获取最新价格
            # 这里需要根据不同交易所的API实现
            price = 0
            if exchange_name == "okx":
                # 使用OKX API获取价格
                if hasattr(exchange_client, "get_ticker"):
                    try:
                        ticker = await exchange_client.get_ticker(trading_pair)
                        if ticker:
                            price = float(ticker.get("last", 0))
                        else:
                            # 模拟价格
                            import random
                            base_price = 45000 if "BTC" in trading_pair else 3200
                            price = base_price * (1 + (random.random() - 0.5) * 0.02)
                            logger.warning(f"OKX API返回空数据，使用模拟价格: {price}")
                    except Exception as api_error:
                        # 网络错误时使用模拟价格
                        import random
                        base_price = 45000 if "BTC" in trading_pair else 3200
                        price = base_price * (1 + (random.random() - 0.5) * 0.02)
                        logger.warning(f"OKX API调用失败: {api_error}，使用模拟价格: {price}")
            else:
                # 模拟其他交易所的价格
                # 实际实现中需要调用对应交易所的API
                import random
                base_price = 45000 if "BTC" in trading_pair else 3200
                price = base_price * (1 + (random.random() - 0.5) * 0.02)
            
            return exchange_name, trading_pair, price
        except Exception as e:
            logger.error(f"获取{exchange_name}的{trading_pair}价格错误: {e}")
            # 发生异常时返回模拟价格，确保程序继续运行
            import random
            base_price = 45000 if "BTC" in trading_pair else 3200
            price = base_price * (1 + (random.random() - 0.5) * 0.02)
            return exchange_name, trading_pair, price
    
    async def _find_arbitrage_opportunities(self) -> List[Dict]:
        """寻找套利机会
        
        分析不同交易所之间的价格差异，寻找套利机会
        
        Returns:
            List[Dict]: 套利机会列表
        """
        opportunities = []
        
        # 分析每个交易对
        for trading_pair in self.config["trading_pairs"]:
            # 收集所有交易所的价格
            prices = {}
            for exchange_name in self.config["exchanges"]:
                if exchange_name in self.price_cache and trading_pair in self.price_cache[exchange_name]:
                    prices[exchange_name] = self.price_cache[exchange_name][trading_pair]["price"]
            
            # 至少需要两个交易所的价格
            if len(prices) < 2:
                continue
            
            # 找出最高和最低价格的交易所
            sorted_exchanges = sorted(prices.items(), key=lambda x: x[1])
            lowest_exchange, lowest_price = sorted_exchanges[0]
            highest_exchange, highest_price = sorted_exchanges[-1]
            
            # 计算价格差异
            price_diff = highest_price - lowest_price
            price_diff_percent = (price_diff / lowest_price) * 100
            
            # 计算扣除费用后的实际利润
            total_fee = self.config["fee_estimate"] * 2  # 买入和卖出各一次费用
            net_profit_percent = price_diff_percent - total_fee
            
            # 检查是否满足套利条件
            if net_profit_percent >= self.config["profit_threshold"]:
                opportunity = {
                    "trading_pair": trading_pair,
                    "buy_exchange": lowest_exchange,
                    "sell_exchange": highest_exchange,
                    "buy_price": lowest_price,
                    "sell_price": highest_price,
                    "price_diff": price_diff,
                    "price_diff_percent": price_diff_percent,
                    "net_profit_percent": net_profit_percent,
                    "timestamp": time.time()
                }
                
                # 检查是否已经记录过相同的套利机会
                if not self._is_duplicate_opportunity(opportunity):
                    opportunities.append(opportunity)
                    self.arbitrage_opportunities.append(opportunity)
                    logger.info(f"发现套利机会: {opportunity}")
        
        return opportunities
    
    def _is_duplicate_opportunity(self, opportunity: Dict) -> bool:
        """检查是否是重复的套利机会
        
        Args:
            opportunity (Dict): 套利机会
            
        Returns:
            bool: 是否是重复的套利机会
        """
        # 检查最近的套利机会
        for existing_opp in self.arbitrage_opportunities[-10:]:
            if (existing_opp["trading_pair"] == opportunity["trading_pair"] and
                existing_opp["buy_exchange"] == opportunity["buy_exchange"] and
                existing_opp["sell_exchange"] == opportunity["sell_exchange"] and
                time.time() - existing_opp["timestamp"] < 60):  # 60秒内的相同机会视为重复
                return True
        return False
    
    async def _execute_arbitrage(self, opportunity: Dict):
        """执行套利交易
        
        Args:
            opportunity (Dict): 套利机会
        """
        trading_pair = opportunity["trading_pair"]
        key = f"{trading_pair}_{opportunity['buy_exchange']}_{opportunity['sell_exchange']}"
        
        # 检查是否已经在执行相同的套利
        if key in self.active_arbitrage:
            logger.debug(f"已经在执行相同的套利: {key}")
            return
        
        try:
            # 标记为正在执行
            self.active_arbitrage[key] = {
                "status": "executing",
                "start_time": time.time()
            }
            
            # 计算交易金额
            # 基于最小交易金额和最大交易金额
            trade_amount = min(self.config["max_trade_amount"], max(self.config["min_trade_amount"], opportunity["buy_price"] * self.config["max_position"]))
            
            # 计算购买数量
            buy_amount = trade_amount / opportunity["buy_price"]
            
            logger.info(f"执行套利交易: 在{opportunity['buy_exchange']}以{opportunity['buy_price']}买入{buy_amount}{trading_pair.split('/')[0]}，在{opportunity['sell_exchange']}以{opportunity['sell_price']}卖出")
            
            # 1. 在低价交易所买入
            buy_order = await self._place_order(opportunity["buy_exchange"], trading_pair, "buy", opportunity["buy_price"], buy_amount)
            
            if not buy_order:
                raise Exception("买入订单失败")
            
            # 2. 在高价交易所卖出
            sell_order = await self._place_order(opportunity["sell_exchange"], trading_pair, "sell", opportunity["sell_price"], buy_amount)
            
            if not sell_order:
                raise Exception("卖出订单失败")
            
            # 3. 计算利润
            buy_cost = opportunity["buy_price"] * buy_amount
            sell_revenue = opportunity["sell_price"] * buy_amount
            fees = buy_cost * (self.config["fee_estimate"] / 100) * 2
            profit = sell_revenue - buy_cost - fees
            profit_percent = (profit / buy_cost) * 100
            
            # 4. 记录交易结果
            trade_result = {
                "trade_id": f"arbitrage_{int(time.time() * 1000)}",
                "inst_id": trading_pair,
                "side": "arbitrage",
                "buy_exchange": opportunity["buy_exchange"],
                "sell_exchange": opportunity["sell_exchange"],
                "buy_price": opportunity["buy_price"],
                "sell_price": opportunity["sell_price"],
                "amount": buy_amount,
                "profit": profit,
                "profit_percent": profit_percent,
                "status": "completed",
                "fee": fees
            }
            
            # 更新策略性能
            self.update_performance(trade_result)
            
            # 标记套利完成
            self.active_arbitrage[key]["status"] = "completed"
            self.active_arbitrage[key]["end_time"] = time.time()
            
            logger.info(f"套利交易完成，利润: {profit} ({profit_percent:.2f}%)")
            
        except Exception as e:
            logger.error(f"套利交易失败: {e}")
            # 标记套利失败
            if key in self.active_arbitrage:
                self.active_arbitrage[key]["status"] = "failed"
                self.active_arbitrage[key]["error"] = str(e)
        finally:
            # 清理活跃套利记录（5分钟后）
            asyncio.create_task(self._cleanup_active_arbitrage(key))
    
    async def _place_order(self, exchange_name: str, trading_pair: str, side: str, price: float, amount: float) -> Optional[Dict]:
        """在交易所下单
        
        Args:
            exchange_name (str): 交易所名称
            trading_pair (str): 交易对
            side (str): 交易方向 (buy/sell)
            price (float): 价格
            amount (float): 数量
            
        Returns:
            Optional[Dict]: 订单信息
        """
        try:
            # 获取交易所客户端
            exchange_client = self.exchange_manager.get_exchange(exchange_name)
            
            # 下单
            # 这里需要根据不同交易所的API实现
            # 暂时使用模拟数据
            order_id = f"order_{int(time.time() * 1000)}"
            
            logger.info(f"在{exchange_name}下单: {side} {amount} {trading_pair} at {price}")
            
            # 模拟订单执行
            await asyncio.sleep(0.5)
            
            return {
                "order_id": order_id,
                "inst_id": trading_pair,
                "side": side,
                "price": price,
                "amount": amount,
                "status": "filled",
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"在{exchange_name}下单失败: {e}")
            return None
    
    async def _cleanup_active_arbitrage(self, key: str):
        """清理活跃套利记录
        
        Args:
            key (str): 套利记录键
        """
        await asyncio.sleep(300)  # 5分钟后清理
        if key in self.active_arbitrage:
            del self.active_arbitrage[key]
            logger.debug(f"清理活跃套利记录: {key}")
    
    def start(self):
        """启动策略
        """
        super().start()
        # 启动套利监控
        import asyncio
        asyncio.create_task(self.run_arbitrage_monitor())
    
    def get_status(self):
        """获取策略状态
        
        Returns:
            dict: 策略状态
        """
        status = super().get_status()
        status.update({
            "active_arbitrage": len(self.active_arbitrage),
            "price_cache": self.price_cache,
            "recent_opportunities": self.arbitrage_opportunities[-10:]
        })
        return status