"""
数据持久化工具
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# 尝试导入OSS持久化模块
try:
    from .oss_persistence import OSSPersistenceManager
    OSS_AVAILABLE = True
except ImportError:
    OSS_AVAILABLE = False
    logger.warning("OSS持久化模块未找到，将仅使用本地存储")

class PersistenceManager:
    """
    数据持久化管理器
    
    负责保存和加载机器人的状态数据
    支持本地存储和OSS云存储双重备份
    """
    
    def __init__(self, storage_dir: str = "./data", enable_oss: bool = True):
        """
        初始化持久化管理器
        
        Args:
            storage_dir: 存储目录
            enable_oss: 是否启用OSS备份
        """
        self.storage_dir = storage_dir
        # 确保存储目录存在
        os.makedirs(self.storage_dir, exist_ok=True)
        logger.info(f"持久化管理器初始化完成，存储目录: {self.storage_dir}")
        
        # 初始化OSS管理器
        self.oss_manager = None
        if enable_oss and OSS_AVAILABLE:
            try:
                self.oss_manager = OSSPersistenceManager(
                    local_backup_dir=storage_dir
                )
                logger.info("OSS备份已启用")
            except Exception as e:
                logger.error(f"OSS初始化失败: {e}")
        
    def save_data(self, filename: str, data: Dict[str, Any]) -> bool:
        """
        保存数据到文件（本地 + OSS双重备份）
        
        Args:
            filename: 文件名
            data: 要保存的数据
            
        Returns:
            bool: 保存是否成功
        """
        try:
            # 先保存到本地
            file_path = os.path.join(self.storage_dir, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"成功保存数据到本地文件: {filename}")
            
            # 如果OSS可用，同步到OSS
            if self.oss_manager:
                try:
                    self.oss_manager.save_to_oss(filename, data)
                except Exception as e:
                    logger.error(f"同步到OSS失败: {e}")
            
            return True
        except Exception as e:
            logger.error(f"保存数据失败: {e}")
            return False
    
    def load_data(self, filename: str, prefer_oss: bool = False) -> Optional[Dict[str, Any]]:
        """
        从文件加载数据（支持从OSS恢复）
        
        Args:
            filename: 文件名
            prefer_oss: 是否优先从OSS加载
            
        Returns:
            Optional[Dict[str, Any]]: 加载的数据，如果文件不存在或加载失败则返回None
        """
        try:
            file_path = os.path.join(self.storage_dir, filename)
            
            # 如果优先从OSS加载且OSS可用
            if prefer_oss and self.oss_manager:
                try:
                    data = self.oss_manager.load_from_oss(filename)
                    if data:
                        # 同时更新本地文件
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        return data
                except Exception as e:
                    logger.warning(f"从OSS加载失败: {e}，尝试从本地加载")
            
            # 从本地加载
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    logger.info(f"成功从本地文件加载数据: {filename}")
                    return data
                except Exception as e:
                    logger.warning(f"从本地文件加载失败: {e}，尝试从OSS加载")
            else:
                logger.info(f"本地文件不存在: {filename}")
            
            # 尝试从OSS加载
            if self.oss_manager:
                try:
                    data = self.oss_manager.load_from_oss(filename)
                    if data:
                        # 恢复到本地
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        logger.info(f"成功从OSS恢复数据到本地: {filename}")
                        return data
                except Exception as e:
                    logger.warning(f"从OSS加载失败: {e}")
            
            return None
            
        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            return None
    
    def save_order_agent_state(self, data: Dict[str, Any]) -> bool:
        """
        保存订单智能体状态
        
        Args:
            data: 订单智能体状态数据
            
        Returns:
            bool: 保存是否成功
        """
        return self.save_data("order_agent_state.json", data)
    
    def load_order_agent_state(self) -> Optional[Dict[str, Any]]:
        """
        加载订单智能体状态
        
        Returns:
            Optional[Dict[str, Any]]: 订单智能体状态数据
        """
        return self.load_data("order_agent_state.json")
    
    def save_coordinator_agent_state(self, data: Dict[str, Any]) -> bool:
        """
        保存协调智能体状态
        
        Args:
            data: 协调智能体状态数据
            
        Returns:
            bool: 保存是否成功
        """
        return self.save_data("coordinator_agent_state.json", data)
    
    def load_coordinator_agent_state(self) -> Optional[Dict[str, Any]]:
        """
        加载协调智能体状态
        
        Returns:
            Optional[Dict[str, Any]]: 协调智能体状态数据
        """
        return self.load_data("coordinator_agent_state.json")
    
    def sync_to_oss(self) -> bool:
        """
        同步所有本地数据到OSS
        
        Returns:
            bool: 同步是否成功
        """
        if not self.oss_manager:
            logger.warning("OSS管理器未初始化，无法同步")
            return False
        
        try:
            return self.oss_manager.sync_all_to_oss()
        except Exception as e:
            logger.error(f"同步到OSS失败: {e}")
            return False
    
    def restore_from_oss(self) -> bool:
        """
        从OSS恢复所有数据到本地
        
        Returns:
            bool: 恢复是否成功
        """
        if not self.oss_manager:
            logger.warning("OSS管理器未初始化，无法恢复")
            return False
        
        try:
            files = [
                "order_agent_state.json",
                "coordinator_agent_state.json",
                "strategy_state.json",
                "trade_history.json"
            ]
            
            success_count = 0
            for filename in files:
                try:
                    data = self.oss_manager.load_from_oss(filename)
                    if data:
                        # 保存到本地
                        file_path = os.path.join(self.storage_dir, filename)
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        logger.info(f"成功从OSS恢复: {filename}")
                        success_count += 1
                except Exception as e:
                    logger.warning(f"恢复 {filename} 失败: {e}")
            
            logger.info(f"从OSS恢复完成: {success_count}/{len(files)} 个文件")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"从OSS恢复失败: {e}")
            return False


# 创建全局持久化管理器实例（启用OSS备份）
persistence_manager = PersistenceManager(enable_oss=True)
