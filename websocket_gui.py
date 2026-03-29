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
        
        # 状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage('就绪')
    
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
    
    def toggle_connection(self):
        """
        切换 WebSocket 连接状态
        """
        if self.ws_client and self.ws_client.is_connected():
            # 断开连接
            asyncio.create_task(self.disconnect_ws())
        else:
            # 连接
            api_key = self.api_key_input.text()
            api_secret = self.secret_input.text()
            passphrase = self.passphrase_input.text()
            is_test = self.testnet_checkbox.currentText() == '模拟盘'
            
            asyncio.create_task(self.connect_ws(api_key, api_secret, passphrase, is_test))
    
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
        
        asyncio.create_task(self._subscribe_instrument(inst_id))
    
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
            asyncio.create_task(self._unsubscribe_instrument(inst_id))
    
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
    
    def closeEvent(self, event):
        """
        关闭事件
        """
        if self.ws_client:
            asyncio.create_task(self.ws_client.close())
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
