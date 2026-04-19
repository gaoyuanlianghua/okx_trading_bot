#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# check_expected_return.py
# 查看订单智能体收益预测因子变化

import asyncio
import logging
import matplotlib.pyplot as plt
import numpy as np
from core.api.okx_rest_client import OKXRESTClient
from core.utils.config_manager import get_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

class ExpectedReturnAnalyzer:
    """收益预测因子分析器"""
    
    def __init__(self, rest_client):
        """初始化分析器
        
        Args:
            rest_client: OKX REST客户端
        """
        self.rest_client = rest_client
        self.expected_returns = []
        self.timestamps = []
        
    async def analyze_expected_return(self):
        """分析预期收益率变化"""
        try:
            # 1. 获取账户余额
            logger.info("获取账户余额...")
            balance = await self.rest_client.get_account_balance()
            if balance and isinstance(balance, dict):
                logger.info(f"账户总权益: {balance.get('totalEq', 'N/A')}")
            
            # 2. 获取市场数据
            logger.info("获取市场数据...")
            ticker = await self.rest_client.get_ticker("BTC-USDT")
            if ticker and len(ticker) > 0:
                current_price = float(ticker[0].get('last', 0))
                logger.info(f"当前BTC价格: {current_price} USDT")
            else:
                current_price = 69000.0  # 默认价格
            
            # 3. 模拟不同价格的预期收益率
            logger.info("计算不同价格的预期收益率...")
            price_range = np.linspace(current_price * 0.95, current_price * 1.05, 20)
            
            for price in price_range:
                # 计算预期收益率
                price_diff = abs(price - current_price)
                expected_return = price_diff / current_price
                
                self.expected_returns.append(expected_return)
                self.timestamps.append(price)
                
                logger.info(f"价格: {price:.2f} USDT, 预期收益率: {expected_return:.4f} ({expected_return*100:.2f}%)")
            
            # 4. 分析收益预测因子变化
            self.analyze_trends()
            
            # 5. 可视化结果
            self.visualize_results(current_price)
            
        except Exception as e:
            logger.error(f"分析预期收益率失败: {e}")
            import traceback
            traceback.print_exc()
    
    def analyze_trends(self):
        """分析收益预测因子变化趋势"""
        if len(self.expected_returns) < 2:
            logger.warning("数据不足，无法分析趋势")
            return
        
        # 计算收益率变化
        returns_diff = np.diff(self.expected_returns)
        
        # 分析趋势
        positive_changes = len([d for d in returns_diff if d > 0])
        negative_changes = len([d for d in returns_diff if d < 0])
        
        logger.info(f"收益预测因子变化趋势:")
        logger.info(f"正向变化: {positive_changes}次")
        logger.info(f"负向变化: {negative_changes}次")
        
        # 计算平均变化率
        if returns_diff.size > 0:
            avg_change = np.mean(returns_diff)
            logger.info(f"平均变化率: {avg_change:.6f}")
        
    def visualize_results(self, current_price):
        """可视化收益预测因子变化"""
        try:
            plt.figure(figsize=(12, 6))
            
            # 绘制预期收益率曲线
            plt.plot(self.timestamps, self.expected_returns, 'b-o', label='预期收益率')
            
            # 标记当前价格
            plt.axvline(x=current_price, color='r', linestyle='--', label=f'当前价格: {current_price:.2f}')
            
            # 标记阈值
            plt.axhline(y=0.005, color='g', linestyle='--', label='收益率阈值: 0.5%')
            
            plt.title('订单智能体收益预测因子变化')
            plt.xlabel('价格 (USDT)')
            plt.ylabel('预期收益率')
            plt.grid(True)
            plt.legend()
            
            # 保存图表
            plt.savefig('expected_return_analysis.png')
            logger.info("收益预测因子分析图表已保存为 expected_return_analysis.png")
            
        except Exception as e:
            logger.error(f"可视化失败: {e}")

async def main():
    """主函数"""
    try:
        # 加载配置
        api_config = get_config("api")
        
        # 初始化OKX REST客户端
        rest_client = OKXRESTClient(
            api_key=api_config["api_key"],
            api_secret=api_config["api_secret"],
            passphrase=api_config["passphrase"],
            is_test=api_config.get("is_test", False)
        )
        
        # 初始化分析器
        analyzer = ExpectedReturnAnalyzer(rest_client)
        
        # 分析预期收益率
        await analyzer.analyze_expected_return()
        
    except Exception as e:
        logger.error(f"主函数错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
