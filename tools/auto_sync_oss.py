#!/usr/bin/env python3
"""
自动同步OSS后台服务
定期将交易数据同步到阿里云OSS
"""

import os
import sys
import time
import logging
from datetime import datetime
from threading import Thread, Event

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.utils.persistence import persistence_manager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AutoSyncOSSService:
    """
    自动同步OSS服务
    
    后台运行，定期将本地数据同步到OSS
    """
    
    def __init__(self, sync_interval: int = 60):
        """
        初始化自动同步服务
        
        Args:
            sync_interval: 同步间隔（秒），默认60秒
        """
        self.sync_interval = sync_interval
        self.stop_event = Event()
        self.sync_thread = None
        
        # 检查OSS是否可用
        if not persistence_manager.oss_manager:
            logger.warning("OSS管理器未初始化，自动同步服务无法启动")
            self.enabled = False
        else:
            self.enabled = True
            logger.info(f"自动同步OSS服务初始化完成，同步间隔: {sync_interval}秒")
    
    def start(self):
        """启动自动同步服务"""
        if not self.enabled:
            logger.warning("自动同步服务未启用")
            return False
        
        if self.sync_thread and self.sync_thread.is_alive():
            logger.warning("自动同步服务已经在运行")
            return False
        
        self.stop_event.clear()
        self.sync_thread = Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
        logger.info("✅ 自动同步OSS服务已启动")
        return True
    
    def stop(self):
        """停止自动同步服务"""
        if not self.sync_thread or not self.sync_thread.is_alive():
            logger.warning("自动同步服务未在运行")
            return False
        
        self.stop_event.set()
        self.sync_thread.join(timeout=5)
        logger.info("✅ 自动同步OSS服务已停止")
        return True
    
    def _sync_loop(self):
        """同步循环"""
        logger.info(f"开始同步循环，每{self.sync_interval}秒同步一次")
        
        while not self.stop_event.is_set():
            try:
                # 执行同步
                self._do_sync()
                
                # 等待下一次同步
                self.stop_event.wait(self.sync_interval)
                
            except Exception as e:
                logger.error(f"同步循环出错: {e}")
                time.sleep(5)
    
    def _do_sync(self):
        """执行同步操作"""
        try:
            files_to_sync = [
                "order_agent_state.json",
                "coordinator_agent_state.json",
                "strategy_state.json",
                "trade_history.json"
            ]
            
            synced_count = 0
            for filename in files_to_sync:
                try:
                    # 从本地加载（使用load_data方法）
                    data = persistence_manager.load_data(filename)
                    if data:
                        # 上传到OSS
                        if persistence_manager.oss_manager.save_to_oss(filename, data):
                            synced_count += 1
                except Exception as e:
                    logger.warning(f"同步 {filename} 失败: {e}")
            
            if synced_count > 0:
                logger.info(f"🔄 自动同步完成: {synced_count}/{len(files_to_sync)} 个文件")
            
        except Exception as e:
            logger.error(f"自动同步失败: {e}")


# 创建全局自动同步服务实例
auto_sync_service = AutoSyncOSSService(sync_interval=60)


def start_auto_sync():
    """启动自动同步服务（便捷函数）"""
    return auto_sync_service.start()


def stop_auto_sync():
    """停止自动同步服务（便捷函数）"""
    return auto_sync_service.stop()


if __name__ == "__main__":
    # 如果直接运行此脚本，启动自动同步服务
    import argparse
    
    parser = argparse.ArgumentParser(description='自动同步OSS服务')
    parser.add_argument('--interval', type=int, default=60, help='同步间隔（秒）')
    parser.add_argument('--daemon', action='store_true', help='作为守护进程运行')
    
    args = parser.parse_args()
    
    # 创建服务实例
    service = AutoSyncOSSService(sync_interval=args.interval)
    
    if args.daemon:
        # 作为守护进程运行
        service.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            service.stop()
    else:
        # 执行一次同步
        service._do_sync()
