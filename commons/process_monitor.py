import os
import time
import psutil
from loguru import logger

class ProcessMonitor:
    """
    进程监控类，用于监控项目最近3分钟运行的进程
    """
    
    def __init__(self, monitor_interval=5, history_duration=180):
        """
        初始化进程监控
        
        Args:
            monitor_interval (int): 监控间隔，单位秒
            history_duration (int): 历史记录时长，单位秒
        """
        self.monitor_interval = monitor_interval
        self.history_duration = history_duration
        self.process_history = []
        self.is_running = False
        self.monitor_thread = None
        
    def start_monitoring(self):
        """
        开始监控进程
        """
        if self.is_running:
            logger.warning("进程监控已经在运行中")
            return
        
        self.is_running = True
        logger.info("开始进程监控")
        
        # 启动监控线程
        import threading
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """
        停止监控进程
        """
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("停止进程监控")
    
    def _monitor_loop(self):
        """
        监控循环
        """
        while self.is_running:
            try:
                # 获取当前进程信息
                current_process = psutil.Process(os.getpid())
                process_info = self._get_process_info(current_process)
                
                # 添加到历史记录
                self.process_history.append({
                    'timestamp': time.time(),
                    'process_info': process_info
                })
                
                # 清理过期的历史记录
                self._cleanup_history()
                
                # 记录进程信息
                self._log_process_info(process_info)
                
            except Exception as e:
                logger.error(f"进程监控出错: {e}")
            
            # 等待下一次监控
            time.sleep(self.monitor_interval)
    
    def _get_process_info(self, process):
        """
        获取进程信息
        
        Args:
            process (psutil.Process): 进程对象
            
        Returns:
            dict: 进程信息
        """
        try:
            info = {
                'pid': process.pid,
                'name': process.name(),
                'status': process.status(),
                'cpu_percent': process.cpu_percent(interval=0.1),
                'memory_percent': process.memory_percent(),
                'memory_info': process.memory_info()._asdict(),
                'num_threads': process.num_threads(),
                'create_time': process.create_time(),
                'cmdline': ' '.join(process.cmdline())
            }
            
            # 获取系统信息
            info['system'] = {
                'cpu_count': psutil.cpu_count(),
                'cpu_percent': psutil.cpu_percent(interval=0.1),
                'virtual_memory': psutil.virtual_memory()._asdict(),
                'disk_usage': psutil.disk_usage('/')._asdict()
            }
            
            return info
        except Exception as e:
            logger.error(f"获取进程信息失败: {e}")
            return {}
    
    def _cleanup_history(self):
        """
        清理过期的历史记录
        """
        current_time = time.time()
        self.process_history = [
            item for item in self.process_history
            if current_time - item['timestamp'] <= self.history_duration
        ]
    
    def _log_process_info(self, process_info):
        """
        记录进程信息
        
        Args:
            process_info (dict): 进程信息
        """
        if not process_info:
            return
        
        logger.info(
            f"进程监控 | PID: {process_info.get('pid')} | 名称: {process_info.get('name')} | "
            f"CPU: {process_info.get('cpu_percent', 0):.2f}% | 内存: {process_info.get('memory_percent', 0):.2f}% | "
            f"线程数: {process_info.get('num_threads', 0)} | 状态: {process_info.get('status')}"
        )
    
    def get_recent_processes(self):
        """
        获取最近3分钟的进程记录
        
        Returns:
            list: 进程记录列表
        """
        return self.process_history
    
    def get_process_summary(self):
        """
        获取进程监控摘要
        
        Returns:
            dict: 进程监控摘要
        """
        if not self.process_history:
            return {
                'total_records': 0,
                'recent_processes': [],
                'system_stats': {}
            }
        
        # 计算平均CPU和内存使用率
        cpu_percents = [item['process_info'].get('cpu_percent', 0) for item in self.process_history]
        memory_percents = [item['process_info'].get('memory_percent', 0) for item in self.process_history]
        
        avg_cpu = sum(cpu_percents) / len(cpu_percents) if cpu_percents else 0
        avg_memory = sum(memory_percents) / len(memory_percents) if memory_percents else 0
        
        # 获取最新的系统信息
        latest_system_info = self.process_history[-1]['process_info'].get('system', {})
        
        return {
            'total_records': len(self.process_history),
            'average_cpu_percent': avg_cpu,
            'average_memory_percent': avg_memory,
            'latest_system_info': latest_system_info,
            'recent_processes': self.process_history[-10:]  # 返回最近10条记录
        }

# 创建全局进程监控实例
global_process_monitor = ProcessMonitor()
