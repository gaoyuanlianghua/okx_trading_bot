#!/usr/bin/env python3
"""
性能测试和压力测试脚本
"""

import time
import psutil
import subprocess
import os
import sys
import json
from datetime import datetime

class PerformanceTester:
    def __init__(self):
        self.process = None
        self.start_time = None
        self.end_time = None
        self.memory_usage = []
        self.cpu_usage = []
    
    def start_application(self):
        """
        启动应用程序
        """
        print("启动应用程序...")
        self.start_time = time.time()
        
        # 启动应用程序
        self.process = subprocess.Popen([sys.executable, "websocket_gui.py"])
        
        # 等待应用程序启动
        time.sleep(5)
        
        print(f"应用程序已启动，进程ID: {self.process.pid}")
    
    def monitor_resources(self, duration=30, interval=1):
        """
        监控资源使用情况
        """
        print(f"监控资源使用情况，持续 {duration} 秒...")
        
        start = time.time()
        while time.time() - start < duration:
            try:
                proc = psutil.Process(self.process.pid)
                memory_info = proc.memory_info()
                cpu_percent = proc.cpu_percent(interval=0.1)
                
                self.memory_usage.append({
                    "time": time.time() - start,
                    "memory": memory_info.rss / (1024 * 1024)  # 转换为MB
                })
                
                self.cpu_usage.append({
                    "time": time.time() - start,
                    "cpu": cpu_percent
                })
                
                print(f"时间: {time.time() - start:.2f}s, 内存: {memory_info.rss / (1024 * 1024):.2f}MB, CPU: {cpu_percent:.2f}%")
                time.sleep(interval)
            except psutil.NoSuchProcess:
                print("进程已结束")
                break
    
    def stop_application(self):
        """
        停止应用程序
        """
        if self.process:
            print("停止应用程序...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.end_time = time.time()
            print("应用程序已停止")
    
    def generate_report(self):
        """
        生成性能测试报告
        """
        if not self.start_time or not self.end_time:
            print("测试未完成，无法生成报告")
            return
        
        total_time = self.end_time - self.start_time
        avg_memory = sum(item["memory"] for item in self.memory_usage) / len(self.memory_usage) if self.memory_usage else 0
        max_memory = max(item["memory"] for item in self.memory_usage) if self.memory_usage else 0
        avg_cpu = sum(item["cpu"] for item in self.cpu_usage) / len(self.cpu_usage) if self.cpu_usage else 0
        max_cpu = max(item["cpu"] for item in self.cpu_usage) if self.cpu_usage else 0
        
        report = {
            "测试时间": datetime.now().isoformat(),
            "启动时间": f"{total_time:.2f}秒",
            "平均内存使用": f"{avg_memory:.2f}MB",
            "最大内存使用": f"{max_memory:.2f}MB",
            "平均CPU使用率": f"{avg_cpu:.2f}%",
            "最大CPU使用率": f"{max_cpu:.2f}%"
        }
        
        print("\n性能测试报告:")
        for key, value in report.items():
            print(f"{key}: {value}")
        
        # 保存报告到文件
        with open("performance_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print("\n报告已保存到 performance_report.json")

def main():
    tester = PerformanceTester()
    
    try:
        tester.start_application()
        tester.monitor_resources()
    finally:
        tester.stop_application()
        tester.generate_report()

if __name__ == "__main__":
    main()
