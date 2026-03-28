#!/usr/bin/env python3
"""
依赖检查和安装脚本
用于检查项目依赖是否已正确安装，并自动安装缺失的依赖
"""

import os
import sys
import subprocess

# 尝试导入区域化日志记录器
try:
    from commons.logger_config import get_logger
    logger = get_logger(region="Dependencies")
except ImportError:
    # 如果无法导入，使用默认的loguru logger
    from loguru import logger
    logger.remove()
    logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> <level>{level}</level> {message}")

def check_pip():
    """
    检查pip是否可用
    """
    try:
        subprocess.run([sys.executable, '-m', 'pip', '--version'], 
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except subprocess.CalledProcessError:
        logger.error("pip 不可用，请确保 pip 已正确安装")
        return False
    except FileNotFoundError:
        logger.error("Python 解释器未找到")
        return False

def read_requirements(file_path="requirements.txt"):
    """
    读取requirements.txt文件
    
    Args:
        file_path (str): requirements.txt文件路径
        
    Returns:
        list: 依赖列表
    """
    if not os.path.exists(file_path):
        logger.error(f"requirements.txt 文件不存在: {file_path}")
        return []
    
    requirements = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # 跳过空行和注释行
            if not line or line.startswith('#'):
                continue
            requirements.append(line)
    
    logger.info(f"读取到 {len(requirements)} 个依赖")
    return requirements

def check_dependency(package):
    """
    检查单个依赖是否已安装
    
    Args:
        package (str): 依赖包名
        
    Returns:
        bool: 是否已安装
    """
    # 处理带有额外选项的包，如 python-socks[asyncio]
    package_name = package.split('[')[0] if '[' in package else package
    
    try:
        # 使用pip list检查包是否已安装
        result = subprocess.run([sys.executable, '-m', 'pip', 'list'], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                              text=True, check=True)
        
        # 检查包是否在列表中
        for line in result.stdout.splitlines():
            if line.startswith(package_name):
                return True
        
        return False
    except subprocess.CalledProcessError:
        logger.error(f"检查依赖 {package} 时出错")
        return False

def install_dependency(package):
    """
    安装单个依赖
    
    Args:
        package (str): 依赖包名
        
    Returns:
        bool: 是否安装成功
    """
    try:
        logger.info(f"正在安装依赖: {package}")
        subprocess.run([sys.executable, '-m', 'pip', 'install', package], 
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                     check=True, text=True)
        logger.info(f"依赖 {package} 安装成功")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"安装依赖 {package} 失败: {e.stderr}")
        return False

def main():
    """
    主函数
    """
    # 配置日志
    logger.remove()
    logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> <level>{level}</level> {message}")
    
    logger.info("开始检查项目依赖...")
    
    # 检查pip是否可用
    if not check_pip():
        sys.exit(1)
    
    # 读取requirements.txt
    requirements = read_requirements()
    if not requirements:
        sys.exit(1)
    
    # 检查并安装缺失的依赖
    missing_deps = []
    for dep in requirements:
        if not check_dependency(dep):
            missing_deps.append(dep)
    
    if not missing_deps:
        logger.info("所有依赖都已正确安装")
        sys.exit(0)
    
    logger.info(f"发现 {len(missing_deps)} 个缺失的依赖: {missing_deps}")
    
    # 安装缺失的依赖
    success_count = 0
    for dep in missing_deps:
        if install_dependency(dep):
            success_count += 1
    
    if success_count == len(missing_deps):
        logger.info("所有缺失的依赖都已成功安装")
        sys.exit(0)
    else:
        logger.error(f"部分依赖安装失败，成功安装 {success_count} 个，失败 {len(missing_deps) - success_count} 个")
        sys.exit(1)

if __name__ == "__main__":
    main()
