#!/usr/bin/env python3
"""
测试模块导入
"""

import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 测试导入
logger.info("开始导入模块...")
try:
    from core.config.env_manager import env_manager
    logger.info("成功导入env_manager")
except Exception as e:
    logger.error(f"导入env_manager失败: {e}")

try:
    from core.api.okx_rest_client import OKXRESTClient
    logger.info("成功导入OKXRESTClient")
except Exception as e:
    logger.error(f"导入OKXRESTClient失败: {e}")

try:
    from strategies.nuclear_dynamics_strategy import NuclearDynamicsStrategy
    logger.info("成功导入NuclearDynamicsStrategy")
except Exception as e:
    logger.error(f"导入NuclearDynamicsStrategy失败: {e}")

logger.info("模块导入完成")

# 测试获取环境信息
try:
    env_info = env_manager.get_env_info()
    logger.info(f"环境信息: {env_info}")
except Exception as e:
    logger.error(f"获取环境信息失败: {e}")

# 测试获取API配置
try:
    api_config = env_manager.get_api_config()
    logger.info(f"API配置: {api_config}")
except Exception as e:
    logger.error(f"获取API配置失败: {e}")
