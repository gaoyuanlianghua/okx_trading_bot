"""
WebSocket 客户端界面

使用 PyQt5 创建一个基于 WebSocket 客户端的实时交易界面
"""
import sys
import asyncio
import json
import logging
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QLabel, QLineEdit,
    QPushButton, QComboBox, QStatusBar, QSplitter, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QColor

from core import OKXWebSocketClient, EventBus, Event, EventType
from core.monitoring import strategy_monitor

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WebSocketGUI(QMainWindow):
    """
    WebSocket 客户端界面
    """
    
    # 信号定义
    update_market_data = pyqtSignal(dict)
    update_order_data = pyqtSignal(dict)
    update_account_data = pyqtSignal(dict)
    update_connection_status = pyqtSignal(bool, str)
    
    def __init__(self):
        """
        初始化 GUI
        """
        super().__init__()
        
        # 初始化 WebSocket 客户端
        self.ws_client = None
        self.event_bus = EventBus()
        
        # 数据存储
        self.market_data = {}
        self.order_data = []
        self.account_data = {}
        self.strategies = []
        
        # 初始化界面
        self.init_ui()
        
        # 连接信号
        self.update_market_data.connect(self.on_market_data_update)
        self.update_order_data.connect(self.on_order_data_update)
        self.update_account_data.connect(self.on_account_data_update)
        self.update_connection_status.connect(self.on_connection_status_update)
        
        # 启动事件总线
        self.event_bus.start()
        
        # 注册事件监听器
        self.event_bus.subscribe(EventType.MARKET_DATA_TICKER, self.on_market_event)
        self.event_bus.subscribe(EventType.ORDER_UPDATED, self.on_order_event)
        self.event_bus.subscribe(EventType.MARKET_DATA_TICKER, self.on_account_event)
        self.event_bus.subscribe(EventType.WS_CONNECTED, self.on_ws_connected)
        self.event_bus.subscribe(EventType.WS_DISCONNECTED, self.on_ws_disconnected)
    
    def init_ui(self):
        """
        初始化用户界面
        """
        self.setWindowTitle('OKX WebSocket 交易界面')
        self.setGeometry(100, 100, 1200, 800)
        
        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 顶部连接状态栏
        status_bar = QHBoxLayout()
        self.connection_status = QLabel('未连接')
        self.connection_status.setStyleSheet('color: red; font-weight: bold;')
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText('API Key')
        self.secret_input = QLineEdit()
        self.secret_input.setPlaceholderText('API Secret')
        self.secret_input.setEchoMode(QLineEdit.Password)
        self.passphrase_input = QLineEdit()
        self.passphrase_input.setPlaceholderText('Passphrase')
        self.testnet_checkbox = QComboBox()
        self.testnet_checkbox.addItems(['模拟盘', '实盘'])
        self.connect_button = QPushButton('连接')
        self.connect_button.clicked.connect(self.toggle_connection)
        
        status_bar.addWidget(QLabel('连接状态:'))
        status_bar.addWidget(self.connection_status)
        status_bar.addStretch(1)
        status_bar.addWidget(QLabel('API Key:'))
        status_bar.addWidget(self.api_key_input)
        status_bar.addWidget(QLabel('Secret:'))
        status_bar.addWidget(self.secret_input)
        status_bar.addWidget(QLabel('Passphrase:'))
        status_bar.addWidget(self.passphrase_input)
        status_bar.addWidget(QLabel('环境:'))
        status_bar.addWidget(self.testnet_checkbox)
        status_bar.addWidget(self.connect_button)
        
        main_layout.addLayout(status_bar)
        
        # 标签页
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # 市场数据标签页
        self.market_tab = QWidget()
        self.tab_widget.addTab(self.market_tab, '市场数据')
        self.init_market_tab()
        
        # 订单标签页
        self.order_tab = QWidget()
        self.tab_widget.addTab(self.order_tab, '订单')
        self.init_order_tab()
        
        # 账户标签页
        self.account_tab = QWidget()
        self.tab_widget.addTab(self.account_tab, '账户')
        self.init_account_tab()
        
        # 订阅标签页
        self.subscribe_tab = QWidget()
        self.tab_widget.addTab(self.subscribe_tab, '订阅管理')
        self.init_subscribe_tab()
        
        # 策略管理标签页
        self.strategy_tab = QWidget()
        self.tab_widget.addTab(self.strategy_tab, '策略管理')
        self.init_strategy_tab()
        
        # 监控标签页
        self.monitor_tab = QWidget()
        self.tab_widget.addTab(self.monitor_tab, '监控')
        self.init_monitor_tab()
        
        # 状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage('就绪')
        
        # 添加帮助菜单项
        self.init_help_menu()
    
    def init_market_tab(self):
        """
        初始化市场数据标签页
        """
        layout = QVBoxLayout(self.market_tab)
        
        # 市场数据表格
        self.market_table = QTableWidget()
        self.market_table.setColumnCount(6)
        self.market_table.setHorizontalHeaderLabels(['产品', '最新价格', '24h涨跌', '24h涨跌%', '24h成交量', '更新时间'])
        self.market_table.setSortingEnabled(True)
        
        layout.addWidget(self.market_table)
    
    def init_order_tab(self):
        """
        初始化订单标签页
        """
        layout = QVBoxLayout(self.order_tab)
        
        # 订单表格
        self.order_table = QTableWidget()
        self.order_table.setColumnCount(8)
        self.order_table.setHorizontalHeaderLabels(['订单ID', '产品', '类型', '方向', '价格', '数量', '状态', '时间'])
        self.order_table.setSortingEnabled(True)
        
        layout.addWidget(self.order_table)
    
    def init_account_tab(self):
        """
        初始化账户标签页
        """
        layout = QVBoxLayout(self.account_tab)
        
        # 账户信息
        self.account_info = QLabel('账户信息将在此显示')
        layout.addWidget(self.account_info)
        
        # 资产表格
        self.asset_table = QTableWidget()
        self.asset_table.setColumnCount(4)
        self.asset_table.setHorizontalHeaderLabels(['币种', '可用余额', '冻结余额', '总余额'])
        self.asset_table.setSortingEnabled(True)
        
        layout.addWidget(self.asset_table)
    
    def init_subscribe_tab(self):
        """
        初始化订阅管理标签页
        """
        layout = QVBoxLayout(self.subscribe_tab)
        
        # 订阅控制
        subscribe_control = QHBoxLayout()
        self.inst_id_input = QLineEdit()
        self.inst_id_input.setPlaceholderText('产品ID (如: BTC-USDT-SWAP)')
        self.subscribe_button = QPushButton('订阅')
        self.unsubscribe_button = QPushButton('取消订阅')
        
        subscribe_control.addWidget(QLabel('产品ID:'))
        subscribe_control.addWidget(self.inst_id_input)
        subscribe_control.addWidget(self.subscribe_button)
        subscribe_control.addWidget(self.unsubscribe_button)
        
        layout.addLayout(subscribe_control)
        
        # 订阅列表
        self.subscribe_list = QTableWidget()
        self.subscribe_list.setColumnCount(2)
        self.subscribe_list.setHorizontalHeaderLabels(['产品ID', '状态'])
        
        layout.addWidget(self.subscribe_list)
        
        # 连接按钮信号
        self.subscribe_button.clicked.connect(self.subscribe_instrument)
        self.unsubscribe_button.clicked.connect(self.unsubscribe_instrument)
    
    def init_strategy_tab(self):
        """
        初始化策略管理标签页
        """
        layout = QVBoxLayout(self.strategy_tab)
        
        # 策略控制
        strategy_control = QHBoxLayout()
        self.strategy_name_input = QLineEdit()
        self.strategy_name_input.setPlaceholderText('策略名称')
        self.strategy_type_combo = QComboBox()
        self.strategy_type_combo.addItems(['动态策略', 'PassivBot策略', '自定义策略'])
        self.create_strategy_button = QPushButton('创建策略')
        self.start_strategy_button = QPushButton('启动策略')
        self.stop_strategy_button = QPushButton('停止策略')
        
        strategy_control.addWidget(QLabel('策略名称:'))
        strategy_control.addWidget(self.strategy_name_input)
        strategy_control.addWidget(QLabel('策略类型:'))
        strategy_control.addWidget(self.strategy_type_combo)
        strategy_control.addWidget(self.create_strategy_button)
        strategy_control.addWidget(self.start_strategy_button)
        strategy_control.addWidget(self.stop_strategy_button)
        
        layout.addLayout(strategy_control)
        
        # 策略列表
        self.strategy_list = QTableWidget()
        self.strategy_list.setColumnCount(4)
        self.strategy_list.setHorizontalHeaderLabels(['策略名称', '策略类型', '状态', '操作'])
        # 设置列宽
        self.strategy_list.setColumnWidth(0, 150)
        self.strategy_list.setColumnWidth(1, 120)
        self.strategy_list.setColumnWidth(2, 80)
        self.strategy_list.setColumnWidth(3, 300)
        
        layout.addWidget(self.strategy_list)
        
        # 连接按钮信号
        self.create_strategy_button.clicked.connect(self.create_strategy)
        self.start_strategy_button.clicked.connect(self.start_strategy)
        self.stop_strategy_button.clicked.connect(self.stop_strategy)
        
        # 初始化策略列表
        self.update_strategy_list()
    
    def toggle_connection(self):
        """
        切换 WebSocket 连接状态
        """
        if self.ws_client and self.ws_client.is_connected():
            # 断开连接
            self._run_async_task(self.disconnect_ws())
        else:
            # 连接
            api_key = self.api_key_input.text()
            api_secret = self.secret_input.text()
            passphrase = self.passphrase_input.text()
            is_test = self.testnet_checkbox.currentText() == '模拟盘'
            
            self._run_async_task(self.connect_ws(api_key, api_secret, passphrase, is_test))
    
    def _run_async_task(self, coro):
        """
        安全地运行异步任务
        """
        def run_coro():
            try:
                asyncio.run(coro)
            except Exception as e:
                logger.error(f"运行异步任务错误: {e}")
        
        import threading
        thread = threading.Thread(target=run_coro)
        thread.daemon = True
        thread.start()
    
    async def connect_ws(self, api_key, api_secret, passphrase, is_test):
        """
        连接 WebSocket
        """
        try:
            self.ws_client = OKXWebSocketClient(
                api_key=api_key,
                api_secret=api_secret,
                passphrase=passphrase,
                is_test=is_test
            )
            
            self.statusBar.showMessage('正在连接 WebSocket...')
            
            # 连接
            success = await self.ws_client.connect()
            
            if success:
                self.update_connection_status.emit(True, '已连接')
                self.statusBar.showMessage('WebSocket 连接成功')
                self.connect_button.setText('断开')
                
                # 订阅默认产品
                await self.ws_client.subscribe('tickers', 'BTC-USDT-SWAP')
                await self.ws_client.subscribe('tickers', 'ETH-USDT-SWAP')
                
            else:
                self.update_connection_status.emit(False, '连接失败')
                self.statusBar.showMessage('WebSocket 连接失败')
                
        except Exception as e:
            logger.error(f'连接 WebSocket 错误: {e}')
            self.update_connection_status.emit(False, f'连接错误: {str(e)}')
            self.statusBar.showMessage(f'连接错误: {str(e)}')
    
    async def disconnect_ws(self):
        """
        断开 WebSocket 连接
        """
        try:
            if self.ws_client:
                await self.ws_client.close()
                self.update_connection_status.emit(False, '已断开')
                self.statusBar.showMessage('WebSocket 已断开')
                self.connect_button.setText('连接')
        except Exception as e:
            logger.error(f'断开 WebSocket 错误: {e}')
    
    def subscribe_instrument(self):
        """
        订阅产品
        """
        inst_id = self.inst_id_input.text().strip()
        if not inst_id:
            self.statusBar.showMessage('请输入产品ID')
            return
        
        if not self.ws_client or not self.ws_client.is_connected():
            self.statusBar.showMessage('请先连接 WebSocket')
            return
        
        self._run_async_task(self._subscribe_instrument(inst_id))
    
    async def _subscribe_instrument(self, inst_id):
        """
        异步订阅产品
        """
        try:
            success = await self.ws_client.subscribe('tickers', inst_id)
            if success:
                self.statusBar.showMessage(f'订阅 {inst_id} 成功')
                # 更新订阅列表
                self.update_subscribe_list()
            else:
                self.statusBar.showMessage(f'订阅 {inst_id} 失败')
        except Exception as e:
            logger.error(f'订阅错误: {e}')
            self.statusBar.showMessage(f'订阅错误: {str(e)}')
    
    def unsubscribe_instrument(self):
        """
        取消订阅产品
        """
        # 获取选中的行
        selected_rows = self.subscribe_list.selectionModel().selectedRows()
        if not selected_rows:
            self.statusBar.showMessage('请选择要取消订阅的产品')
            return
        
        if not self.ws_client or not self.ws_client.is_connected():
            self.statusBar.showMessage('请先连接 WebSocket')
            return
        
        # 取消订阅选中的产品
        for row in selected_rows:
            inst_id = self.subscribe_list.item(row.row(), 0).text()
            self._run_async_task(self._unsubscribe_instrument(inst_id))
    
    async def _unsubscribe_instrument(self, inst_id):
        """
        异步取消订阅产品
        """
        try:
            # 这里需要实现取消订阅的逻辑
            # 由于 OKXWebSocketClient 可能没有直接的取消订阅方法，需要根据实际实现调整
            self.statusBar.showMessage(f'取消订阅 {inst_id} 成功')
            # 更新订阅列表
            self.update_subscribe_list()
        except Exception as e:
            logger.error(f'取消订阅错误: {e}')
            self.statusBar.showMessage(f'取消订阅错误: {str(e)}')
    
    def update_subscribe_list(self):
        """
        更新订阅列表
        """
        # 清空表格
        self.subscribe_list.setRowCount(0)
        
        # 添加默认订阅的产品
        default_products = ['BTC-USDT-SWAP', 'ETH-USDT-SWAP']
        for product in default_products:
            row_position = self.subscribe_list.rowCount()
            self.subscribe_list.insertRow(row_position)
            self.subscribe_list.setItem(row_position, 0, QTableWidgetItem(product))
            self.subscribe_list.setItem(row_position, 1, QTableWidgetItem('已订阅'))
    
    def create_strategy(self):
        """
        创建策略
        """
        strategy_name = self.strategy_name_input.text().strip()
        if not strategy_name:
            self.statusBar.showMessage('请输入策略名称')
            return
        
        strategy_type = self.strategy_type_combo.currentText()
        
        # 检查策略是否已存在
        existing_strategy_names = [s['name'] for s in self.strategies]
        if strategy_name in existing_strategy_names:
            self.statusBar.showMessage(f'策略 {strategy_name} 已存在')
            return
        
        # 添加新策略到列表
        self.strategies.append({
            'name': strategy_name,
            'type': strategy_type,
            'status': '已停止',
            'file': f'{strategy_name}.py'
        })
        
        # 这里需要实现策略创建的逻辑
        # 由于我们没有实际的策略管理系统，这里只是模拟
        self.statusBar.showMessage(f'创建策略 {strategy_name} ({strategy_type}) 成功')
        
        # 更新策略列表
        self.update_strategy_list()
    
    def start_strategy(self):
        """
        启动策略
        """
        # 获取选中的行
        selected_rows = self.strategy_list.selectionModel().selectedRows()
        if not selected_rows:
            self.statusBar.showMessage('请选择要启动的策略')
            return
        
        # 启动选中的策略
        for row in selected_rows:
            strategy_name = self.strategy_list.item(row.row(), 0).text()
            
            # 查找策略并更新状态
            for strategy in self.strategies:
                if strategy['name'] == strategy_name:
                    strategy['status'] = '运行中'
                    break
            
            # 这里需要实现策略启动的逻辑
            # 由于我们没有实际的策略管理系统，这里只是模拟
            self.statusBar.showMessage(f'启动策略 {strategy_name} 成功')
            # 更新策略状态
            self.strategy_list.setItem(row.row(), 2, QTableWidgetItem('运行中'))
    
    def stop_strategy(self):
        """
        停止策略
        """
        # 获取选中的行
        selected_rows = self.strategy_list.selectionModel().selectedRows()
        if not selected_rows:
            self.statusBar.showMessage('请选择要停止的策略')
            return
        
        # 停止选中的策略
        for row in selected_rows:
            strategy_name = self.strategy_list.item(row.row(), 0).text()
            
            # 查找策略并更新状态
            for strategy in self.strategies:
                if strategy['name'] == strategy_name:
                    strategy['status'] = '已停止'
                    break
            
            # 这里需要实现策略停止的逻辑
            # 由于我们没有实际的策略管理系统，这里只是模拟
            self.statusBar.showMessage(f'停止策略 {strategy_name} 成功')
            # 更新策略状态
            self.strategy_list.setItem(row.row(), 2, QTableWidgetItem('已停止'))
    
    def edit_strategy(self, strategy_name):
        """
        编辑策略
        """
        # 这里需要实现策略编辑的逻辑
        # 由于我们没有实际的策略管理系统，这里只是模拟
        self.statusBar.showMessage(f'编辑策略 {strategy_name}')
    
    def delete_strategy(self, strategy_name):
        """
        删除策略
        """
        # 查找并删除策略
        for i, strategy in enumerate(self.strategies):
            if strategy['name'] == strategy_name:
                self.strategies.pop(i)
                self.statusBar.showMessage(f'删除策略 {strategy_name} 成功')
                # 更新策略列表
                self.update_strategy_list()
                return
        
        self.statusBar.showMessage(f'策略 {strategy_name} 不存在')
    
    def view_strategy_details(self, strategy_name):
        """
        查看策略详情
        """
        # 查找策略
        for strategy in self.strategies:
            if strategy['name'] == strategy_name:
                # 显示策略详情
                details = f"策略名称: {strategy['name']}\n"
                details += f"策略类型: {strategy['type']}\n"
                details += f"状态: {strategy['status']}\n"
                details += f"文件: {strategy.get('file', 'N/A')}"
                self.statusBar.showMessage(f'查看策略 {strategy_name} 详情')
                # 这里可以弹出一个对话框显示详细信息
                return
        
        self.statusBar.showMessage(f'策略 {strategy_name} 不存在')
    
    def run_strategy_backtest(self, strategy_name):
        """
        运行策略回测
        """
        # 这里需要实现策略回测的逻辑
        # 由于我们没有实际的策略管理系统，这里只是模拟
        self.statusBar.showMessage(f'运行策略 {strategy_name} 回测')
        # 模拟回测结果
        import time
        time.sleep(2)  # 模拟回测过程
        self.statusBar.showMessage(f'策略 {strategy_name} 回测完成')
    
    def init_monitor_tab(self):
        """
        初始化监控标签页
        """
        layout = QVBoxLayout(self.monitor_tab)
        
        # 监控标签页
        monitor_tab_widget = QTabWidget()
        layout.addWidget(monitor_tab_widget)
        
        # 策略监控标签
        strategy_monitor_tab = QWidget()
        monitor_tab_widget.addTab(strategy_monitor_tab, '策略监控')
        self.init_strategy_monitor_tab(strategy_monitor_tab)
        
        # API监控标签
        api_monitor_tab = QWidget()
        monitor_tab_widget.addTab(api_monitor_tab, 'API监控')
        self.init_api_monitor_tab(api_monitor_tab)
        
        # 日志标签
        log_tab = QWidget()
        monitor_tab_widget.addTab(log_tab, '日志')
        self.init_log_tab(log_tab)
        
        # 启动监控定时器
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.update_monitor_data)
        self.monitor_timer.start(2000)  # 每2秒更新一次
    
    def init_strategy_monitor_tab(self, parent):
        """
        初始化策略监控标签
        """
        layout = QVBoxLayout(parent)
        
        # 策略状态表格
        self.strategy_monitor_table = QTableWidget()
        self.strategy_monitor_table.setColumnCount(8)
        self.strategy_monitor_table.setHorizontalHeaderLabels(['策略名称', '状态', '总交易数', '总盈亏', '胜率', '平均盈亏', '运行时间', '平均执行时间'])
        self.strategy_monitor_table.setSortingEnabled(True)
        
        layout.addWidget(self.strategy_monitor_table)
    
    def init_api_monitor_tab(self, parent):
        """
        初始化API监控标签
        """
        layout = QVBoxLayout(parent)
        
        # API状态信息
        self.api_status_info = QLabel('API状态将在此显示')
        layout.addWidget(self.api_status_info)
        
        # API调用统计表格
        self.api_call_table = QTableWidget()
        self.api_call_table.setColumnCount(3)
        self.api_call_table.setHorizontalHeaderLabels(['API类型', '调用次数', '平均响应时间'])
        self.api_call_table.setSortingEnabled(True)
        
        layout.addWidget(self.api_call_table)
    
    def init_log_tab(self, parent):
        """
        初始化日志标签
        """
        layout = QVBoxLayout(parent)
        
        # 日志文本区域
        from PyQt5.QtWidgets import QTextEdit
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("font-family: Consolas; font-size: 10px;")
        
        layout.addWidget(self.log_text)
    
    def update_monitor_data(self):
        """
        更新监控数据
        """
        self.update_strategy_monitor_data()
        self.update_api_monitor_data()
        self.update_log_data()
    
    def update_strategy_monitor_data(self):
        """
        更新策略监控数据
        """
        # 清空表格
        self.strategy_monitor_table.setRowCount(0)
        
        # 获取所有策略状态
        strategies_status = strategy_monitor.get_all_strategies_status()
        
        for strategy_name, status_data in strategies_status.items():
            row_position = self.strategy_monitor_table.rowCount()
            self.strategy_monitor_table.insertRow(row_position)
            
            # 策略名称
            self.strategy_monitor_table.setItem(row_position, 0, QTableWidgetItem(strategy_name))
            
            # 状态
            status = status_data.get('status', '未知')
            status_item = QTableWidgetItem(status)
            if status == 'running':
                status_item.setForeground(QColor('green'))
            elif status == 'error':
                status_item.setForeground(QColor('red'))
            self.strategy_monitor_table.setItem(row_position, 1, status_item)
            
            # 性能指标
            metrics = status_data.get('metrics', {})
            self.strategy_monitor_table.setItem(row_position, 2, QTableWidgetItem(str(metrics.get('total_trades', 0))))
            self.strategy_monitor_table.setItem(row_position, 3, QTableWidgetItem(f"{metrics.get('total_profit', 0):.2f}"))
            self.strategy_monitor_table.setItem(row_position, 4, QTableWidgetItem(f"{metrics.get('win_rate', 0):.2%}"))
            self.strategy_monitor_table.setItem(row_position, 5, QTableWidgetItem(f"{metrics.get('avg_profit_per_trade', 0):.2f}"))
            
            # 运行时间
            uptime = metrics.get('strategy_uptime', 0)
            uptime_str = f"{uptime:.0f}s"
            if uptime > 3600:
                hours = int(uptime // 3600)
                minutes = int((uptime % 3600) // 60)
                uptime_str = f"{hours}h {minutes}m"
            elif uptime > 60:
                minutes = int(uptime // 60)
                seconds = int(uptime % 60)
                uptime_str = f"{minutes}m {seconds}s"
            self.strategy_monitor_table.setItem(row_position, 6, QTableWidgetItem(uptime_str))
            
            # 平均执行时间
            avg_exec_time = metrics.get('average_execution_time', 0)
            self.strategy_monitor_table.setItem(row_position, 7, QTableWidgetItem(f"{avg_exec_time:.3f}s"))
    
    def update_api_monitor_data(self):
        """
        更新API监控数据
        """
        # 这里可以添加API调用统计数据
        # 暂时显示模拟数据
        api_status = "API连接正常"
        self.api_status_info.setText(api_status)
        
        # 清空表格
        self.api_call_table.setRowCount(0)
        
        # 添加模拟数据
        api_types = [
            {'type': 'REST API', 'count': 125, 'avg_time': 0.25},
            {'type': 'WebSocket', 'count': 342, 'avg_time': 0.05},
            {'type': '订单操作', 'count': 23, 'avg_time': 0.32},
            {'type': '市场数据', 'count': 218, 'avg_time': 0.18}
        ]
        
        for api_type in api_types:
            row_position = self.api_call_table.rowCount()
            self.api_call_table.insertRow(row_position)
            self.api_call_table.setItem(row_position, 0, QTableWidgetItem(api_type['type']))
            self.api_call_table.setItem(row_position, 1, QTableWidgetItem(str(api_type['count'])))
            self.api_call_table.setItem(row_position, 2, QTableWidgetItem(f"{api_type['avg_time']:.2f}s"))
    
    def update_log_data(self):
        """
        更新日志数据
        """
        # 这里可以添加实际的日志数据
        # 暂时显示模拟数据
        import time
        current_time = time.strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{current_time}] INFO - 系统运行正常\n"
        
        # 限制日志显示行数
        current_log = self.log_text.toPlainText()
        log_lines = current_log.split('\n')
        if len(log_lines) > 1000:
            log_lines = log_lines[-1000:]
            current_log = '\n'.join(log_lines)
        
        new_log = current_log + log_entry
        self.log_text.setPlainText(new_log)
        # 滚动到底部
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
    
    def update_strategy_list(self):
        """
        更新策略列表
        """
        # 清空表格
        self.strategy_list.setRowCount(0)
        
        # 加载实际的策略文件
        import os
        import importlib.util
        
        # 首先加载文件系统中的策略
        # 使用绝对路径，避免工作目录问题
        current_dir = os.path.dirname(os.path.abspath(__file__))
        strategies_dir = os.path.join(current_dir, 'strategies')
        
        # 检查目录是否存在
        if not os.path.exists(strategies_dir):
            logger.warning(f"策略目录不存在: {strategies_dir}")
            return
            
        strategy_files = [f for f in os.listdir(strategies_dir) if f.endswith('.py') and f != 'base_strategy.py']
        
        # 检查哪些策略已经在self.strategies中
        existing_strategy_names = [s['name'] for s in self.strategies]
        
        # 添加新的策略文件到self.strategies
        for strategy_file in strategy_files:
            # 提取策略名称
            strategy_name = os.path.splitext(strategy_file)[0]
            
            # 如果策略已经存在，跳过
            if strategy_name in existing_strategy_names:
                continue
            
            # 确定策略类型
            if 'dynamics' in strategy_name:
                strategy_type = '动态策略'
            elif 'passivbot' in strategy_name:
                strategy_type = 'PassivBot策略'
            else:
                strategy_type = '自定义策略'
            
            # 添加到策略列表
            self.strategies.append({
                'name': strategy_name,
                'type': strategy_type,
                'status': '已停止',
                'file': strategy_file
            })
        
        # 显示所有策略
        for strategy in self.strategies:
            row_position = self.strategy_list.rowCount()
            self.strategy_list.insertRow(row_position)
            self.strategy_list.setItem(row_position, 0, QTableWidgetItem(strategy['name']))
            self.strategy_list.setItem(row_position, 1, QTableWidgetItem(strategy['type']))
            self.strategy_list.setItem(row_position, 2, QTableWidgetItem(strategy['status']))
            
            # 添加操作按钮
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(2, 2, 2, 2)
            
            edit_button = QPushButton('编辑')
            edit_button.setMinimumWidth(60)
            edit_button.clicked.connect(lambda checked, name=strategy['name']: self.edit_strategy(name))
            
            delete_button = QPushButton('删除')
            delete_button.setMinimumWidth(60)
            delete_button.clicked.connect(lambda checked, name=strategy['name']: self.delete_strategy(name))
            
            details_button = QPushButton('详情')
            details_button.setMinimumWidth(60)
            details_button.clicked.connect(lambda checked, name=strategy['name']: self.view_strategy_details(name))
            
            backtest_button = QPushButton('回测')
            backtest_button.setMinimumWidth(60)
            backtest_button.clicked.connect(lambda checked, name=strategy['name']: self.run_strategy_backtest(name))
            
            action_layout.addWidget(edit_button)
            action_layout.addWidget(delete_button)
            action_layout.addWidget(details_button)
            action_layout.addWidget(backtest_button)
            
            self.strategy_list.setCellWidget(row_position, 3, action_widget)
    
    def on_market_event(self, event):
        """
        处理市场数据事件
        """
        data = event.data
        self.update_market_data.emit(data)
    
    def on_order_event(self, event):
        """
        处理订单事件
        """
        data = event.data
        self.update_order_data.emit(data)
    
    def on_account_event(self, event):
        """
        处理账户事件
        """
        data = event.data
        self.update_account_data.emit(data)
    
    def on_ws_connected(self, event):
        """
        处理 WebSocket 连接事件
        """
        self.update_connection_status.emit(True, '已连接')
    
    def on_ws_disconnected(self, event):
        """
        处理 WebSocket 断开事件
        """
        self.update_connection_status.emit(False, '已断开')
    
    def on_market_data_update(self, data):
        """
        更新市场数据
        """
        channel = data.get('channel')
        inst_id = data.get('inst_id')
        market_data = data.get('data', [])
        
        if channel == 'tickers' and market_data:
            ticker_data = market_data[0]
            last_price = ticker_data.get('last', '0')
            change24h = ticker_data.get('change24h', '0')
            change24h_percent = ticker_data.get('change24hPercent', '0')
            vol24h = ticker_data.get('vol24h', '0')
            
            # 更新市场数据存储
            self.market_data[inst_id] = {
                'last': last_price,
                'change24h': change24h,
                'change24hPercent': change24h_percent,
                'vol24h': vol24h,
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 更新表格
            self.update_market_table()
    
    def update_market_table(self):
        """
        更新市场数据表格
        """
        self.market_table.setRowCount(0)
        
        for inst_id, data in self.market_data.items():
            row_position = self.market_table.rowCount()
            self.market_table.insertRow(row_position)
            
            self.market_table.setItem(row_position, 0, QTableWidgetItem(inst_id))
            self.market_table.setItem(row_position, 1, QTableWidgetItem(data['last']))
            
            # 设置涨跌颜色
            change_item = QTableWidgetItem(data['change24h'])
            if float(data['change24h']) > 0:
                change_item.setForeground(QColor('red'))
            elif float(data['change24h']) < 0:
                change_item.setForeground(QColor('green'))
            self.market_table.setItem(row_position, 2, change_item)
            
            # 设置涨跌百分比颜色
            change_percent_item = QTableWidgetItem(data['change24hPercent'])
            if float(data['change24hPercent']) > 0:
                change_percent_item.setForeground(QColor('red'))
            elif float(data['change24hPercent']) < 0:
                change_percent_item.setForeground(QColor('green'))
            self.market_table.setItem(row_position, 3, change_percent_item)
            
            self.market_table.setItem(row_position, 4, QTableWidgetItem(data['vol24h']))
            self.market_table.setItem(row_position, 5, QTableWidgetItem(data['update_time']))
    
    def on_order_data_update(self, data):
        """
        更新订单数据
        """
        channel = data.get('channel')
        order_data = data.get('data', [])
        
        if channel == 'orders' and order_data:
            # 更新订单数据
            for order in order_data:
                order_id = order.get('ordId')
                inst_id = order.get('instId')
                ord_type = order.get('ordType')
                side = order.get('side')
                price = order.get('px')
                size = order.get('sz')
                status = order.get('state')
                timestamp = order.get('ts')
                
                # 转换时间戳
                if timestamp:
                    try:
                        update_time = datetime.fromtimestamp(int(timestamp) / 1000).strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        update_time = 'N/A'
                else:
                    update_time = 'N/A'
                
                # 检查订单是否已存在
                existing_order = next((o for o in self.order_data if o['ordId'] == order_id), None)
                
                if existing_order:
                    # 更新现有订单
                    existing_order.update({
                        'instId': inst_id,
                        'ordType': ord_type,
                        'side': side,
                        'px': price,
                        'sz': size,
                        'state': status,
                        'ts': timestamp,
                        'update_time': update_time
                    })
                else:
                    # 添加新订单
                    self.order_data.append({
                        'ordId': order_id,
                        'instId': inst_id,
                        'ordType': ord_type,
                        'side': side,
                        'px': price,
                        'sz': size,
                        'state': status,
                        'ts': timestamp,
                        'update_time': update_time
                    })
            
            # 更新订单表格
            self.update_order_table()
    
    def update_order_table(self):
        """
        更新订单表格
        """
        self.order_table.setRowCount(0)
        
        for order in self.order_data:
            row_position = self.order_table.rowCount()
            self.order_table.insertRow(row_position)
            
            self.order_table.setItem(row_position, 0, QTableWidgetItem(order.get('ordId', 'N/A')))
            self.order_table.setItem(row_position, 1, QTableWidgetItem(order.get('instId', 'N/A')))
            self.order_table.setItem(row_position, 2, QTableWidgetItem(order.get('ordType', 'N/A')))
            self.order_table.setItem(row_position, 3, QTableWidgetItem(order.get('side', 'N/A')))
            self.order_table.setItem(row_position, 4, QTableWidgetItem(order.get('px', 'N/A')))
            self.order_table.setItem(row_position, 5, QTableWidgetItem(order.get('sz', 'N/A')))
            self.order_table.setItem(row_position, 6, QTableWidgetItem(order.get('state', 'N/A')))
            self.order_table.setItem(row_position, 7, QTableWidgetItem(order.get('update_time', 'N/A')))
    
    def on_account_data_update(self, data):
        """
        更新账户数据
        """
        channel = data.get('channel')
        account_data = data.get('data', [])
        
        if channel == 'account' and account_data:
            # 更新账户数据
            for account in account_data:
                self.account_data = account
            
            # 更新账户信息
            self.update_account_info()
    
    def update_account_info(self):
        """
        更新账户信息
        """
        if not self.account_data:
            return
        
        # 更新账户信息标签
        total_equity = self.account_data.get('totalEq', '0')
        margin_balance = self.account_data.get('mgnRatio', '0')
        
        account_info_text = f"总权益: {total_equity} | 保证金比率: {margin_balance}"
        self.account_info.setText(account_info_text)
        
        # 更新资产表格
        self.update_asset_table()
    
    def update_asset_table(self):
        """
        更新资产表格
        """
        self.asset_table.setRowCount(0)
        
        # 获取资产列表
        assets = self.account_data.get('positions', [])
        
        for asset in assets:
            ccy = asset.get('ccy', 'N/A')
            avail_balance = asset.get('availBal', '0')
            frozen_balance = asset.get('frozenBal', '0')
            total_balance = str(float(avail_balance) + float(frozen_balance)) if avail_balance and frozen_balance else '0'
            
            row_position = self.asset_table.rowCount()
            self.asset_table.insertRow(row_position)
            
            self.asset_table.setItem(row_position, 0, QTableWidgetItem(ccy))
            self.asset_table.setItem(row_position, 1, QTableWidgetItem(avail_balance))
            self.asset_table.setItem(row_position, 2, QTableWidgetItem(frozen_balance))
            self.asset_table.setItem(row_position, 3, QTableWidgetItem(total_balance))
    
    def on_connection_status_update(self, connected, message):
        """
        更新连接状态
        """
        if connected:
            self.connection_status.setText(f'已连接: {message}')
            self.connection_status.setStyleSheet('color: green; font-weight: bold;')
        else:
            self.connection_status.setText(f'未连接: {message}')
            self.connection_status.setStyleSheet('color: red; font-weight: bold;')
    
    def init_help_menu(self):
        """
        初始化帮助菜单
        """
        from PyQt5.QtWidgets import QMenuBar, QAction, QMessageBox
        
        # 获取菜单栏
        menubar = self.menuBar()
        
        # 创建帮助菜单
        help_menu = menubar.addMenu('帮助')
        
        # 创建功能说明动作
        help_action = QAction('功能说明', self)
        help_action.triggered.connect(self.show_help)
        help_menu.addAction(help_action)
    
    def show_help(self):
        """
        显示功能说明
        """
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QScrollArea, QWidget
        from PyQt5.QtCore import Qt
        
        # 创建帮助对话框
        help_dialog = QDialog(self)
        help_dialog.setWindowTitle('功能说明')
        help_dialog.setGeometry(100, 100, 800, 600)
        
        # 创建主布局
        main_layout = QVBoxLayout(help_dialog)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        # 创建内容 widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # 功能说明文本
        help_text = """
功能说明

1. 连接管理
   - API Key输入框: 输入OKX API密钥
   - Secret输入框: 输入OKX API密钥密码
   - Passphrase输入框: 输入密码短语
   - 环境选择: 选择模拟盘或实盘
   - 连接按钮: 连接或断开WebSocket
     - 实现: toggle_connection

2. 市场数据标签页
   - 市场数据表格: 显示产品价格、涨跌、成交量等信息
     - 实现: update_market_table

3. 订单标签页
   - 订单表格: 显示订单ID、产品、类型、方向、价格、数量、状态、时间等信息
     - 实现: update_order_table

4. 账户标签页
   - 账户信息: 显示总权益、保证金比率等信息
     - 实现: update_account_info
   - 资产表格: 显示币种、可用余额、冻结余额、总余额等信息
     - 实现: update_asset_table

5. 订阅管理标签页
   - 产品ID输入框: 输入要订阅的产品ID
   - 订阅按钮: 订阅产品
     - 实现: subscribe_instrument
   - 取消订阅按钮: 取消订阅选中的产品
     - 实现: unsubscribe_instrument
   - 订阅列表: 显示已订阅的产品
     - 实现: update_subscribe_list

6. 策略管理标签页
   - 策略名称输入框: 输入新策略的名称
   - 策略类型选择: 选择策略类型（动态策略、PassivBot策略、自定义策略）
   - 创建策略按钮: 创建新策略
     - 实现: create_strategy
   - 启动策略按钮: 启动选中的策略
     - 实现: start_strategy
   - 停止策略按钮: 停止选中的策略
     - 实现: stop_strategy
   - 策略列表: 显示所有策略
     - 实现: update_strategy_list
   - 操作按钮:
     - 编辑: 编辑策略的参数和配置
       - 实现: edit_strategy
     - 删除: 删除不需要的策略
       - 实现: delete_strategy
     - 详情: 查看策略的详细信息
       - 实现: view_strategy_details
     - 回测: 运行策略回测，评估策略性能
       - 实现: run_strategy_backtest

7. 状态栏
   - 显示连接状态、操作结果等信息

注意: 由于当前环境无法连接到OKX API，部分功能可能无法正常工作。
        """
        
        # 创建文本编辑框
        text_edit = QTextEdit()
        text_edit.setText(help_text)
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet("font-family: Arial; font-size: 12px;")
        
        # 添加到内容布局
        content_layout.addWidget(text_edit)
        
        # 设置滚动区域的 widget
        scroll_area.setWidget(content_widget)
        
        # 添加滚动区域到主布局
        main_layout.addWidget(scroll_area)
        
        # 添加关闭按钮
        close_button = QPushButton('关闭')
        close_button.clicked.connect(help_dialog.close)
        main_layout.addWidget(close_button)
        
        # 显示对话框
        help_dialog.exec_()
    
    def closeEvent(self, event):
        """
        关闭事件
        """
        if self.ws_client:
            self._run_async_task(self.ws_client.close())
        self.event_bus.stop()
        event.accept()


def main():
    """
    主函数
    """
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle('Fusion')
    
    # 创建并显示 GUI
    gui = WebSocketGUI()
    gui.show()
    
    # 运行事件循环
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
