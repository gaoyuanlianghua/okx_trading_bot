"""
阿里云OSS持久化模块
用于将交易机器人的策略数据备份到OSS，防止重启后数据丢失
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class OSSPersistenceManager:
    """
    OSS持久化管理器
    
    负责将机器人状态数据备份到阿里云OSS
    支持从OSS恢复数据
    """
    
    def __init__(self, 
                 access_key_id: str = None,
                 access_key_secret: str = None,
                 endpoint: str = None,
                 bucket_name: str = None,
                 local_backup_dir: str = "./data"):
        """
        初始化OSS持久化管理器
        
        Args:
            access_key_id: 阿里云AccessKey ID
            access_key_secret: 阿里云AccessKey Secret
            endpoint: OSS内网域名
            bucket_name: OSS存储桶名称
            local_backup_dir: 本地备份目录
        """
        # 从参数或环境变量读取配置
        self.bucket_name = bucket_name or os.getenv('OSS_BUCKET_NAME') or 'oself-jh'
        self.access_key_id = access_key_id or os.getenv('OSS_ACCESS_KEY_ID')
        self.access_key_secret = access_key_secret or os.getenv('OSS_ACCESS_KEY_SECRET')
        
        # 自动选择内网或外网域名
        # 内网域名（如果在阿里云ECS上）: oss-cn-hongkong-internal.aliyuncs.com
        # 外网域名（通用）: oss-cn-hongkong.aliyuncs.com
        if endpoint:
            self.endpoint = endpoint
        elif os.getenv('OSS_ENDPOINT'):
            self.endpoint = os.getenv('OSS_ENDPOINT')
        else:
            # 默认使用香港外网域名
            self.endpoint = "oss-cn-hongkong.aliyuncs.com"
        
        self.local_backup_dir = local_backup_dir
        
        # 确保本地备份目录存在
        os.makedirs(self.local_backup_dir, exist_ok=True)
        
        # 初始化OSS客户端
        self.oss_client = None
        self._init_oss_client()
        
        logger.info(f"OSS持久化管理器初始化完成")
        logger.info(f"  存储桶: {self.bucket_name}")
        logger.info(f"  内网域名: {self.endpoint}")
        logger.info(f"  本地备份: {self.local_backup_dir}")
    
    def _init_oss_client(self):
        """初始化OSS客户端"""
        try:
            # 尝试使用阿里云OSS SDK
            try:
                import oss2
                auth = oss2.Auth(self.access_key_id, self.access_key_secret)
                # 使用正确的endpoint格式，不要包含bucket名
                # 阿里云OSS SDK会自动处理bucket.endpoint的格式
                endpoint = self.endpoint.replace(f"{self.bucket_name}.", "")
                self.oss_client = oss2.Bucket(auth, endpoint, self.bucket_name)
                logger.info(f"阿里云OSS SDK初始化成功，使用endpoint: {endpoint}")
                return
            except ImportError:
                logger.warning("阿里云OSS SDK未安装，尝试使用boto3")
            
            # 使用boto3兼容S3协议
            import boto3
            from botocore.client import Config
            
            self.oss_client = boto3.client(
                's3',
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.access_key_secret,
                endpoint_url=f"http://{self.endpoint}",
                config=Config(s3={'addressing_style': 'virtual'})
            )
            logger.info("boto3 S3客户端初始化成功")
            
        except Exception as e:
            logger.error(f"OSS客户端初始化失败: {e}")
            self.oss_client = None
    
    def _get_oss_key(self, filename: str) -> str:
        """
        生成OSS存储路径
        
        Args:
            filename: 文件名
            
        Returns:
            str: OSS存储路径
        """
        # 按日期组织文件
        today = datetime.now().strftime("%Y-%m-%d")
        return f"trading_bot/{today}/{filename}"
    
    def save_to_oss(self, filename: str, data: Dict[str, Any]) -> bool:
        """
        保存数据到OSS
        
        Args:
            filename: 文件名
            data: 要保存的数据
            
        Returns:
            bool: 保存是否成功
        """
        if not self.oss_client:
            logger.warning("OSS客户端未初始化，仅保存到本地")
            return self._save_local(filename, data)
        
        try:
            # 先保存到本地
            if not self._save_local(filename, data):
                return False
            
            # 上传到OSS
            oss_key = self._get_oss_key(filename)
            json_data = json.dumps(data, ensure_ascii=False, indent=2)
            
            # 根据客户端类型选择上传方式
            if hasattr(self.oss_client, 'put_object'):
                # 阿里云OSS SDK
                self.oss_client.put_object(oss_key, json_data.encode('utf-8'))
            else:
                # boto3 S3
                self.oss_client.put_object(
                    Bucket=self.bucket_name,
                    Key=oss_key,
                    Body=json_data.encode('utf-8')
                )
            
            logger.info(f"成功上传数据到OSS: {oss_key}")
            return True
            
        except Exception as e:
            logger.error(f"上传数据到OSS失败: {e}")
            # 失败时至少保证本地有备份
            return self._save_local(filename, data)
    
    def load_from_oss(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        从OSS加载数据
        
        Args:
            filename: 文件名
            
        Returns:
            Optional[Dict[str, Any]]: 加载的数据
        """
        if not self.oss_client:
            logger.warning("OSS客户端未初始化，从本地加载")
            return self._load_local(filename)
        
        try:
            oss_key = self._get_oss_key(filename)
            
            # 根据客户端类型选择下载方式
            if hasattr(self.oss_client, 'get_object'):
                # 阿里云OSS SDK
                result = self.oss_client.get_object(oss_key)
                json_data = result.read().decode('utf-8')
            else:
                # boto3 S3
                result = self.oss_client.get_object(
                    Bucket=self.bucket_name,
                    Key=oss_key
                )
                json_data = result['Body'].read().decode('utf-8')
            
            data = json.loads(json_data)
            logger.info(f"成功从OSS加载数据: {oss_key}")
            return data
            
        except Exception as e:
            logger.warning(f"从OSS加载数据失败: {e}，尝试从本地加载")
            return self._load_local(filename)
    
    def _save_local(self, filename: str, data: Dict[str, Any]) -> bool:
        """
        保存数据到本地文件
        
        Args:
            filename: 文件名
            data: 要保存的数据
            
        Returns:
            bool: 保存是否成功
        """
        try:
            file_path = os.path.join(self.local_backup_dir, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"成功保存数据到本地: {filename}")
            return True
        except Exception as e:
            logger.error(f"保存数据到本地失败: {e}")
            return False
    
    def _load_local(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        从本地文件加载数据
        
        Args:
            filename: 文件名
            
        Returns:
            Optional[Dict[str, Any]]: 加载的数据
        """
        try:
            file_path = os.path.join(self.local_backup_dir, filename)
            if not os.path.exists(file_path):
                logger.info(f"本地文件不存在: {filename}")
                return None
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"成功从本地加载数据: {filename}")
            return data
        except Exception as e:
            logger.error(f"从本地加载数据失败: {e}")
            return None
    
    def list_oss_files(self, prefix: str = "trading_bot/") -> list:
        """
        列出OSS中的文件
        
        Args:
            prefix: 文件前缀
            
        Returns:
            list: 文件列表
        """
        if not self.oss_client:
            logger.warning("OSS客户端未初始化")
            return []
        
        try:
            files = []
            
            if hasattr(self.oss_client, 'list_objects'):
                # 阿里云OSS SDK
                result = self.oss_client.list_objects(prefix=prefix)
                for obj in result.object_list:
                    files.append(obj.key)
            else:
                # boto3 S3
                result = self.oss_client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix=prefix
                )
                for obj in result.get('Contents', []):
                    files.append(obj['Key'])
            
            return files
            
        except Exception as e:
            logger.error(f"列出OSS文件失败: {e}")
            return []
    
    def sync_all_to_oss(self) -> bool:
        """
        同步所有本地数据到OSS
        
        Returns:
            bool: 同步是否成功
        """
        try:
            files = [
                "order_agent_state.json",
                "coordinator_agent_state.json",
                "strategy_state.json",
                "trade_history.json"
            ]
            
            success_count = 0
            for filename in files:
                data = self._load_local(filename)
                if data:
                    if self.save_to_oss(filename, data):
                        success_count += 1
            
            logger.info(f"同步完成: {success_count}/{len(files)} 个文件成功")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"同步数据到OSS失败: {e}")
            return False


# 创建全局OSS持久化管理器实例
# 从环境变量读取配置
oss_persistence_manager = OSSPersistenceManager()
