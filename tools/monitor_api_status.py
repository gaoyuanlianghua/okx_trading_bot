#!/usr/bin/env python3
"""
监控OKX API状态并实现API端点切换
"""

import asyncio
import logging
from core.api.okx_rest_client import OKXRESTClient

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 不同的OKX API端点
API_ENDPOINTS = [
    "https://www.okx.com",  # 主端点
    "https://www.okx.cn",  # 中国端点
    "https://okx.com",  # 备选端点
]

class APIMonitor:
    """API状态监控器"""
    
    def __init__(self, api_key, api_secret, passphrase, is_test=False):
        """
        初始化API监控器
        
        Args:
            api_key: API密钥
            api_secret: API密钥密码
            passphrase: 密码短语
            is_test: 是否为模拟盘
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.is_test = is_test
        self.current_endpoint = API_ENDPOINTS[0]
        self.endpoint_status = {}
    
    async def check_endpoint_status(self, endpoint):
        """
        检查单个API端点的状态
        
        Args:
            endpoint: API端点URL
            
        Returns:
            bool: 端点是否可用
        """
        try:
            # 创建临时客户端来测试端点
            client = OKXRESTClient(
                api_key=self.api_key,
                api_secret=self.api_secret,
                passphrase=self.passphrase,
                is_test=self.is_test
            )
            
            # 临时修改BASE_URL来测试不同端点
            original_base_url = client.BASE_URL
            client.BASE_URL = endpoint
            
            # 调用服务器时间接口来测试端点
            server_time = await client.get_server_time()
            await client.close()
            
            if server_time:
                logger.info(f"端点 {endpoint} 状态正常")
                return True
            else:
                logger.warning(f"端点 {endpoint} 状态异常")
                return False
        except Exception as e:
            logger.error(f"检查端点 {endpoint} 时出错: {e}")
            return False
    
    async def monitor_all_endpoints(self):
        """
        监控所有API端点的状态
        """
        logger.info("开始监控API端点状态...")
        
        tasks = []
        for endpoint in API_ENDPOINTS:
            task = self.check_endpoint_status(endpoint)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # 更新端点状态
        for i, endpoint in enumerate(API_ENDPOINTS):
            self.endpoint_status[endpoint] = results[i]
        
        logger.info(f"API端点状态: {self.endpoint_status}")
        return self.endpoint_status
    
    async def find_best_endpoint(self):
        """
        找到最佳的API端点
        
        Returns:
            str: 最佳端点URL
        """
        await self.monitor_all_endpoints()
        
        # 按优先级顺序找到第一个可用的端点
        for endpoint in API_ENDPOINTS:
            if self.endpoint_status.get(endpoint, False):
                logger.info(f"选择最佳端点: {endpoint}")
                self.current_endpoint = endpoint
                return endpoint
        
        logger.error("所有API端点都不可用")
        return self.current_endpoint
    
    async def update_okx_client_endpoint(self, client):
        """
        更新OKX客户端的API端点
        
        Args:
            client: OKXRESTClient实例
        """
        best_endpoint = await self.find_best_endpoint()
        if best_endpoint != client.BASE_URL:
            logger.info(f"切换API端点: {client.BASE_URL} -> {best_endpoint}")
            client.BASE_URL = best_endpoint
            return True
        return False

async def main():
    """主函数"""
    import yaml
    
    # 从配置文件加载API密钥
    with open('config/config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    api_key = config.get('api', {}).get('api_key', '')
    api_secret = config.get('api', {}).get('api_secret', '')
    passphrase = config.get('api', {}).get('passphrase', '')
    is_test = config.get('api', {}).get('is_test', False)
    
    if not api_key or not api_secret or not passphrase:
        logger.error("API密钥配置不完整")
        return
    
    # 创建API监控器
    monitor = APIMonitor(api_key, api_secret, passphrase, is_test)
    
    # 监控API状态
    await monitor.monitor_all_endpoints()
    
    # 找到最佳端点
    best_endpoint = await monitor.find_best_endpoint()
    logger.info(f"推荐使用的API端点: {best_endpoint}")

if __name__ == "__main__":
    # 使用Python 3.6兼容的方式运行异步函数
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
