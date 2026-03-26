import time
from commons.process_monitor import global_process_monitor
from commons.logger_config import global_logger as logger

if __name__ == "__main__":
    try:
        logger.info("开始测试进程监控")
        
        # 启动进程监控
        global_process_monitor.start_monitoring()
        
        # 运行一段时间
        logger.info("进程监控已启动，运行10秒...")
        for i in range(10):
            logger.info(f"测试进行中: {i+1}/10")
            time.sleep(1)
        
        # 获取进程监控摘要
        summary = global_process_monitor.get_process_summary()
        logger.info(f"进程监控摘要: {summary}")
        
        # 获取最近的进程记录
        recent_processes = global_process_monitor.get_recent_processes()
        logger.info(f"最近的进程记录数量: {len(recent_processes)}")
        
        # 停止进程监控
        global_process_monitor.stop_monitoring()
        
        logger.info("进程监控测试完成")
        
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
