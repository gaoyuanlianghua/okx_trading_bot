#!/usr/bin/env python3
# 交易数据收集器，按照日期保存180天的数据

import os
import json
import time
import logging
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_collector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('DataCollector')

# 数据存储目录
DATA_DIR = 'trade_data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# 保存180天的数据
KEEP_DAYS = 180

class DataCollector:
    def __init__(self):
        self.data_cache = []
        self.last_save_time = time.time()
    
    def add_trade_data(self, trade_data):
        """添加交易数据"""
        # 添加时间戳
        trade_data['timestamp'] = datetime.now().isoformat()
        self.data_cache.append(trade_data)
        
        # 每10分钟保存一次数据
        if time.time() - self.last_save_time > 600:
            self.save_data()
            self.last_save_time = time.time()
    
    def save_data(self):
        """保存数据到文件"""
        if not self.data_cache:
            return
        
        # 获取当前日期
        today = datetime.now().strftime('%Y-%m-%d')
        file_path = os.path.join(DATA_DIR, f'{today}.json')
        
        # 读取现有数据
        existing_data = []
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    existing_data = json.load(f)
            except Exception as e:
                logger.error(f"读取数据文件失败: {e}")
        
        # 添加新数据
        existing_data.extend(self.data_cache)
        
        # 保存数据
        try:
            with open(file_path, 'w') as f:
                json.dump(existing_data, f, indent=2)
            logger.info(f"保存了 {len(self.data_cache)} 条交易数据到 {file_path}")
            self.data_cache = []
        except Exception as e:
            logger.error(f"保存数据失败: {e}")
    
    def cleanup_old_data(self):
        """清理超过180天的旧数据"""
        cutoff_date = datetime.now() - timedelta(days=KEEP_DAYS)
        cutoff_str = cutoff_date.strftime('%Y-%m-%d')
        
        for filename in os.listdir(DATA_DIR):
            if filename.endswith('.json'):
                file_date_str = filename[:-5]  # 移除 .json 后缀
                if file_date_str < cutoff_str:
                    file_path = os.path.join(DATA_DIR, filename)
                    try:
                        os.remove(file_path)
                        logger.info(f"删除了过期数据文件: {file_path}")
                    except Exception as e:
                        logger.error(f"删除过期数据文件失败: {e}")

# 测试数据收集器
if __name__ == "__main__":
    collector = DataCollector()
    
    # 模拟添加交易数据
    test_data = {
        'strategy': 'NuclearDynamicsStrategy',
        'side': 'neutral',
        'price': 69193.9,
        'signal_strength': 0.4,
        'signal_level': 'S',
        'inst_id': 'BTC-USDT',
        'indicators': {
            'spring_drift': {'P': '→', 'E': '→', 'M': '→', 'direction': 'neutral'},
            'angular_momentum_flow': {'flow': 3.498811771768574e-06, 'direction': 'to_B'},
            'pairing_gap': {'gap': 0.9955382201039431, 'trend': 'stable', 'asymmetric_param': 0.9999978260916825},
            'phase_sync': {'phase_diff': 1.4133794540664555, 'status': 'unlocked'},
            'atr': 0.32857142857184435
        }
    }
    
    collector.add_trade_data(test_data)
    collector.save_data()
    collector.cleanup_old_data()
    
    logger.info("数据收集器测试完成")