#!/usr/bin/env python3
"""
手动卖出脚本
用于手动执行卖出操作
"""

import asyncio
import json
from core.agents.order_agent import OrderAgent
from core.agents.coordinator_agent import CoordinatorAgent
from core.config import AgentConfig
from core.traders.trader_manager import TraderManager
from core.api.okx_rest_client import OKXRESTClient

async def manual_sell():
    """手动执行卖出操作"""
    print("=== 手动卖出脚本 ===")
    
    # 配置
    config = AgentConfig(
        agent_id="manual_sell_agent",
        name="Manual Sell Agent",
        description="手动卖出BTC的智能体"
    )
    
    # 初始化REST客户端
    rest_client = OKXRESTClient(
        api_key="YOUR_API_KEY",
        api_secret="YOUR_API_SECRET",
        passphrase="YOUR_PASSPHRASE"
    )
    
    # 初始化交易器管理器
    trader_manager = TraderManager(rest_client)
    
    # 初始化订单智能体
    order_agent = OrderAgent(config, trader=trader_manager.get_trader("spot"), rest_client=rest_client)
    
    # 同步账户和订单状态
    print("正在同步账户和订单状态...")
    sync_result = await order_agent.sync_account_and_orders()
    if not sync_result.get("success"):
        print(f"同步失败: {sync_result.get('error')}")
        return
    
    # 获取当前BTC价格
    print("正在获取当前BTC价格...")
    ticker = await rest_client.get_ticker("BTC-USDT")
    current_price = float(ticker.get("last", 0))
    print(f"当前BTC价格: {current_price:.2f} USDT")
    
    # 计算卖出数量
    # 从订单智能体的状态文件中获取未卖出的买入订单
    try:
        with open("/root/okx_trading_bot/data/order_agent_state.json", "r") as f:
            state = json.load(f)
        
        # 查找未卖出的买入订单
        buy_trades = []
        for trade in state.get("trade_history", []):
            if trade.get("side") == "buy" and trade.get("state") == "filled":
                # 检查是否已经卖出
                sold = False
                for t in state.get("trade_history", []):
                    if t.get("side") == "sell" and t.get("state") == "filled" and t.get("buy_trade_id") == trade.get("trade_id"):
                        sold = True
                        break
                if not sold:
                    buy_trades.append(trade)
        
        if not buy_trades:
            print("没有未卖出的