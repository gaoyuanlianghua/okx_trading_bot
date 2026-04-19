#!/usr/bin/env python3
"""
交易测试脚本 - 使用交易器完成各种交易
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from core.config.env_manager import env_manager
from core import (
    EventBus,
    AgentConfig,
    OrderAgent,
    OKXRESTClient,
)


async def test_trading():
    """测试各种交易功能"""
    print("\n" + "=" * 60)
    print("交易测试脚本")
    print("=" * 60)
    
    # 获取环境配置
    env_info = env_manager.get_env_info()
    api_config = env_manager.get_api_config()
    
    print(f"\n当前环境: {env_info['current_env']}")
    print(f"模拟盘模式: {api_config['is_test']}")
    print(f"API Key: {api_config['api_key'][:8]}...")
    
    if not api_config['is_test']:
        print("\n⚠️  警告：当前不是模拟盘环境！")
        confirm = input("确认要在实盘进行测试吗？(yes/no): ")
        if confirm.lower() != 'yes':
            print("测试已取消")
            return
    
    # 创建事件总线
    event_bus = EventBus()
    
    # 创建REST客户端
    print("\n创建REST客户端...")
    rest_client = OKXRESTClient(
        api_key=api_config['api_key'],
        api_secret=api_config['api_secret'],
        passphrase=api_config['passphrase'],
        is_test=api_config['is_test']
    )
    print("✅ REST客户端创建成功")
    
    # 创建订单智能体
    print("\n创建订单智能体...")
    order_config = AgentConfig(
        name="Order_Test", 
        description="测试用订单智能体"
    )
    order_agent = OrderAgent(
        config=order_config,
        rest_client=rest_client
    )
    print("✅ 订单智能体创建成功")
    
    # 启动订单智能体
    print("\n启动订单智能体...")
    await order_agent.start()
    print("✅ 订单智能体启动成功")
    
    # 显示菜单
    while True:
        print("\n" + "=" * 60)
        print("交易测试菜单")
        print("=" * 60)
        print("1. 查看账户余额")
        print("2. 查看市场行情 (BTC-USDT)")
        print("3. 查看持仓")
        print("4. 查看订单历史")
        print("5. 买入测试 (现货)")
        print("6. 卖出测试 (现货)")
        print("7. 查看交易记录")
        print("0. 退出")
        print("=" * 60)
        
        choice = input("\n请选择操作 (0-7): ").strip()
        
        if choice == '0':
            print("\n退出测试...")
            break
        
        elif choice == '1':
            # 查看账户余额
            print("\n获取账户余额...")
            try:
                balance = await rest_client.get_account_balance()
                if balance:
                    print("✅ 账户余额获取成功")
                    print(f"总权益: {balance.get('totalEq', 'N/A')} USDT")
                    
                    details = balance.get('details', [])
                    if details:
                        print("\n币种余额:")
                        for item in details:
                            ccy = item.get('ccy', 'N/A')
                            avail_bal = item.get('availBal', '0')
                            eq = item.get('eq', '0')
                            print(f"  {ccy}: 可用={avail_bal}, 权益={eq}")
                else:
                    print("❌ 获取账户余额失败")
            except Exception as e:
                print(f"❌ 获取账户余额出错: {e}")
                import traceback
                traceback.print_exc()
        
        elif choice == '2':
            # 查看市场行情
            print("\n获取BTC-USDT行情...")
            try:
                ticker = await rest_client.get_ticker('BTC-USDT')
                if ticker:
                    print("✅ 行情获取成功")
                    print(f"交易对: {ticker.get('instId')}")
                    print(f"最新价: {ticker.get('last')} USDT")
                    print(f"24h最高: {ticker.get('high24h')} USDT")
                    print(f"24h最低: {ticker.get('low24h')} USDT")
                    print(f"24h成交量: {ticker.get('vol24h')}")
                else:
                    print("❌ 获取行情失败")
            except Exception as e:
                print(f"❌ 获取行情出错: {e}")
        
        elif choice == '3':
            # 查看持仓
            print("\n获取持仓...")
            try:
                positions = await rest_client.get_positions(inst_id='BTC-USDT')
                if positions:
                    print("✅ 持仓获取成功")
                    print(f"持仓数量: {len(positions)}")
                    for i, pos in enumerate(positions, 1):
                        print(f"\n持仓 {i}:")
                        print(f"  交易对: {pos.get('instId')}")
                        print(f"  持仓数量: {pos.get('pos')}")
                        print(f"  持仓方向: {pos.get('posSide')}")
                        print(f"  开仓均价: {pos.get('avgPx')}")
                        print(f"  未实现盈亏: {pos.get('upl')}")
                else:
                    print("当前无持仓")
            except Exception as e:
                print(f"❌ 获取持仓出错: {e}")
        
        elif choice == '4':
            # 查看订单历史
            print("\n获取订单历史...")
            try:
                orders = await rest_client.get_order_history(
                    inst_type='SPOT',
                    inst_id='BTC-USDT',
                    limit=20
                )
                if orders:
                    print(f"✅ 获取到 {len(orders)} 条订单记录")
                    print("\n最近订单:")
                    for i, order in enumerate(orders[:10], 1):
                        print(f"\n订单 {i}:")
                        print(f"  订单ID: {order.get('ordId')}")
                        print(f"  交易对: {order.get('instId')}")
                        print(f"  方向: {order.get('side')}")
                        print(f"  类型: {order.get('ordType')}")
                        print(f"  状态: {order.get('state')}")
                        print(f"  价格: {order.get('avgPx', order.get('px'))}")
                        print(f"  数量: {order.get('fillSz', order.get('sz'))}")
                else:
                    print("暂无订单记录")
            except Exception as e:
                print(f"❌ 获取订单历史出错: {e}")
        
        elif choice == '5':
            # 买入测试
            print("\n=== 买入测试 ===")
            
            # 获取当前价格
            try:
                ticker = await rest_client.get_ticker('BTC-USDT')
                if not ticker:
                    print("❌ 获取行情失败")
                    continue
                
                current_price = float(ticker.get('last', 0))
                print(f"当前BTC价格: {current_price} USDT")
            except Exception as e:
                print(f"❌ 获取价格失败: {e}")
                continue
            
            # 输入买入数量
            try:
                amount = input("\n请输入买入数量 (BTC, 默认0.0001): ").strip()
                if not amount:
                    amount = '0.0001'
                amount = float(amount)
                
                if amount <= 0:
                    print("❌ 数量必须大于0")
                    continue
            except ValueError:
                print("❌ 无效的数量")
                continue
            
            # 确认
            total_cost = amount * current_price
            print(f"\n预计花费: {total_cost:.2f} USDT")
            confirm = input("确认买入？(yes/no): ").strip().lower()
            
            if confirm != 'yes':
                print("操作已取消")
                continue
            
            # 执行买入
            print("\n执行买入...")
            try:
                order_params = {
                    'inst_id': 'BTC-USDT',
                    'side': 'buy',
                    'ord_type': 'market',
                    'sz': str(amount),
                    'td_mode': 'cash'
                }
                
                result = await order_agent.place_order(order_params)
                
                if result.get('success'):
                    print("✅ 买入成功！")
                    print(f"订单ID: {result.get('order_id')}")
                else:
                    print(f"❌ 买入失败: {result.get('error')}")
                    
            except Exception as e:
                print(f"❌ 买入出错: {e}")
                import traceback
                traceback.print_exc()
        
        elif choice == '6':
            # 卖出测试
            print("\n=== 卖出测试 ===")
            
            # 获取当前价格
            try:
                ticker = await rest_client.get_ticker('BTC-USDT')
                if not ticker:
                    print("❌ 获取行情失败")
                    continue
                
                current_price = float(ticker.get('last', 0))
                print(f"当前BTC价格: {current_price} USDT")
            except Exception as e:
                print(f"❌ 获取价格失败: {e}")
                continue
            
            # 输入卖出数量
            try:
                amount = input("\n请输入卖出数量 (BTC, 默认0.0001): ").strip()
                if not amount:
                    amount = '0.0001'
                amount = float(amount)
                
                if amount <= 0:
                    print("❌ 数量必须大于0")
                    continue
            except ValueError:
                print("❌ 无效的数量")
                continue
            
            # 确认
            total_revenue = amount * current_price
            print(f"\n预计收入: {total_revenue:.2f} USDT")
            confirm = input("确认卖出？(yes/no): ").strip().lower()
            
            if confirm != 'yes':
                print("操作已取消")
                continue
            
            # 执行卖出
            print("\n执行卖出...")
            try:
                order_params = {
                    'inst_id': 'BTC-USDT',
                    'side': 'sell',
                    'ord_type': 'market',
                    'sz': str(amount),
                    'td_mode': 'cash'
                }
                
                result = await order_agent.place_order(order_params)
                
                if result.get('success'):
                    print("✅ 卖出成功！")
                    print(f"订单ID: {result.get('order_id')}")
                else:
                    print(f"❌ 卖出失败: {result.get('error')}")
                    
            except Exception as e:
                print(f"❌ 卖出出错: {e}")
                import traceback
                traceback.print_exc()
        
        elif choice == '7':
            # 查看交易记录
            print("\n交易记录:")
            try:
                trade_history = order_agent._trade_history
                if trade_history:
                    print(f"共 {len(trade_history)} 条记录")
                    print("\n最近记录:")
                    for i, trade in enumerate(trade_history[-10:], 1):
                        print(f"\n记录 {i}:")
                        print(f"  交易ID: {trade.get('trade_id')}")
                        print(f"  交易对: {trade.get('inst_id')}")
                        print(f"  方向: {trade.get('side')}")
                        print(f"  价格: {trade.get('price')}")
                        print(f"  数量: {trade.get('filled_size')}")
                        print(f"  手续费: {trade.get('fee')}")
                        print(f"  时间: {trade.get('timestamp')}")
                else:
                    print("暂无交易记录")
            except Exception as e:
                print(f"❌ 获取交易记录出错: {e}")
        
        else:
            print("\n❌ 无效的选择，请重新输入")
        
        # 暂停一下
        input("\n按回车键继续...")
    
    # 停止订单智能体
    print("\n停止订单智能体...")
    await order_agent.stop()
    print("✅ 订单智能体已停止")
    
    # 关闭REST客户端
    if hasattr(rest_client, 'session') and rest_client.session:
        await rest_client.session.close()
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(test_trading())
    except KeyboardInterrupt:
        print("\n\n用户中断，退出...")
    except Exception as e:
        print(f"\n运行出错: {e}")
        import traceback
        traceback.print_exc()
