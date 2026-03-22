"""
事件总线单元测试
"""

import unittest
import threading
import time
from commons.event_bus import EventBus


class TestEventBus(unittest.TestCase):
    """测试事件总线功能"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.event_bus = EventBus()
        self.received_events = []
        self.lock = threading.Lock()
    
    def test_subscribe_and_publish(self):
        """测试订阅和发布事件"""
        # 定义回调函数
        def callback(data):
            with self.lock:
                self.received_events.append(data)
        
        # 订阅事件
        self.event_bus.subscribe('test_event', callback)
        
        # 发布事件
        test_data = {'key': 'value'}
        self.event_bus.publish('test_event', test_data)
        
        # 验证事件是否被正确接收
        time.sleep(0.1)  # 等待异步处理
        with self.lock:
            self.assertEqual(len(self.received_events), 1)
            self.assertEqual(self.received_events[0], test_data)
    
    def test_multiple_subscribers(self):
        """测试多个订阅者"""
        callback1_count = 0
        callback2_count = 0
        
        def callback1(data):
            nonlocal callback1_count
            callback1_count += 1
        
        def callback2(data):
            nonlocal callback2_count
            callback2_count += 1
        
        # 订阅同一个事件
        self.event_bus.subscribe('test_event', callback1)
        self.event_bus.subscribe('test_event', callback2)
        
        # 发布事件
        self.event_bus.publish('test_event', {'data': 'test'})
        
        # 验证两个回调都被调用
        time.sleep(0.1)
        self.assertEqual(callback1_count, 1)
        self.assertEqual(callback2_count, 1)
    
    def test_unsubscribe(self):
        """测试取消订阅"""
        def callback(data):
            with self.lock:
                self.received_events.append(data)
        
        # 订阅事件
        self.event_bus.subscribe('test_event', callback)
        
        # 取消订阅
        self.event_bus.unsubscribe('test_event', callback)
        
        # 发布事件
        self.event_bus.publish('test_event', {'key': 'value'})
        
        # 验证事件没有被接收
        time.sleep(0.1)
        with self.lock:
            self.assertEqual(len(self.received_events), 0)
    
    def test_thread_safety(self):
        """测试线程安全性"""
        event_count = 0
        lock = threading.Lock()
        
        def callback(data):
            nonlocal event_count
            with lock:
                event_count += 1
        
        # 订阅事件
        self.event_bus.subscribe('thread_safe_event', callback)
        
        # 多线程发布事件
        threads = []
        for i in range(10):
            thread = threading.Thread(
                target=self.event_bus.publish,
                args=('thread_safe_event', {'thread': i})
            )
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 验证所有事件都被处理
        self.assertEqual(event_count, 10)
    
    def test_publish_nonexistent_event(self):
        """测试发布不存在的事件"""
        # 发布一个没有订阅者的事件，应该不会抛出异常
        try:
            self.event_bus.publish('nonexistent_event', {'data': 'test'})
            success = True
        except Exception:
            success = False
        
        self.assertTrue(success)
    
    def test_callback_exception_handling(self):
        """测试回调函数异常处理"""
        def failing_callback(data):
            raise ValueError("Callback failed")
        
        # 订阅事件
        self.event_bus.subscribe('failing_event', failing_callback)
        
        # 发布事件，应该不会影响其他事件处理
        try:
            self.event_bus.publish('failing_event', {'data': 'test'})
            success = True
        except Exception:
            success = False
        
        self.assertTrue(success)


if __name__ == '__main__':
    unittest.main()
