# -*- coding: utf-8 -*-
"""
测试OKX API客户端功能
"""

import os
import sys
import logging
import json

# 添加项目根路径到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from okx_trading_bot.okx_api_client import OKXAPIClient

# 读取配置文件
def load_config():
    """加载配置文件"""
    # 获取当前脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(
        script_dir,
        'config', 'okx_config.json'
    )
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"加载配置文件失败: {e}")
        return {}

# 加载配置
config = load_config()
api_config = config.get('api', {})

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_okx_api_client():
    """测试OKX API客户端"""
    try:
        logger.info("开始测试OKX API客户端")
        
        # 创建API客户端实例
        api_url = api_config.get('api_url')
        api_client = OKXAPIClient(
            api_key=api_config.get('api_key'),
            api_secret=api_config.get('api_secret'),
            passphrase=api_config.get('passphrase'),
            is_test=api_config.get('is_test', True),
            api_url=api_url
        )
        logger.info(f"OKX API客户端创建成功，API URL: {api_url}")
        
        # 测试获取市场数据
        logger.info("测试获取BTC-USDT-SWAP的ticker数据")
        ticker = api_client.get_ticker("BTC-USDT-SWAP")
        if ticker:
            logger.info(f"获取ticker成功: {ticker}")
        else:
            logger.error("获取ticker失败")
        
        # 测试获取账户信息
        logger.info("测试获取账户余额")
        balance = api_client.get_account_balance()
        if balance:
            logger.info(f"获取账户余额成功: {balance}")
        else:
            logger.error("获取账户余额失败")
        
        logger.info("OKX API客户端测试完成")
        return True
        
    except Exception as e:
        logger.error(f"OKX API客户端测试失败: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    test_okx_api_client()
