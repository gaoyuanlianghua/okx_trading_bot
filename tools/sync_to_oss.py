#!/usr/bin/env python3
"""
OSS数据同步脚本
用于手动或定时将交易机器人数据同步到阿里云OSS
"""

import os
import sys
import logging
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.utils.persistence import persistence_manager
from core.utils.oss_persistence import oss_persistence_manager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def sync_all_data():
    """同步所有数据到OSS"""
    logger.info("=" * 60)
    logger.info("开始同步数据到OSS...")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    try:
        # 使用persistence_manager同步
        success = persistence_manager.sync_to_oss()
        
        if success:
            logger.info("✅ 数据同步到OSS成功")
        else:
            logger.warning("⚠️ 数据同步到OSS部分失败")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ 同步失败: {e}")
        return False


def restore_all_data():
    """从OSS恢复所有数据"""
    logger.info("=" * 60)
    logger.info("开始从OSS恢复数据...")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    try:
        # 使用persistence_manager恢复
        success = persistence_manager.restore_from_oss()
        
        if success:
            logger.info("✅ 从OSS恢复数据成功")
        else:
            logger.warning("⚠️ 从OSS恢复数据部分失败")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ 恢复失败: {e}")
        return False


def check_oss_connection():
    """检查OSS连接状态"""
    logger.info("检查OSS连接状态...")
    
    try:
        if oss_persistence_manager.oss_client:
            # 尝试列出文件
            files = oss_persistence_manager.list_oss_files()
            logger.info(f"✅ OSS连接正常，找到 {len(files)} 个文件")
            return True
        else:
            logger.error("❌ OSS客户端未初始化")
            return False
            
    except Exception as e:
        logger.error(f"❌ OSS连接失败: {e}")
        return False


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='OSS数据同步工具')
    parser.add_argument('action', choices=['sync', 'restore', 'check'], 
                        help='操作类型: sync(同步到OSS), restore(从OSS恢复), check(检查连接)')
    
    args = parser.parse_args()
    
    if args.action == 'sync':
        sync_all_data()
    elif args.action == 'restore':
        restore_all_data()
    elif args.action == 'check':
        check_oss_connection()


if __name__ == "__main__":
    main()
