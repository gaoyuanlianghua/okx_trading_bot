import os
import time
import psutil
from datetime import datetime, timedelta
from threading import Thread, Lock

# 初始化日志配置
from commons.logger_config import global_logger_config

# 获取区域化日志记录器
def get_logger(region=None):
    return global_logger_config.get_logger(region=region)

# 创建默认日志记录器
logger = get_logger("Process")

class ProcessMonitor:
    """进程监控器，用于监控项目最近3分钟运行的进程"""
    
    def __init__(self, process_name=None, monitor_interval=10):
        """
        初始化进程监控器
        
        Args:
            process_name (str, optional): 要监控的进程名称
            monitor_interval (int, optional): 监控间隔（秒）
        """
        self.process_name = process_name
        self.monitor_interval = monitor_interval
        self.process_history = []  # 进程历史记录
        self.history_lock = Lock()
        self.is_running = False
        self.monitor_thread = None
        
        # 保留最近3分钟的进程记录
        self.retention_period = 3 * 60  # 3分钟
        
        logger.info("进程监控器初始化完成")
    
    def start(self):
        """启动进程监控"""
        if not self.is_running:
            self.is_running = True
            self.monitor_thread = Thread(target=self._monitor_loop)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            logger.info("进程监控已启动")
    
    def stop(self):
        """停止进程监控"""
        if self.is_running:
            self.is_running = False
            if self.monitor_thread:
                self.monitor_thread.join()
            logger.info("进程监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.is_running:
            try:
                # 记录当前进程状态
                self._record_process_status()
                
                # 清理过期的进程记录
                self._cleanup_old_records()
                
                # 等待下一次监控
                time.sleep(self.monitor_interval)
            except Exception as e:
                logger.error(f"进程监控失败: {e}")
                time.sleep(self.monitor_interval)
    
    def _record_process_status(self):
        """记录当前进程状态"""
        try:
            # 获取当前进程
            current_process = psutil.Process(os.getpid())
            
            # 获取进程信息
            process_info = {
                'timestamp': time.time(),
                'datetime': datetime.now().isoformat(),
                'pid': current_process.pid,
                'name': current_process.name(),
                'status': current_process.status(),
                'cpu_percent': current_process.cpu_percent(interval=0.1),
                'memory_percent': current_process.memory_percent(),
                'memory_info': current_process.memory_info()._asdict(),
                'threads': current_process.num_threads(),
                'open_files': len(current_process.open_files()) if hasattr(current_process, 'open_files') else 0,
                'connections': len(current_process.connections()) if hasattr(current_process, 'connections') else 0
            }
            
            # 添加到历史记录
            with self.history_lock:
                self.process_history.append(process_info)
                
            # 记录日志
            logger.info(f"进程状态: 名称={process_info['name']}, PID={process_info['pid']}, CPU={process_info['cpu_percent']:.2f}%, 内存={process_info['memory_percent']:.2f}%")
            
        except Exception as e:
            logger.error(f"记录进程状态失败: {e}")
    
    def _cleanup_old_records(self):
        """清理过期的进程记录"""
        try:
            current_time = time.time()
            cutoff_time = current_time - self.retention_period
            
            with self.history_lock:
                # 过滤掉过期的记录
                self.process_history = [record for record in self.process_history if record['timestamp'] >= cutoff_time]
                
        except Exception as e:
            logger.error(f"清理进程记录失败: {e}")
    
    def get_process_history(self):
        """
        获取进程历史记录
        
        Returns:
            list: 进程历史记录
        """
        with self.history_lock:
            return self.process_history.copy()
    
    def get_latest_process_status(self):
        """
        获取最新的进程状态
        
        Returns:
            dict: 最新的进程状态
        """
        with self.history_lock:
            if self.process_history:
                return self.process_history[-1]
            return None
    
    def get_process_summary(self):
        """
        获取进程汇总信息
        
        Returns:
            dict: 进程汇总信息
        """
        try:
            with self.history_lock:
                if not self.process_history:
                    return None
                
                # 计算平均值
                cpu_percents = [record['cpu_percent'] for record in self.process_history]
                memory_percents = [record['memory_percent'] for record in self.process_history]
                
                summary = {
                    'timestamp': time.time(),
                    'datetime': datetime.now().isoformat(),
                    'record_count': len(self.process_history),
                    'avg_cpu_percent': sum(cpu_percents) / len(cpu_percents) if cpu_percents else 0,
                    'max_cpu_percent': max(cpu_percents) if cpu_percents else 0,
                    'min_cpu_percent': min(cpu_percents) if cpu_percents else 0,
                    'avg_memory_percent': sum(memory_percents) / len(memory_percents) if memory_percents else 0,
                    'max_memory_percent': max(memory_percents) if memory_percents else 0,
                    'min_memory_percent': min(memory_percents) if memory_percents else 0,
                    'latest_status': self.process_history[-1] if self.process_history else None
                }
                
                return summary
                
        except Exception as e:
            logger.error(f"获取进程汇总信息失败: {e}")
            return None

# 全局进程监控实例
global_process_monitor = ProcessMonitor()

# 启动进程监控
global_process_monitor.start()

if __name__ == "__main__":
    # 测试进程监控
    try:
        # 启动监控
        monitor = ProcessMonitor(monitor_interval=5)
        monitor.start()
        
        # 运行一段时间
        time.sleep(20)
        
        # 获取进程历史
        history = monitor.get_process_history()
        logger.info(f"进程历史记录数: {len(history)}")
        
        # 获取最新状态
        latest = monitor.get_latest_process_status()
        if latest:
            logger.info(f"最新进程状态: {latest}")
        
        # 获取汇总信息
        summary = monitor.get_process_summary()
        if summary:
            logger.info(f"进程汇总信息: {summary}")
        
        # 停止监控
        monitor.stop()
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
