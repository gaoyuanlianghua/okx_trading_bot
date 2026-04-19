#!/usr/bin/env python3
"""
检查交易收益情况
"""

import asyncio
import yaml
from core.api.okx_rest_client import OKXRESTClient

async def check_profit():
    """检查交易收益情况"""
    try:
        # 加载配置
        with open('config/config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        api_config = config['api']
        
        # 初始化客户端
        client = OKXRESTClient(
            api_key=api_config['api_key'],
            api_secret=api_config['api_secret'],
            passphrase=api_config['passphrase'],
            is_test=api_config['is_test']
        )
        
        print('API 客户端初始化完成')
        print('检查账户信息和交易收益...')
        
        # 获取账户余额
        print('\n1. 账户余额:')
        balance = await client.get_account_balance()
        if balance:
            print(f'总权益: {balance.get("totalEq", "0")} USDT')
            details = balance.get("details", [])
            for detail in details:
                ccy = detail.get("ccy")
                avail_bal = detail.get("availBal")
                eq = detail.get("eq")
                print(f'  {ccy}: 可用余额 = {avail_bal}, 权益 = {eq}')
        else:
            print('获取账户余额失败')
        
        # 获取交易历史
        print('\n2. 最近交易历史:')
        try:
            order_history = await client.get_order_history(inst_type="SPOT", inst_id="BTC-USDT", limit=10)
            if order_history:
                print(f'最近 {len(order_history)} 条交易记录:')
                for order in order_history:
                    ord_id = order.get("ordId")
                    side = order.get("side")
                    sz = order.get("sz")
                    px = order.get("px")
                    state = order.get("state")
                    fee = order.get("fee")
                    fee_ccy = order.get("feeCcy")
                    c_time = order.get("cTime")
                    print(f'  订单ID: {ord_id}')
                    print(f'  方向: {side}, 数量: {sz} BTC, 价格: {px} USDT')
                    print(f'  状态: {state}, 手续费: {fee} {fee_ccy}')
                    print(f'  时间: {c_time}')
                    print('  ---')
            else:
                print('获取交易历史失败')
        except Exception as e:
            print(f'获取交易历史失败: {e}')
        
        # 获取持仓信息
        print('\n3. 持仓信息:')
        try:
            positions = await client.get_positions(inst_type="SPOT", inst_id="BTC-USDT")
            if positions:
                for position in positions:
                    inst_id = position.get("instId")
                    pos_side = position.get("posSide")
                    pos = position.get("pos")
                    avg_px = position.get("avgPx")
                    print(f'  {inst_id}: 持仓方向 = {pos_side}, 持仓数量 = {pos} BTC, 平均成本 = {avg_px} USDT')
            else:
                print('当前无持仓')
        except Exception as e:
            print(f'获取持仓信息失败: {e}')
        
    except Exception as e:
        print(f'检查收益失败: {e}')
    finally:
        if 'client' in locals():
            await client.close()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(check_profit())
