#!/usr/bin/env python3
"""
持续运行核互反动力学策略
"""

import asyncio
import time
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from core.config.env_manager import env_manager
from core.api.okx_rest_client import OKXRESTClient
from strategies.nuclear_dynamics_strategy import NuclearDynamicsStrategy

def print_header():
    """打印头部信息"""
    print("\n" + "=" * 60)
    print("持续运行核互反动力学策略")
    print("=" * 60)

def print_status(message):
    """打印状态信息"""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")

async def main():
    """主函数"""
    print_header()
    
    # 检查环境
    env_info = env_manager.get_env_info()
    if not env_info['is_test']:
        print_status("⚠️  注意：当前不是模拟盘环境，将使用实盘交易！")
    else:
        print_status("✅ 正在使用模拟盘环境")
    
    # 获取API配置
    api_config = env_manager.get_api_config()
    print_status(f"API Key: {api_config['api_key'][:8]}...")
    print_status(f"模拟盘模式: {api_config['is_test']}")
    
    # 创建REST客户端
    rest_client = OKXRESTClient(
        api_key=api_config['api_key'],
        api_secret=api_config['api_secret'],
        passphrase=api_config['passphrase'],
        is_test=api_config['is_test']
    )
    
    # 测试API连接
    print_status("测试API连接...")
    server_time = await rest_client.get_server_time()
    if server_time:
        print_status(f"✅ 服务器时间获取成功: {server_time}")
    else:
        print_status("❌ API连接失败")
        return
    
    # 测试行情数据
    ticker = await rest_client.get_ticker('BTC-USDT')
    if ticker:
        print_status(f"✅ 行情数据获取成功")
        print_status(f"  BTC-USDT 最新价: {ticker.get('last')} USDT")
    else:
        print_status("❌ 行情数据获取失败")
        return
    
    # 创建策略实例
    print_status("初始化核互反动力学策略...")
    strategy_config = {
        'strategy': {
            'name': 'nuclear_dynamics_strategy',
            'symbol': 'BTC-USDT',
            'timeframe': '1m'
        }
    }
    
    strategy = NuclearDynamicsStrategy(
        api_client=rest_client,
        config=strategy_config
    )
    print_status("✅ 策略初始化成功")
    
    # 启动策略
    strategy.start()
    print_status("✅ 策略启动成功")
    
    print("\n" + "=" * 60)
    print("开始持续运行策略（每60秒执行一次）")
    print("按 Ctrl+C 停止策略")
    print("=" * 60)
    
    try:
        while True:
            # 获取最新行情数据
            print_status("获取最新行情数据...")
            ticker = await rest_client.get_ticker('BTC-USDT')
            
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
                
                # 执行策略
                print_status("执行策略...")
                signal = strategy.execute(strategy_data)
                
                if signal and signal.get('side') != 'neutral':
                    print("\n" + "-" * 40)
                    print_status(f"策略信号: {signal}")
                    print_status(f"📊 信号强度: {signal.get('signal_strength'):.2f}")
                    print_status(f"📈 信号级别: {signal.get('signal_level')}")
                    print_status(f"🎯 信号得分: {signal.get('signal_score')}")
                    print_status(f"💡 方向: {signal.get('side')}")
                    print_status(f"💰 价格: {signal.get('price')}")
                    print("-" * 40 + "\n")
                else:
                    print_status("策略信号: 中性 (无交易)")
            else:
                print_status("获取行情数据失败")
            
            # 等待60秒
            print_status("等待下一次执行...")
            await asyncio.sleep(60)
            
    except KeyboardInterrupt:
        print_status("用户中断，停止策略")
    except Exception as e:
        print_status(f"运行策略时出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 停止策略
        strategy.stop()
        # 清理REST客户端
        if hasattr(rest_client, 'session') and rest_client.session:
            await rest_client.session.close()
        print_status("策略已停止")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
