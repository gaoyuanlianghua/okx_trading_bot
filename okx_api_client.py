import time
import hmac
import hashlib
import base64
import json
import os
import socket
import ssl
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from threading import Lock

# 初始化日志配置
from commons.logger_config import global_logger_config

# 获取区域化日志记录器
def get_logger(region=None):
    return global_logger_config.get_logger(region=region)

# 创建默认日志记录器
logger = get_logger("API")
from urllib.parse import urlparse, urlencode

# 导入网络相关模块
from network.network_errors import NetworkError, ConnectionError, TimeoutError, DNSResolutionError, SSLHandshakeError, RateLimitError, ServerError, global_network_error_handler


# 导入DNS解析模块
from network.dns_resolver import (
    custom_dns_resolve, prewarm_dns_cache, batch_dns_resolve, 
    update_dns_config, switch_dns_region, get_dns_stats, reset_dns_stats,
    async_custom_dns_resolve, DNS_WHITELIST, CURRENT_DNS_CONFIG,
    validate_domain, DNS_CACHE
)

# 导入HTTP适配器模块
from network.http_adapters import DNSBypassingSession, custom_getaddrinfo, original_getaddrinfo

# 导入重试装饰器模块
from network.retry_utils import smart_retry, retry_with_backoff

class OKXAPIClient:
    """OKX API客户端封装，简化API调用和认证管理"""
    
    def __init__(self, api_key=None, api_secret=None, passphrase=None, is_test=False, api_url=None, api_ip=None, api_ips=None, timeout=30, proxy=None):
        """
        初始化OKX API客户端
        
        Args:
            api_key (str, optional): OKX API密钥
            api_secret (str, optional): OKX API密钥密码
            passphrase (str, optional): OKX API密钥短语
            is_test (bool, optional): 是否使用测试网
            api_url (str, optional): 自定义OKX API URL
            api_ip (str, optional): OKX API服务器IP地址（已废弃）
            api_ips (list, optional): OKX API服务器IP地址列表（已废弃）
            timeout (int, optional): API请求超时时间，单位秒，默认30秒
            proxy (dict, optional): 代理配置，格式: {"enabled": bool, "http": str, "https": str, "socks5": str}
        """
        # 加载环境变量
        load_dotenv()
        
        # 使用全局配置管理器获取配置
        api_config = {}
        try:
            from commons.config_manager import global_config_manager
            self.config_manager = global_config_manager
            api_config = self.config_manager.get("api", {})
            logger.info("从配置管理器加载API配置成功")
        except ImportError as e:
            logger.warning(f"无法导入配置管理器，将使用本地配置加载: {e}")
            # 回退到本地配置文件加载
            config_path = os.path.join(os.path.dirname(__file__), 'config', 'okx_config.json')
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                api_config = config.get('api', {})
                logger.info(f"从配置文件加载配置成功: {config_path}")
            except Exception as ex:
                logger.warning(f"回退配置文件加载也失败: {ex}")
        except Exception as e:
            logger.error(f"从配置管理器加载配置失败: {e}")
        
        # WebSocket配置
        self.ws_ip = api_config.get('ws_ip')
        self.ws_ips = api_config.get('ws_ips', [])
        self.ws_open_timeout = api_config.get('ws_open_timeout', 15.0)
        self.ws_ping_timeout = api_config.get('ws_ping_timeout', 10.0)
        self.ws_close_timeout = api_config.get('ws_close_timeout', 5.0)
        self.ws_max_queue = api_config.get('ws_max_queue', 1000)
        self.ws_ping_interval = api_config.get('ws_ping_interval', 30.0)
        
        # 设置API密钥
        self.api_key = api_key or os.getenv('OKX_API_KEY') or api_config.get('api_key')
        self.api_secret = api_secret or os.getenv('OKX_API_SECRET') or api_config.get('api_secret')
        self.passphrase = passphrase or os.getenv('OKX_PASSPHRASE') or api_config.get('passphrase')
        self.is_test = is_test
        self.timeout = timeout or int(os.getenv('OKX_API_TIMEOUT', '30')) or api_config.get('timeout', 30)
        
        # API URL - 优先使用传入的api_url，然后是环境变量，最后是默认值
        # 模拟盘和实盘使用相同的REST API URL，但需要添加x-simulated-trading: 1请求头
        self.api_url = api_url or os.getenv('OKX_API_URL') or api_config.get('api_url') or 'https://www.okx.com'
        # 清理API URL，移除可能存在的反引号或其他特殊字符
        self.api_url = self.api_url.strip().strip('`')
        
        # 解析URL，获取主机名和路径
        self.parsed_url = urlparse(self.api_url)
        self.host_name = self.parsed_url.netloc
        self.base_path = self.parsed_url.path
        
        # API版本，当前OKX API版本为v5
        self.api_version = "v5"
        
        # 创建自定义会话，支持可靠DNS解析和重试机制
        self.session = DNSBypassingSession(
            retry_count=3,
            backoff_factor=0.5
        )
        
        # 读取代理配置
        self.proxy_config = api_config.get('proxy', {})
        self.proxy_enabled = self.proxy_config.get('enabled', False)
        
        # 配置代理
        if self.proxy_enabled:
            proxies = {}
            if self.proxy_config.get('http'):
                proxies['http'] = self.proxy_config['http']
            if self.proxy_config.get('https'):
                proxies['https'] = self.proxy_config['https']
            if self.proxy_config.get('socks5'):
                proxies['http'] = self.proxy_config['socks5']
                proxies['https'] = self.proxy_config['socks5']
            
            self.session.proxies = proxies
            self.active_proxy_url = self.proxy_config.get('socks5') or self.proxy_config.get('https') or self.proxy_config.get('http')
            logger.info(f"已配置代理: {self.active_proxy_url}")
        else:
            self.session.proxies = {}
            self.active_proxy_url = None
            logger.info("未使用代理，只保留基本API调用功能")
        
        # 自定义SSL上下文，伪装TLS指纹
        import ssl
        ssl_context = ssl.create_default_context()
        # 强制使用TLS 1.2（避免TLS 1.3的特征被识别）
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        ssl_context.maximum_version = ssl.TLSVersion.TLSv1_2
        # 使用常见的加密套件（避免冷门套件被标记）
        ssl_context.set_ciphers("ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256")
        # 关闭会话复用（减少特征），兼容不同Python版本
        if hasattr(ssl, 'OP_NO_SESSION_RESUMPTION_ON_RECONNECT'):
            ssl_context.options |= ssl.OP_NO_SESSION_RESUMPTION_ON_RECONNECT
        # 禁用旧版本协议和不安全特性
        ssl_context.options |= ssl.OP_NO_SSLv2
        ssl_context.options |= ssl.OP_NO_SSLv3
        ssl_context.options |= ssl.OP_NO_TLSv1
        ssl_context.options |= ssl.OP_NO_TLSv1_1
        
        # 创建带有智能重试策略的HTTP适配器
        retry_strategy = Retry(
            total=8,  # 增加重试次数
            status_forcelist=[429, 500, 502, 503, 504, 521, 522, 523, 524],  # 增加更多错误码
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS"],
            backoff_factor=0.3,  # 进一步减少退避因子，提高重试效率
            respect_retry_after_header=True,
            raise_on_status=False  # 不抛出异常，让应用层处理
        )
        
        # 应用SSL上下文，修复旧版本requests库不支持ssl_context参数的问题
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=100,  # 大幅增加连接池大小
            pool_maxsize=100,     # 大幅增加连接池最大大小
            pool_block=False
        )
        adapter._ssl_context = ssl_context
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)
        
        # 设置会话超时
        self.session.timeout = self.timeout  # 使用配置文件中的超时时间
        self.session.trust_env = True  # 信任环境变量中的代理设置
        
        # 添加合规浏览器请求头，伪装流量特征
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Origin": self.api_url,
            "Referer": f"{self.api_url}/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        })
        
        # 清理请求头中的反引号，确保Origin和Referer字段格式正确
        if "Origin" in self.session.headers:
            self.session.headers["Origin"] = self.session.headers["Origin"].strip().strip('`')
        if "Referer" in self.session.headers:
            self.session.headers["Referer"] = self.session.headers["Referer"].strip().strip('`')
        
        logger.info(f"已配置API客户端超时时间: {self.timeout}秒")
        logger.info(f"已配置HTTP适配器重试策略: {retry_strategy}")
        
        # 添加线程锁，确保线程安全
        self._lock = Lock()
        
        # 初始化状态标志
        self.initialized = False
        self.initialization_error = None
        
        logger.info(f"OKX API客户端初始化完成，测试网: {is_test}，超时时间: {self.timeout}秒")
        logger.info(f"API URL: {self.api_url}")
        logger.info("使用可靠DNS解析，通过自定义DNS服务器确保连接稳定性")
        
        # 异步初始化网络相关配置
        self.async_init()
        
    def update_health_status(self):
        """
        更新健康检查状态
        """
        try:
            from commons.health_checker import global_health_checker
            
            # 检查网络状态
            network_status = 'PASS' if self.test_network_connection() else 'FAIL'
            global_health_checker.update_check_status(
                'network',
                network_status,
                '网络连接正常' if network_status == 'PASS' else '网络连接失败'
            )
            
            # 检查API状态
            api_status = 'PASS' if self.initialized else 'FAIL'
            global_health_checker.update_check_status(
                'api',
                api_status,
                'API客户端初始化成功' if api_status == 'PASS' else 'API客户端初始化失败',
                last_response_time=time.time()
            )
        except Exception as e:
            logger.error(f"更新健康状态失败: {e}")
    
    def async_init(self):
        """异步初始化网络相关配置，避免阻塞主线程"""
        def init_thread():
            try:
                # 检查是否启用网络适配
                enable_network_adaptation = False
                try:
                    from commons.config_manager import global_config_manager
                    config = global_config_manager.get_config()
                    enable_network_adaptation = config.get("network", {}).get("enable_adaptation", True)
                except Exception as e:
                    logger.error(f"加载网络配置失败: {e}")
                
                if enable_network_adaptation:
                    # 自动配置DNS解析IP
                    self.auto_configure_dns()
                    
                    # 测试网络连接
                    self.test_network_connection()
                else:
                    logger.info("网络适配已禁用，跳过初始化网络配置")
                
                self.initialized = True
                logger.info("OKX API客户端网络初始化完成")
                # 更新健康状态
                self.update_health_status()
            except Exception as e:
                self.initialization_error = str(e)
                logger.error(f"OKX API客户端网络初始化失败: {e}")
                # 更新健康状态
                self.update_health_status()
        
        import threading
        self.init_thread = threading.Thread(target=init_thread)
        self.init_thread.daemon = True
        self.init_thread.start()
    
    def get_current_ip(self):
        """获取当前活跃的API IP地址"""
        try:
            # 从配置管理器获取当前API IP
            api_config = self.config_manager.get("api", {})
            
            # 优先返回配置的api_ip，如果没有则返回api_ips列表中的第一个
            api_ip = api_config.get('api_ip')
            if api_ip:
                return api_ip
            
            api_ips = api_config.get('api_ips', [])
            if api_ips:
                return api_ips[0]
            
            return None
        except Exception as e:
            logger.error(f"获取当前IP失败: {e}")
            return None
    
    def get_network_status(self):
        """
        获取当前网络状态
        """
        return {
            "current_ip": self.get_current_ip(),
            "response_times": self.get_ip_response_times(),
            "dns_stats": self.get_dns_stats(),
            "connection_status": self.test_network_connection()
        }
    
    def verify_api_key(self):
        """
        验证API密钥有效性
        
        Returns:
            dict: 验证结果，包含status和message字段
        """
        auth_logger = get_logger("Auth")
        try:
            auth_logger.info(f"正在验证API密钥有效性，API URL: {self.api_url}")
            
            # 使用账户余额接口验证API密钥
            path = f"/api/{self.api_version}/account/balance"
            method = "GET"
            
            # 生成签名
            timestamp = str(time.time())
            message = f"{timestamp}{method}{path}"
            mac = hmac.new(bytes(self.api_secret, 'utf-8'), bytes(message, 'utf-8'), hashlib.sha256)
            signature = base64.b64encode(mac.digest()).decode()
            
            # 准备请求头
            headers = {
                "OK-ACCESS-KEY": self.api_key,
                "OK-ACCESS-SIGN": signature,
                "OK-ACCESS-TIMESTAMP": timestamp,
                "OK-ACCESS-PASSPHRASE": self.passphrase,
                "Content-Type": "application/json"
            }
            
            # 发送请求
            url = f"{self.api_url}{path}"
            response = self.session.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            # 解析响应
            result = response.json()
            if result.get("code") == "0":
                auth_logger.info("API密钥验证成功")
                return {
                    "status": "success",
                    "message": "API密钥验证成功",
                    "data": result.get("data")
                }
            else:
                error_msg = result.get("msg", "未知错误")
                auth_logger.error(f"API密钥验证失败: {error_msg}")
                return {
                    "status": "error",
                    "message": f"API密钥验证失败: {error_msg}",
                    "code": result.get("code")
                }
        except ConnectionResetError as e:
            auth_logger.error(f"API密钥验证时连接被重置: {e}")
            return {
                "status": "error",
                "message": f"连接被远程服务器重置: {e}",
                "hint": "这可能是DPI拦截或服务器限流导致的，请检查代理配置或降低请求频率"
            }
        except requests.exceptions.RequestException as e:
            auth_logger.error(f"API密钥验证失败: {e}")
            return {
                "status": "error",
                "message": f"请求失败: {e}"
            }
        except Exception as e:
            auth_logger.error(f"API密钥验证过程中发生未知错误: {e}")
            return {
                "status": "error",
                "message": f"未知错误: {e}"
            }
    
    def auto_configure_dns(self):
        """
        自动配置DNS解析IP，将解析结果保存到环境变量中
        """
        dns_logger = get_logger("DNS")
        dns_logger.info("自动配置DNS解析IP...")
        
        try:
            # 解析OKX API域名
            okx_ips = []
            for domain in DNS_WHITELIST:
                ip = custom_dns_resolve(domain)
                if ip:
                    okx_ips.append(ip)
                    dns_logger.info(f"解析 {domain} 到 {ip}")
            
            # 去重并转换为逗号分隔的字符串
            unique_ips = list(set(okx_ips))
            ips_str = ",".join(unique_ips)
            
            # 设置环境变量
            os.environ["OKX_API_IPS"] = ips_str
            dns_logger.info(f"已设置环境变量 OKX_API_IPS: {ips_str}")
            
            # 写入配置文件
            self.write_dns_config(unique_ips)
            
        except Exception as e:
            dns_logger.error(f"自动配置DNS解析IP失败: {e}")
    
    def write_dns_config(self, ips):
        """
        将DNS解析结果写入配置文件
        
        Args:
            ips (list): 解析到的IP地址列表
        """
        dns_logger = get_logger("DNS")
        try:
            config_dir = os.path.join(os.path.dirname(__file__), 'config')
            config_path = os.path.join(config_dir, 'okx_config.json')
            
            # 确保config目录存在
            os.makedirs(config_dir, exist_ok=True)
            
            # 读取现有配置，如果不存在则创建新配置
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
            except FileNotFoundError:
                config = {}
            
            # 更新配置
            if 'api' not in config:
                config['api'] = {}
            config['api']['api_ips'] = ips
            
            # 写入配置文件
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            dns_logger.info(f"已更新配置文件，添加API IP地址: {ips}")
        except Exception as e:
            dns_logger.error(f"写入DNS配置失败: {e}")
    
    def test_network_connection(self):
        """测试网络连接"""
        network_logger = get_logger("Network")
        network_logger.info("测试网络连接...")
        
        try:
            # 测试DNS解析
            network_logger.info(f"正在解析主机名: {self.host_name}")
            ip = custom_dns_resolve(self.host_name)
            
            # 如果DNS解析失败，使用配置文件中的API IP地址
            if not ip or ip.startswith('169.254.'):
                network_logger.warning(f"DNS解析失败或返回无效IP: {ip}")
                # 从配置文件中获取API IP地址
                api_ip = self.config_manager.get("api", {}).get("api_ip")
                if api_ip and not api_ip.startswith('169.254.'):
                    network_logger.info(f"使用配置文件中的API IP地址: {api_ip}")
                    ip = api_ip
                else:
                    # 从API IP列表中获取第一个有效IP
                    api_ips = self.config_manager.get("api", {}).get("api_ips", [])
                    for api_ip_candidate in api_ips:
                        if api_ip_candidate and not api_ip_candidate.startswith('169.254.'):
                            network_logger.info(f"使用配置文件中的API IP地址: {api_ip_candidate}")
                            ip = api_ip_candidate
                            break
                
                if not ip or ip.startswith('169.254.'):
                    network_logger.error(f"无法解析主机名: {self.host_name}，且配置文件中没有有效API IP地址")
                    network_logger.error("可能的原因:")
                    network_logger.error("1. 系统DNS配置问题")
                    network_logger.error("2. 网络环境对DNS查询的拦截")
                    network_logger.error("3. 域名不存在或已过期")
                    network_logger.error("4. 配置文件中没有有效API IP地址")
                    network_logger.error("建议: 检查网络连接或禁用自定义DNS解析")
                    return False
            
            network_logger.info(f"使用IP地址: {ip}")
            
            # 测试socket连接
            network_logger.info(f"正在测试Socket连接: {ip}:443")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((ip, 443))
            s.close()
            
            network_logger.info(f"Socket连接成功: {ip}:443")
            
            # 测试SSL握手
            network_logger.info(f"正在测试SSL握手: {ip}:443")
            context = ssl.create_default_context()
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
            
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((ip, 443))
            
            ssl_sock = context.wrap_socket(s, server_hostname=self.host_name)
            ssl_sock.close()
            s.close()
            
            network_logger.info(f"SSL握手成功: {ip}:443")
            network_logger.info("网络连接测试通过")
            return True
            
        except ssl.SSLError as e:
            network_logger.error(f"SSL握手失败: {e}")
            network_logger.error("可能的原因:")
            network_logger.error("1. 防火墙或代理服务器阻止了SSL连接")
            network_logger.error("2. SSL证书验证失败")
            network_logger.error("3. 网络环境问题")
            network_logger.error("4. 服务器配置问题")
            network_logger.error("建议: 检查网络连接或使用代理服务器")
            network_logger.error(f"详细错误信息: {type(e).__name__}: {e}")
            return False
        except socket.timeout:
            network_logger.error(f"连接超时: 无法连接到 {ip if 'ip' in locals() else self.host_name}:443")
            network_logger.error("可能的原因:")
            network_logger.error("1. 网络延迟过高")
            network_logger.error("2. 服务器负载过高")
            network_logger.error("3. 防火墙或代理服务器阻止了连接")
            network_logger.error("建议: 检查网络连接或调整超时时间")
            return False
        except socket.error as e:
            network_logger.error(f"网络连接失败: {e}")
            network_logger.error("可能的原因:")
            network_logger.error("1. 网络连接断开")
            network_logger.error("2. 服务器不可用")
            network_logger.error("3. 防火墙或代理服务器阻止了连接")
            network_logger.error("建议: 检查网络连接或API服务器状态")
            network_logger.error(f"详细错误信息: {type(e).__name__}: {e}")
            return False
        except Exception as e:
            network_logger.error(f"网络连接测试失败: {e}")
            network_logger.error("可能的原因:")
            network_logger.error("1. 未知的网络错误")
            network_logger.error("2. 代码逻辑错误")
            network_logger.error("3. 依赖库问题")
            network_logger.error("建议: 检查日志详细信息或联系开发者")
            network_logger.error(f"详细错误信息: {type(e).__name__}: {e}")
            import traceback
            network_logger.error(f"异常堆栈: {traceback.format_exc()}")
            return False
    
    def run_network_adapter(self, auto_update=True):
        """运行网络自动适配脚本
        
        Args:
            auto_update (bool): 是否自动更新配置文件
            
        Returns:
            bool: 执行是否成功
        """
        import subprocess
        import os
        
        network_logger = get_logger("Network")
        network_logger.info("运行网络自动适配脚本...")
        
        # 构建PowerShell命令
        script_path = os.path.join(os.path.dirname(__file__), "AutoNetworkAdapter.ps1")
        auto_update_param = "true" if auto_update else "false"
        
        # 执行PowerShell脚本
        command = [
            "powershell",
            "-ExecutionPolicy", "Bypass",
            "-File", script_path,
            "-AutoUpdate", auto_update_param
        ]
        
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=os.path.dirname(__file__),
                timeout=60
            )
            
            network_logger.info(f"网络自动适配脚本执行结果: {result.returncode}")
            network_logger.debug(f"脚本输出: {result.stdout}")
            if result.stderr:
                network_logger.error(f"脚本错误: {result.stderr}")
            
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            network_logger.error("网络自动适配脚本执行超时")
            return False
        except Exception as e:
            network_logger.error(f"执行网络自动适配脚本失败: {e}")
            return False
    
    def switch_to_next_ip(self):
        """切换到下一个API IP地址（已废弃）"""
        return None
    
    def switch_to_fastest_ip(self):
        """切换到响应时间最快的API IP地址（已废弃）"""
        return None
    
    def get_ip_response_times(self):
        """获取各IP地址的响应时间"""
        return self.session.ip_response_times
    
    def get_dns_stats(self):
        """
        获取DNS解析统计信息
        
        Returns:
            dict: DNS解析统计信息
        """
        return get_dns_stats()
    
    def reset_dns_stats(self):
        """
        重置DNS解析统计信息
        """
        reset_dns_stats()
    
    def switch_dns_region(self, region):
        """
        切换DNS服务器区域
        
        Args:
            region (str): 区域名称，可选值: global, asia, europe, north_america
            
        Returns:
            bool: 切换是否成功
        """
        return switch_dns_region(region)
    
    def update_dns_config(self, new_config):
        """
        动态更新DNS配置
        
        Args:
            new_config (dict): 新的DNS配置
            
        Returns:
            bool: 更新是否成功
        """
        return update_dns_config(new_config)
    
    def get_dns_config(self):
        """
        获取当前DNS配置
        
        Returns:
            dict: 当前DNS配置
        """
        from network.dns_resolver import CURRENT_DNS_CONFIG
        return CURRENT_DNS_CONFIG.copy()
    
    def _generate_signature(self, timestamp, method, request_path, body):
        """
        生成OKX API签名
        
        Args:
            timestamp (str): 时间戳
            method (str): HTTP方法（GET/POST）
            request_path (str): 请求路径
            body (str): 请求体（JSON字符串）
        
        Returns:
            str: 签名
        """
        # 确保method全部大写
        method = method.upper()
        
        # 拼接字符串，GET请求body为空字符串
        message = timestamp + method + request_path + body
        
        # 生成HMAC SHA256签名
        mac = hmac.new(bytes(self.api_secret, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
        d = mac.digest()
        
        # Base64编码
        return base64.b64encode(d).decode()
    
    def _get_headers(self, timestamp, sign, exp_time=None):
        """
        获取API请求头
        
        Args:
            timestamp (str): 时间戳
            sign (str): 签名
            exp_time (str, optional): 请求有效截止时间
        
        Returns:
            dict: 请求头
        """
        headers = {
            "Content-Type": "application/json",
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
        }
        
        # 模拟盘添加请求头
        if self.is_test:
            headers["x-simulated-trading"] = "1"
        
        # 添加请求有效截止时间
        if exp_time:
            headers["expTime"] = exp_time
            
        return headers
    
    def _get_public_headers(self):
        """
        获取公共API请求头（不需要签名）
        
        Returns:
            dict: 请求头
        """
        return {
            "Content-Type": "application/json",
        }
    
    def _get_timestamp(self):
        """
        获取当前时间戳
        
        Returns:
            str: ISO格式的时间戳
        """
        return time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
    
    def _request(self, method, endpoint, params=None, need_sign=True, exp_time=None):
        """
        发送API请求
        
        Args:
            method (str): HTTP方法（GET/POST）
            endpoint (str): API端点（如"public/ticker"）
            params (dict): 请求参数
            need_sign (bool): 是否需要签名
            exp_time (str, optional): 请求有效截止时间
        
        Returns:
            dict: API响应
        """
        # 确定请求区域
        if endpoint.startswith('market/'):
            request_region = "MarketData"
        elif endpoint.startswith('trade/'):
            request_region = "Trade"
        elif endpoint.startswith('account/'):
            request_region = "Account"
        elif endpoint.startswith('public/'):
            request_region = "Public"
        else:
            request_region = "API"
        
        # 获取区域化日志记录器
        api_logger = get_logger(request_region)
        
        # 构建请求URL
        request_path = f"{self.base_path}/api/{self.api_version}/{endpoint}"
        url = f"{self.parsed_url.scheme}://{self.host_name}{request_path}"
        
        # 构建请求体
        body = json.dumps(params) if (method == "POST" and params) else ""
        
        # 构建查询参数
        query_params = "" if not params else f"?{urlencode(params)}"
        if method == "GET":
            url += query_params
            request_path += query_params
        
        # 检查API密钥是否存在
        if need_sign and (not self.api_key or not self.api_secret or not self.passphrase):
            api_logger.error("API密钥未设置，无法发送需要签名的请求")
            return None
        
        # 获取时间戳和签名
        timestamp = self._get_timestamp()
        sign = self._generate_signature(timestamp, method, request_path, body) if need_sign else None
        
        # 获取请求头
        headers = self._get_headers(timestamp, sign, exp_time) if need_sign else self._get_public_headers()
        
        api_logger.debug(f"发送API请求: {method} {url}")
        api_logger.debug(f"请求头: {headers}")
        if body:
            api_logger.debug(f"请求体: {body}")
        
        # 记录请求开始时间
        start_time = time.time()
        success = False
        response_size = 0
        
        try:
            # 发送请求
            if method == "GET":
                response = self.session.get(url, headers=headers)
            else:
                response = self.session.post(url, headers=headers, data=body)
            
            # 记录响应大小
            response_size = len(response.content) if response.content else 0
            
            # 解析响应
            response_data = response.json()
            api_logger.debug(f"API响应: {response_data}")
            
            # 验证响应
            if not self._validate_response(response_data, method, url):
                return None
            
            success = True
            return response_data
        except requests.exceptions.RequestException as e:
            api_logger.error(f"HTTP请求失败: {e}")
            return None
        except json.JSONDecodeError as e:
            api_logger.error(f"解析API响应失败: {e}")
            return None
        finally:
            # 计算请求耗时
            request_time = time.time() - start_time
            
            # 记录网络请求信息
            try:
                from network.network_monitor import global_network_monitor
                global_network_monitor.record_request(
                    success=success,
                    request_time=request_time,
                    response_size=response_size
                )
            except Exception as e:
                api_logger.error(f"记录网络请求信息失败: {e}")
    
    def _validate_response(self, response, method, url):
        """
        验证API响应
        
        Args:
            response (dict): API响应
            method (str): HTTP方法
            url (str): 请求URL
        
        Returns:
            bool: 是否验证通过
        """
        # 确定响应区域
        if 'market' in url:
            response_region = "MarketData"
        elif 'trade' in url:
            response_region = "Trade"
        elif 'account' in url:
            response_region = "Account"
        elif 'public' in url:
            response_region = "Public"
        else:
            response_region = "API"
        
        # 获取区域化日志记录器
        api_logger = get_logger(response_region)
        
        if not response:
            api_logger.error(f"API请求失败，未收到响应: {method} {url}")
            return False
        
        if not isinstance(response, dict):
            api_logger.error(f"API响应格式错误，预期为字典类型: {method} {url}")
            return False
        
        if response.get('code') != '0':
            error_msg = response.get('msg', 'Unknown error')
            error_code = response.get('code', 'Unknown code')
            self._handle_api_error(error_code, error_msg, method, url, response_region)
            return False
        
        return True
    
    def _handle_api_error(self, error_code, error_msg, method, url, region="API"):
        """
        处理API错误，根据OKX API错误代码文档提供详细解释和处理建议
        
        Args:
            error_code (str): 错误码
            error_msg (str): 错误信息
            method (str): HTTP方法
            url (str): 请求URL
            region (str): 错误发生的区域
        """
        # 获取区域化日志记录器
        api_logger = get_logger(region)
        
        # 错误码分类处理
        error_info = {
            # 认证相关错误
            '100001': ('API密钥格式错误', '检查API密钥是否正确，确保没有空格或特殊字符'),
            '100002': ('签名无效', '检查签名生成算法是否正确，确保时间戳与服务器时间同步'),
            '100003': ('时间戳无效', '检查本地时间是否与服务器时间同步，时间差应小于30秒'),
            '100004': ('API密钥已过期', '请在OKX平台重新生成API密钥'),
            '100005': ('API密钥权限不足', '请在OKX平台检查API密钥权限设置'),
            
            # 参数相关错误
            '101001': ('参数格式错误', '检查请求参数格式是否符合API文档要求'),
            '101002': ('必填参数缺失', '检查是否遗漏了必填参数'),
            '101003': ('参数值超出范围', '检查参数值是否在允许范围内'),
            '101004': ('无效的交易对', '检查交易对是否存在或是否支持'),
            
            # 订单相关错误
            '102001': ('余额不足', '检查账户余额是否充足'),
            '102002': ('订单数量超出限制', '减少订单数量或联系OKX客服'),
            '102003': ('订单价格超出限制', '检查订单价格是否在允许范围内'),
            '102004': ('订单已存在', '请勿重复提交同一订单'),
            '102005': ('订单不存在', '检查订单ID是否正确'),
            
            # 系统相关错误
            '500001': ('系统错误', '请稍后重试或联系OKX客服'),
            '500002': ('服务繁忙', '请稍后重试或减少请求频率'),
            '500003': ('网络异常', '检查网络连接或代理设置'),
        }
        
        # 获取错误解释和处理建议
        if error_code in error_info:
            error_desc, error_suggestion = error_info[error_code]
            api_logger.error(f"API请求失败 (错误码: {error_code}): {error_msg} - {method} {url}")
            api_logger.error(f"错误解释: {error_desc}")
            api_logger.error(f"处理建议: {error_suggestion}")
        else:
            api_logger.error(f"API请求失败 (错误码: {error_code}): {error_msg} - {method} {url}")
            api_logger.error(f"请参考OKX API文档了解详细错误信息: https://www.oyuzh.org/docs-v5/zh/#error-code-rest-api-account")
    
    def _process_result(self, result):
        """
        处理API返回结果
        """
        if result and isinstance(result, dict):
            if result.get('code') == '0':
                return result.get('data')
            else:
                error_msg = result.get('msg', 'Unknown error')
                error_code = result.get('code', 'Unknown code')
                self._handle_api_error(error_code, error_msg, "N/A", "N/A", "API")
                return None
        return result
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def get_ticker(self, inst_id):
        """获取行情信息"""
        try:
            result = self._request(
                method="GET",
                endpoint="market/ticker",
                params={"instId": inst_id},
                need_sign=False
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"获取行情信息失败 [{inst_id}]: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def get_order_book(self, inst_id, depth=10):
        """获取订单簿数据"""
        try:
            result = self._request(
                method="GET",
                endpoint="market/books",
                params={"instId": inst_id, "sz": depth},
                need_sign=False
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"获取订单簿数据失败 [{inst_id}]: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def get_candlesticks(self, inst_id, bar='1m', limit=100):
        """获取K线数据"""
        try:
            result = self._request(
                method="GET",
                endpoint="market/candles",
                params={"instId": inst_id, "bar": bar, "limit": limit},
                need_sign=False
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"获取K线数据失败 [{inst_id}, {bar}]: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def get_trades(self, inst_id, limit=50):
        """获取成交数据"""
        try:
            result = self._request(
                method="GET",
                endpoint="market/trades",
                params={"instId": inst_id, "limit": limit},
                need_sign=False
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"获取成交数据失败 [{inst_id}]: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def get_server_time(self):
        """获取服务器时间"""
        try:
            result = self._request(
                method="GET",
                endpoint="public/time",
                need_sign=False
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"获取服务器时间失败: {e}")
            return None
    
    # 交易相关方法
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def place_order(self, inst_id, side, ord_type, sz, px=None, td_mode=None, cl_ord_id=None, tag=None, pos_side=None, reduce_only=None, tgt_ccy=None, tp_px=None, tp_trigger_px=None, tp_ord_px=None, sl_px=None, sl_trigger_px=None, sl_ord_px=None, tp_trigger_px_type=None, sl_trigger_px_type=None, quick_mgn_type=None, req_id=None, exp_time=None):
        """下单
        
        Args:
            inst_id (str): 交易产品ID
            side (str): 订单方向 (buy/sell)
            ord_type (str): 订单类型 (market/limit/post_only/fok/ioc/optimal_limit_ioc/optimal_limit_fok)
            sz (str): 订单数量
            px (str, optional): 订单价格 (限价单必填)
            td_mode (str, optional): 交易模式 (cash/cross/isolated)
            cl_ord_id (str, optional): 客户自定义订单ID
            tag (str, optional): 订单标签
            pos_side (str, optional): 持仓方向 (net/long/short)
            reduce_only (bool, optional): 是否仅减仓
            tgt_ccy (str, optional): 目标币种
            tp_px (str, optional): 止盈价格
            tp_trigger_px (str, optional): 止盈触发价格
            tp_ord_px (str, optional): 止盈委托价格
            sl_px (str, optional): 止损价格
            sl_trigger_px (str, optional): 止损触发价格
            sl_ord_px (str, optional): 止损委托价格
            tp_trigger_px_type (str, optional): 止盈触发价格类型
            sl_trigger_px_type (str, optional): 止损触发价格类型
            quick_mgn_type (str, optional): 快捷杠杆类型
            req_id (str, optional): 请求ID
            exp_time (str, optional): 请求有效截止时间
        
        Returns:
            dict: 订单信息
        """
        try:
            params = {
                'instId': inst_id,
                'side': side,
                'ordType': ord_type,
                'sz': sz
            }
            
            # 可选参数
            if px:
                params['px'] = px
            if td_mode:
                params['tdMode'] = td_mode
            if cl_ord_id:
                params['clOrdId'] = cl_ord_id
            if tag:
                params['tag'] = tag
            if pos_side:
                params['posSide'] = pos_side
            if reduce_only:
                params['reduceOnly'] = reduce_only
            if tgt_ccy:
                params['tgtCcy'] = tgt_ccy
            if tp_px:
                params['tpPx'] = tp_px
            if tp_trigger_px:
                params['tpTriggerPx'] = tp_trigger_px
            if tp_ord_px:
                params['tpOrdPx'] = tp_ord_px
            if sl_px:
                params['slPx'] = sl_px
            if sl_trigger_px:
                params['slTriggerPx'] = sl_trigger_px
            if sl_ord_px:
                params['slOrdPx'] = sl_ord_px
            if tp_trigger_px_type:
                params['tpTriggerPxType'] = tp_trigger_px_type
            if sl_trigger_px_type:
                params['slTriggerPxType'] = sl_trigger_px_type
            if quick_mgn_type:
                params['quickMgnType'] = quick_mgn_type
            if req_id:
                params['reqId'] = req_id
            
            result = self._request(
                method="POST",
                endpoint="trade/order",
                params=params,
                need_sign=True,
                exp_time=exp_time
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"下单失败 [{inst_id}, {side}, {ord_type}]: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def batch_place_orders(self, orders, exp_time=None):
        """批量下单
        
        Args:
            orders (list): 订单列表，每个订单包含必要的下单参数
            exp_time (str, optional): 请求有效截止时间
        
        Returns:
            dict: 批量下单结果
        """
        try:
            result = self._request(
                method="POST",
                endpoint="trade/batch-orders",
                params=orders,
                need_sign=True,
                exp_time=exp_time
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"批量下单失败: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def cancel_order(self, inst_id, ord_id, cl_ord_id=None, sub_ord_id=None, req_id=None, exp_time=None):
        """取消订单
        
        Args:
            inst_id (str): 交易产品ID
            ord_id (str, optional): 订单ID
            cl_ord_id (str, optional): 客户自定义订单ID
            sub_ord_id (str, optional): 子订单ID
            req_id (str, optional): 请求ID
            exp_time (str, optional): 请求有效截止时间
        
        Returns:
            dict: 取消订单结果
        """
        try:
            params = {
                'instId': inst_id
            }
            
            if ord_id:
                params['ordId'] = ord_id
            if cl_ord_id:
                params['clOrdId'] = cl_ord_id
            if sub_ord_id:
                params['subOrdId'] = sub_ord_id
            if req_id:
                params['reqId'] = req_id
            
            result = self._request(
                method="POST",
                endpoint="trade/cancel-order",
                params=params,
                need_sign=True,
                exp_time=exp_time
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"取消订单失败 [{inst_id}, {ord_id}]: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def batch_cancel_orders(self, cancel_orders, exp_time=None):
        """批量取消订单
        
        Args:
            cancel_orders (list): 取消订单列表，每个订单包含必要的取消参数
            exp_time (str, optional): 请求有效截止时间
        
        Returns:
            dict: 批量取消订单结果
        """
        try:
            result = self._request(
                method="POST",
                endpoint="trade/batch-cancel-orders",
                params=cancel_orders,
                need_sign=True,
                exp_time=exp_time
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"批量取消订单失败: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def get_order(self, inst_id, ord_id=None, cl_ord_id=None, sub_ord_id=None):
        """获取订单信息
        
        Args:
            inst_id (str): 交易产品ID
            ord_id (str, optional): 订单ID
            cl_ord_id (str, optional): 客户自定义订单ID
            sub_ord_id (str, optional): 子订单ID
        
        Returns:
            dict: 订单信息
        """
        try:
            params = {
                'instId': inst_id
            }
            
            if ord_id:
                params['ordId'] = ord_id
            if cl_ord_id:
                params['clOrdId'] = cl_ord_id
            if sub_ord_id:
                params['subOrdId'] = sub_ord_id
            
            result = self._request(
                method="GET",
                endpoint="trade/order",
                params=params,
                need_sign=True
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"获取订单信息失败 [{inst_id}, {ord_id}]: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def amend_order(self, inst_id, ord_id=None, cl_ord_id=None, req_id=None, new_sz=None, new_px=None, tp_px=None, tp_trigger_px=None, tp_ord_px=None, sl_px=None, sl_trigger_px=None, sl_ord_px=None, tp_trigger_px_type=None, sl_trigger_px_type=None, sub_ord_id=None, exp_time=None):
        """修改订单
        
        Args:
            inst_id (str): 交易产品ID
            ord_id (str, optional): 订单ID
            cl_ord_id (str, optional): 客户自定义订单ID
            req_id (str, optional): 请求ID
            new_sz (str, optional): 新的订单数量
            new_px (str, optional): 新的订单价格
            tp_px (str, optional): 新的止盈价格
            tp_trigger_px (str, optional): 新的止盈触发价格
            tp_ord_px (str, optional): 新的止盈委托价格
            sl_px (str, optional): 新的止损价格
            sl_trigger_px (str, optional): 新的止损触发价格
            sl_ord_px (str, optional): 新的止损委托价格
            tp_trigger_px_type (str, optional): 新的止盈触发价格类型
            sl_trigger_px_type (str, optional): 新的止损触发价格类型
            sub_ord_id (str, optional): 子订单ID
            exp_time (str, optional): 请求有效截止时间
        
        Returns:
            dict: 修改订单结果
        """
        try:
            params = {
                'instId': inst_id
            }
            
            if ord_id:
                params['ordId'] = ord_id
            if cl_ord_id:
                params['clOrdId'] = cl_ord_id
            if req_id:
                params['reqId'] = req_id
            if new_sz:
                params['newSz'] = new_sz
            if new_px:
                params['newPx'] = new_px
            if tp_px:
                params['tpPx'] = tp_px
            if tp_trigger_px:
                params['tpTriggerPx'] = tp_trigger_px
            if tp_ord_px:
                params['tpOrdPx'] = tp_ord_px
            if sl_px:
                params['slPx'] = sl_px
            if sl_trigger_px:
                params['slTriggerPx'] = sl_trigger_px
            if sl_ord_px:
                params['slOrdPx'] = sl_ord_px
            if tp_trigger_px_type:
                params['tpTriggerPxType'] = tp_trigger_px_type
            if sl_trigger_px_type:
                params['slTriggerPxType'] = sl_trigger_px_type
            if sub_ord_id:
                params['subOrdId'] = sub_ord_id
            
            result = self._request(
                method="POST",
                endpoint="trade/amend-order",
                params=params,
                need_sign=True,
                exp_time=exp_time
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"修改订单失败 [{inst_id}, {ord_id}]: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def batch_amend_orders(self, amend_orders, exp_time=None):
        """批量修改订单
        
        Args:
            amend_orders (list): 修改订单列表，每个订单包含必要的修改参数
            exp_time (str, optional): 请求有效截止时间
        
        Returns:
            dict: 批量修改订单结果
        """
        try:
            result = self._request(
                method="POST",
                endpoint="trade/batch-amend-orders",
                params=amend_orders,
                need_sign=True,
                exp_time=exp_time
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"批量修改订单失败: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def get_pending_orders(self, inst_id=None, state=None, ord_type=None, after=None, before=None, limit=50):
        """获取未成交订单
        
        Args:
            inst_id (str, optional): 交易产品ID
            state (str, optional): 订单状态 (pending/partially_filled)
            ord_type (str, optional): 订单类型
            after (str, optional): 请求此ID之前（更旧）的分页数据
            before (str, optional): 请求此ID之后（更新）的分页数据
            limit (int, optional): 返回结果的数量，默认50
        
        Returns:
            dict: 未成交订单列表
        """
        try:
            params = {
                'limit': limit
            }
            
            if inst_id:
                params['instId'] = inst_id
            if state:
                params['state'] = state
            if ord_type:
                params['ordType'] = ord_type
            if after:
                params['after'] = after
            if before:
                params['before'] = before
            
            result = self._request(
                method="GET",
                endpoint="trade/orders-pending",
                params=params,
                need_sign=True
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"获取未成交订单失败 [{inst_id}]: {e}")
            return None
    
    # 账户相关方法
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def get_account_balance(self, ccy=None):
        """获取账户余额
        
        Args:
            ccy (str, optional): 币种，支持多币种查询，用逗号分隔，不超过20个
        
        Returns:
            dict: 账户余额信息
        """
        try:
            params = {}
            if ccy:
                params['ccy'] = ccy
            
            result = self._request(
                method="GET",
                endpoint="account/balance",
                params=params,
                need_sign=True
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"获取账户余额失败: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def get_positions(self, inst_id=None, inst_type=None, pos_id=None):
        """获取持仓信息
        
        Args:
            inst_id (str, optional): 交易产品ID，支持多个，用逗号分隔，不超过10个
            inst_type (str, optional): 产品类型 (MARGIN/SWAP/FUTURES/OPTION)
            pos_id (str, optional): 持仓ID，支持多个，用逗号分隔，不超过20个
        
        Returns:
            dict: 持仓信息列表
        """
        try:
            params = {}
            
            if inst_id:
                params['instId'] = inst_id
            if inst_type:
                params['instType'] = inst_type
            if pos_id:
                params['posId'] = pos_id
            
            result = self._request(
                method="GET",
                endpoint="account/positions",
                params=params,
                need_sign=True
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"获取持仓信息失败 [{inst_id}]: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def get_instruments(self, inst_type, inst_family=None, inst_id=None):
        """获取交易产品基础信息
        
        Args:
            inst_type (str): 产品类型 (SPOT/MARGIN/SWAP/FUTURES/OPTION)
            inst_family (str, optional): 交易品种，仅适用于交割/永续/期权，期权必填
            inst_id (str, optional): 产品ID
        
        Returns:
            dict: 交易产品基础信息列表
        """
        try:
            params = {
                'instType': inst_type
            }
            
            if inst_family:
                params['instFamily'] = inst_family
            if inst_id:
                params['instId'] = inst_id
            
            result = self._request(
                method="GET",
                endpoint="account/instruments",
                params=params,
                need_sign=True
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"获取交易产品基础信息失败 [{inst_type}]: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def set_leverage(self, inst_id, lever, mgn_mode='isolated', pos_side=None, ccy=None):
        """设置杠杆
        
        Args:
            inst_id (str): 交易产品ID
            lever (str): 杠杆倍数
            mgn_mode (str, optional): 保证金模式 (isolated/cross)
            pos_side (str, optional): 持仓方向 (long/short)
            ccy (str, optional): 币种，仅适用于跨币种保证金模式
        
        Returns:
            dict: 设置杠杆结果
        """
        try:
            params = {
                'instId': inst_id,
                'lever': str(lever),
                'mgnMode': mgn_mode
            }
            
            if pos_side:
                params['posSide'] = pos_side
            if ccy:
                params['ccy'] = ccy
            
            result = self._request(
                method="POST",
                endpoint="account/set-leverage",
                params=params,
                need_sign=True
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"设置杠杆失败 [{inst_id}, {lever}, {mgn_mode}]: {e}")
            return None
    
    # 资金相关方法
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def get_balances(self):
        """获取资金账户余额"""
        try:
            result = self._request(
                method="GET",
                endpoint="asset/balances",
                need_sign=True
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"获取资金账户余额失败: {e}")
            return None
    
    @retry_with_backoff(max_retries=3, exceptions=(requests.exceptions.RequestException,))
    def transfer(self, ccy, amt, from_, to, sub_acct=None):
        """资金划转"""
        try:
            params = {
                'ccy': ccy,
                'amt': amt,
                'from': from_,
                'to': to
            }
            if sub_acct:
                params['subAcct'] = sub_acct
            
            result = self._request(
                method="POST",
                endpoint="asset/transfer",
                params=params,
                need_sign=True
            )
            return self._process_result(result)
        except Exception as e:
            logger.error(f"资金划转失败 [{ccy}, {amt}, {from_} → {to}]: {e}")
            return None

# 创建默认客户端实例
client = None

def get_client():
    """获取默认客户端实例"""
    global client
    if not client:
        # 从配置文件加载API配置
        import os
        import json
        config_path = os.path.join(os.path.dirname(__file__), 'config/okx_config.json')
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            api_config = config.get('api', {})
            client = OKXAPIClient(
                api_key=api_config.get('api_key'),
                api_secret=api_config.get('api_secret'),
                passphrase=api_config.get('passphrase'),
                is_test=api_config.get('is_test', False),
                api_url=api_config.get('api_url'),
                api_ip=api_config.get('api_ip'),
                api_ips=api_config.get('api_ips', []),
                timeout=api_config.get('timeout', 30)
            )
        except Exception as e:
            logger.error(f"从配置文件加载客户端配置失败: {e}")
            client = OKXAPIClient()
    return client

if __name__ == "__main__":
    # 测试客户端
    try:
        # 创建客户端，使用API IP地址绕过DNS解析
        test_client = OKXAPIClient(
            is_test=True,
            api_ip='18.141.249.241'  # OKX API的IP地址，用于绕过DNS解析
        )
        
        # 测试获取行情
        ticker = test_client.get_ticker('BTC-USDT-SWAP')
        if ticker:
            logger.info(f"BTC-USDT-SWAP 行情: {ticker[0]['last']}")
        else:
            logger.warning("无法获取行情数据，可能是API密钥未配置或测试网问题")
            
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
