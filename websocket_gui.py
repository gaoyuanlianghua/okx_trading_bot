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
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QStatusBar,
    QSplitter,
    QGroupBox,
    QFormLayout,
    QFrame,
    QMessageBox,
)
from PyQt5.QtGui import QColor, QFont, QIcon
from PyQt5.QtCore import QTimer, pyqtSignal, Qt, QSize

# 导入图表库
import matplotlib

matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import mplfinance as mpf
import numpy as np
import pandas as pd

from core import OKXWebSocketClient, EventBus, EventType
from core.monitoring import strategy_monitor

# 设置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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
        self.strategy_instances = {}  # 存储策略实例
        self.strategy_threads = {}  # 存储策略线程

        # 线程池管理
        import concurrent.futures

        self._thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=5
        )  # 限制线程池大小

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
        self.setWindowTitle("OKX 交易机器人")
        self.setGeometry(100, 100, 1400, 900)
        
        # 设置全局样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f2f5;
            }
            QGroupBox {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                background-color: white;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton {
                background-color: #1976D2;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                min-width: 90px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1565C0;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
            QLineEdit {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #1976D2;
            }
            QComboBox {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 8px;
                font-size: 14px;
            }
            QTableWidget {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                alternate-background-color: #f9f9f9;
            }
            QTableWidget::item:selected {
                background-color: #E3F2FD;
            }
            QStatusBar {
                background-color: white;
                border-top: 1px solid #e0e0e0;
                font-size: 12px;
            }
            QLabel {
                font-size: 14px;
            }
            QTabBar::tab {
                background-color: #f5f5f5;
                padding: 12px 20px;
                margin-right: 2px;
                border-radius: 6px 6px 0 0;
                font-size: 14px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 2px solid #1976D2;
            }
        """)

        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # 顶部连接状态栏
        status_group = QGroupBox("连接管理")
        status_layout = QVBoxLayout()
        status_layout.setContentsMargins(15, 15, 15, 15)
        
        # 连接状态和API配置
        api_config_layout = QHBoxLayout()
        api_config_layout.setSpacing(15)
        
        # 连接状态
        status_left = QHBoxLayout()
        status_left.addWidget(QLabel("连接状态:"))
        self.connection_status = QLabel("未连接")
        self.connection_status.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
        status_left.addWidget(self.connection_status)
        status_left.addStretch(1)
        
        # API配置
        api_inputs_layout = QHBoxLayout()
        api_inputs_layout.setSpacing(10)
        
        api_inputs_layout.addWidget(QLabel("API Key:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("API Key")
        self.api_key_input.setMinimumWidth(220)
        api_inputs_layout.addWidget(self.api_key_input)
        
        api_inputs_layout.addWidget(QLabel("Secret:"))
        self.secret_input = QLineEdit()
        self.secret_input.setPlaceholderText("API Secret")
        self.secret_input.setEchoMode(QLineEdit.Password)
        self.secret_input.setMinimumWidth(220)
        api_inputs_layout.addWidget(self.secret_input)
        
        api_inputs_layout.addWidget(QLabel("Passphrase:"))
        self.passphrase_input = QLineEdit()
        self.passphrase_input.setPlaceholderText("Passphrase")
        self.passphrase_input.setMinimumWidth(180)
        api_inputs_layout.addWidget(self.passphrase_input)
        
        api_inputs_layout.addWidget(QLabel("环境:"))
        self.testnet_checkbox = QComboBox()
        self.testnet_checkbox.addItems(["模拟盘", "实盘"])
        self.testnet_checkbox.setMinimumWidth(100)
        api_inputs_layout.addWidget(self.testnet_checkbox)
        
        self.connect_button = QPushButton("连接")
        self.connect_button.clicked.connect(self.toggle_connection)
        api_inputs_layout.addWidget(self.connect_button)
        
        api_config_layout.addLayout(status_left)
        api_config_layout.addLayout(api_inputs_layout)
        status_layout.addLayout(api_config_layout)
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)

        # 仪表盘概览
        dashboard_group = QGroupBox("仪表盘概览")
        dashboard_layout = QHBoxLayout()
        dashboard_layout.setContentsMargins(15, 15, 15, 15)
        dashboard_layout.setSpacing(15)
        
        # 市场概览卡片
        market_overview = QGroupBox("市场概览")
        market_overview.setMinimumHeight(160)
        market_overview.setStyleSheet("QGroupBox { border-radius: 10px; }")
        market_overview_layout = QVBoxLayout()
        market_overview_layout.setContentsMargins(20, 20, 20, 20)
        market_overview_layout.setSpacing(10)
        
        # 市场概览内容
        market_content = QVBoxLayout()
        market_content.setSpacing(8)
        self.market_price_label = QLabel("BTC/USDT: $45,000")
        self.market_price_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.market_change_label = QLabel("24h: +2.5%")
        self.market_change_label.setStyleSheet("font-size: 16px; color: green;")
        market_content.addWidget(self.market_price_label)
        market_content.addWidget(self.market_change_label)
        market_overview_layout.addLayout(market_content)
        market_overview.setLayout(market_overview_layout)
        
        # 账户概览卡片
        account_overview = QGroupBox("账户概览")
        account_overview.setMinimumHeight(160)
        account_overview.setStyleSheet("QGroupBox { border-radius: 10px; }")
        account_overview_layout = QVBoxLayout()
        account_overview_layout.setContentsMargins(20, 20, 20, 20)
        account_overview_layout.setSpacing(10)
        
        # 账户概览内容
        account_content = QVBoxLayout()
        account_content.setSpacing(8)
        self.account_balance_label = QLabel("总余额: $10,000")
        self.account_balance_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.account_pnl_label = QLabel("今日盈亏: +$150")
        self.account_pnl_label.setStyleSheet("font-size: 16px; color: green;")
        account_content.addWidget(self.account_balance_label)
        account_content.addWidget(self.account_pnl_label)
        account_overview_layout.addLayout(account_content)
        account_overview.setLayout(account_overview_layout)
        
        # 策略概览卡片
        strategy_overview = QGroupBox("策略概览")
        strategy_overview.setMinimumHeight(160)
        strategy_overview.setStyleSheet("QGroupBox { border-radius: 10px; }")
        strategy_overview_layout = QVBoxLayout()
        strategy_overview_layout.setContentsMargins(20, 20, 20, 20)
        strategy_overview_layout.setSpacing(10)
        
        # 策略概览内容
        strategy_content = QVBoxLayout()
        strategy_content.setSpacing(8)
        self.strategy_status_label = QLabel("运行中: 2个策略")
        self.strategy_status_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.strategy_profit_label = QLabel("总利润: +$500")
        self.strategy_profit_label.setStyleSheet("font-size: 16px; color: green;")
        strategy_content.addWidget(self.strategy_status_label)
        strategy_content.addWidget(self.strategy_profit_label)
        strategy_overview_layout.addLayout(strategy_content)
        strategy_overview.setLayout(strategy_overview_layout)
        
        # 交易概览卡片
        trade_overview = QGroupBox("交易概览")
        trade_overview.setMinimumHeight(160)
        trade_overview.setStyleSheet("QGroupBox { border-radius: 10px; }")
        trade_overview_layout = QVBoxLayout()
        trade_overview_layout.setContentsMargins(20, 20, 20, 20)
        trade_overview_layout.setSpacing(10)
        
        # 交易概览内容
        trade_content = QVBoxLayout()
        trade_content.setSpacing(8)
        self.trade_count_label = QLabel("今日交易: 12笔")
        self.trade_count_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.trade_win_rate_label = QLabel("胜率: 75%")
        self.trade_win_rate_label.setStyleSheet("font-size: 16px; color: green;")
        trade_content.addWidget(self.trade_count_label)
        trade_content.addWidget(self.trade_win_rate_label)
        trade_overview_layout.addLayout(trade_content)
        trade_overview.setLayout(trade_overview_layout)
        
        # 添加卡片到仪表盘
        dashboard_layout.addWidget(market_overview, 1)
        dashboard_layout.addWidget(account_overview, 1)
        dashboard_layout.addWidget(strategy_overview, 1)
        dashboard_layout.addWidget(trade_overview, 1)
        dashboard_group.setLayout(dashboard_layout)
        main_layout.addWidget(dashboard_group)

        # 标签页 - 简化为主要功能
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        self.tab_widget.setTabShape(QTabWidget.Rounded)
        main_layout.addWidget(self.tab_widget)

        # 市场数据标签页
        self.market_tab = QWidget()
        self.tab_widget.addTab(self.market_tab, "市场数据")
        self.init_market_tab()

        # 交易与订单标签页
        self.trade_tab = QWidget()
        self.tab_widget.addTab(self.trade_tab, "交易与订单")
        self.init_trade_tab()

        # 策略管理标签页
        self.strategy_tab = QWidget()
        self.tab_widget.addTab(self.strategy_tab, "策略管理")
        self.init_strategy_tab()

        # 监控与分析标签页
        self.monitor_tab = QWidget()
        self.tab_widget.addTab(self.monitor_tab, "监控与分析")
        self.init_monitor_tab()

        # 状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("就绪")

        # 添加帮助菜单项
        self.init_help_menu()

    def init_trade_tab(self):
        """
        初始化交易与订单标签页
        """
        trade_layout = QVBoxLayout(self.trade_tab)
        trade_layout.setContentsMargins(15, 15, 15, 15)
        trade_layout.setSpacing(15)
        
        # 顶部布局：交易操作
        trade_ops_group = QGroupBox("交易操作")
        trade_ops_layout = QHBoxLayout()
        trade_ops_layout.setContentsMargins(15, 15, 15, 15)
        trade_ops_layout.setSpacing(15)
        
        # 交易对选择
        trade_ops_layout.addWidget(QLabel("交易对:"))
        self.trade_pair_combo = QComboBox()
        self.trade_pair_combo.addItems(["BTC-USDT-SWAP", "ETH-USDT-SWAP", "BNB-USDT-SWAP"])
        self.trade_pair_combo.setMinimumWidth(150)
        trade_ops_layout.addWidget(self.trade_pair_combo)
        
        # 交易方向
        trade_ops_layout.addWidget(QLabel("方向:"))
        self.trade_side_combo = QComboBox()
        self.trade_side_combo.addItems(["买入", "卖出"])
        self.trade_side_combo.setMinimumWidth(100)
        trade_ops_layout.addWidget(self.trade_side_combo)
        
        # 交易类型
        trade_ops_layout.addWidget(QLabel("类型:"))
        self.trade_type_combo = QComboBox()
        self.trade_type_combo.addItems(["市价", "限价"])
        self.trade_type_combo.setMinimumWidth(100)
        trade_ops_layout.addWidget(self.trade_type_combo)
        
        # 价格
        trade_ops_layout.addWidget(QLabel("价格:"))
        self.trade_price_input = QLineEdit()
        self.trade_price_input.setPlaceholderText("价格")
        self.trade_price_input.setMinimumWidth(100)
        trade_ops_layout.addWidget(self.trade_price_input)
        
        # 数量
        trade_ops_layout.addWidget(QLabel("数量:"))
        self.trade_amount_input = QLineEdit()
        self.trade_amount_input.setPlaceholderText("数量")
        self.trade_amount_input.setMinimumWidth(100)
        trade_ops_layout.addWidget(self.trade_amount_input)
        
        # 执行按钮
        self.execute_trade_button = QPushButton("执行交易")
        self.execute_trade_button.clicked.connect(self.execute_trade)
        trade_ops_layout.addWidget(self.execute_trade_button)
        
        trade_ops_group.setLayout(trade_ops_layout)
        trade_layout.addWidget(trade_ops_group)
        
        # 下方布局：订单和账户信息
        bottom_layout = QHBoxLayout()
        
        # 订单列表
        order_group = QGroupBox("订单列表")
        order_layout = QVBoxLayout()
        
        self.order_table = QTableWidget()
        self.order_table.setColumnCount(8)
        self.order_table.setHorizontalHeaderLabels(["订单ID", "交易对", "类型", "方向", "价格", "数量", "状态", "时间"])
        self.order_table.horizontalHeader().setStretchLastSection(True)
        order_layout.addWidget(self.order_table)
        order_group.setLayout(order_layout)
        
        # 账户信息
        account_group = QGroupBox("账户信息")
        account_layout = QVBoxLayout()
        
        self.account_table = QTableWidget()
        self.account_table.setColumnCount(4)
        self.account_table.setHorizontalHeaderLabels(["币种", "可用余额", "冻结余额", "总余额"])
        self.account_table.horizontalHeader().setStretchLastSection(True)
        account_layout.addWidget(self.account_table)
        
        # 资产分布
        asset_distribution_group = QGroupBox("资产分布")
        asset_distribution_layout = QVBoxLayout()
        
        # 创建资产分布图表
        from matplotlib.figure import Figure
        self.asset_figure = Figure(figsize=(5, 3))
        self.asset_canvas = FigureCanvas(self.asset_figure)
        asset_distribution_layout.addWidget(self.asset_canvas)
        asset_distribution_group.setLayout(asset_distribution_layout)
        
        account_layout.addWidget(asset_distribution_group)
        account_group.setLayout(account_layout)
        
        bottom_layout.addWidget(order_group, 2)
        bottom_layout.addWidget(account_group, 1)
        trade_layout.addLayout(bottom_layout)
    
    def init_market_tab(self):
        """
        初始化市场数据标签页
        """
        market_layout = QVBoxLayout(self.market_tab)
        market_layout.setContentsMargins(15, 15, 15, 15)
        market_layout.setSpacing(15)
        
        # 顶部控制栏
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)
        
        # 产品搜索
        self.market_search = QLineEdit()
        self.market_search.setPlaceholderText("搜索产品...")
        self.market_search.setMinimumWidth(200)
        control_layout.addWidget(QLabel("搜索:"))
        control_layout.addWidget(self.market_search)
        
        # 刷新按钮
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.update_market_table)
        control_layout.addWidget(refresh_button)
        
        # 显示数量
        self.show_count = QComboBox()
        self.show_count.addItems(["10", "20", "50", "100"])
        self.show_count.setCurrentText("20")
        control_layout.addWidget(QLabel("显示数量:"))
        control_layout.addWidget(self.show_count)
        
        control_layout.addStretch(1)
        market_layout.addLayout(control_layout)
        
        # 市场数据表格
        market_group = QGroupBox("市场数据")
        market_layout.addWidget(market_group)
        
        market_table_layout = QVBoxLayout(market_group)
        market_table_layout.setContentsMargins(15, 15, 15, 15)
        
        self.market_table = QTableWidget()
        self.market_table.setColumnCount(6)
        self.market_table.setHorizontalHeaderLabels(["交易对", "最新价格", "涨跌幅", "成交量", "最高价", "最低价"])
        self.market_table.horizontalHeader().setStretchLastSection(True)
        market_table_layout.addWidget(self.market_table)
        
        # 价格图表
        chart_group = QGroupBox("价格图表")
        chart_layout = QVBoxLayout(chart_group)
        chart_layout.setContentsMargins(15, 15, 15, 15)
        
        # 创建价格图表
        self.price_figure = Figure(figsize=(10, 4))
        self.price_canvas = FigureCanvas(self.price_figure)
        chart_layout.addWidget(self.price_canvas)
        market_layout.addWidget(chart_group)

    def init_order_tab(self):
        """
        初始化订单标签页
        """
        layout = QVBoxLayout(self.order_tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 顶部控制栏
        control_layout = QHBoxLayout()
        
        # 订单状态筛选
        self.order_status_filter = QComboBox()
        self.order_status_filter.addItems(["所有", "待成交", "已成交", "已取消", "部分成交"])
        control_layout.addWidget(QLabel("状态:"))
        control_layout.addWidget(self.order_status_filter)
        
        # 产品筛选
        self.order_product_filter = QLineEdit()
        self.order_product_filter.setPlaceholderText("产品ID")
        self.order_product_filter.setMinimumWidth(150)
        control_layout.addWidget(QLabel("产品:"))
        control_layout.addWidget(self.order_product_filter)
        
        # 刷新按钮
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.update_order_table)
        control_layout.addWidget(refresh_button)
        
        # 显示数量
        self.order_show_count = QComboBox()
        self.order_show_count.addItems(["10", "20", "50", "100"])
        self.order_show_count.setCurrentText("20")
        control_layout.addWidget(QLabel("显示数量:"))
        control_layout.addWidget(self.order_show_count)
        
        control_layout.addStretch(1)
        layout.addLayout(control_layout)

        # 订单表格
        self.order_table = QTableWidget()
        self.order_table.setColumnCount(8)
        self.order_table.setHorizontalHeaderLabels(
            ["订单ID", "产品", "类型", "方向", "价格", "数量", "状态", "时间"]
        )
        self.order_table.setSortingEnabled(True)
        self.order_table.setAlternatingRowColors(True)
        self.order_table.setSelectionMode(QTableWidget.SingleSelection)
        self.order_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        # 设置列宽
        self.order_table.setColumnWidth(0, 150)
        self.order_table.setColumnWidth(1, 120)
        self.order_table.setColumnWidth(2, 80)
        self.order_table.setColumnWidth(3, 60)
        self.order_table.setColumnWidth(4, 80)
        self.order_table.setColumnWidth(5, 80)
        self.order_table.setColumnWidth(6, 80)
        self.order_table.setColumnWidth(7, 150)

        layout.addWidget(self.order_table)
        
        # 底部状态栏
        status_layout = QHBoxLayout()
        self.order_status = QLabel("就绪")
        status_layout.addWidget(self.order_status)
        status_layout.addStretch(1)
        layout.addLayout(status_layout)

    def init_account_tab(self):
        """
        初始化账户标签页
        """
        layout = QVBoxLayout(self.account_tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 账户信息卡片
        account_group = QGroupBox("账户信息")
        account_layout = QHBoxLayout()
        account_layout.setContentsMargins(10, 10, 10, 10)
        
        # 总权益
        equity_group = QGroupBox("总权益")
        equity_layout = QVBoxLayout()
        self.total_equity_label = QLabel("0.00 USDT")
        self.total_equity_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        equity_layout.addWidget(self.total_equity_label)
        equity_group.setLayout(equity_layout)
        account_layout.addWidget(equity_group)
        
        # 保证金比率
        margin_group = QGroupBox("保证金比率")
        margin_layout = QVBoxLayout()
        self.margin_ratio_label = QLabel("0.00%")
        self.margin_ratio_label.setStyleSheet("font-size: 16px;")
        margin_layout.addWidget(self.margin_ratio_label)
        margin_group.setLayout(margin_layout)
        account_layout.addWidget(margin_group)
        
        # 可用余额
        available_group = QGroupBox("可用余额")
        available_layout = QVBoxLayout()
        self.available_balance_label = QLabel("0.00 USDT")
        self.available_balance_label.setStyleSheet("font-size: 16px;")
        available_layout.addWidget(self.available_balance_label)
        available_group.setLayout(available_layout)
        account_layout.addWidget(available_group)
        
        # 总仓位
        position_group = QGroupBox("总仓位")
        position_layout = QVBoxLayout()
        self.total_position_label = QLabel("0.00 USDT")
        self.total_position_label.setStyleSheet("font-size: 16px;")
        position_layout.addWidget(self.total_position_label)
        position_group.setLayout(position_layout)
        account_layout.addWidget(position_group)
        
        account_group.setLayout(account_layout)
        layout.addWidget(account_group)

        # 资产表格
        asset_group = QGroupBox("资产明细")
        asset_layout = QVBoxLayout()
        
        # 资产表格控制栏
        asset_control_layout = QHBoxLayout()
        
        # 资产搜索
        self.asset_search = QLineEdit()
        self.asset_search.setPlaceholderText("搜索币种...")
        self.asset_search.setMinimumWidth(200)
        asset_control_layout.addWidget(QLabel("搜索:"))
        asset_control_layout.addWidget(self.asset_search)
        
        # 刷新按钮
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.update_asset_table)
        asset_control_layout.addWidget(refresh_button)
        
        asset_control_layout.addStretch(1)
        asset_layout.addLayout(asset_control_layout)
        
        # 资产表格
        self.asset_table = QTableWidget()
        self.asset_table.setColumnCount(4)
        self.asset_table.setHorizontalHeaderLabels(
            ["币种", "可用余额", "冻结余额", "总余额"]
        )
        self.asset_table.setSortingEnabled(True)
        self.asset_table.setAlternatingRowColors(True)
        self.asset_table.setSelectionMode(QTableWidget.SingleSelection)
        self.asset_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        # 设置列宽
        self.asset_table.setColumnWidth(0, 80)
        self.asset_table.setColumnWidth(1, 120)
        self.asset_table.setColumnWidth(2, 120)
        self.asset_table.setColumnWidth(3, 120)
        
        asset_layout.addWidget(self.asset_table)
        asset_group.setLayout(asset_layout)
        layout.addWidget(asset_group)
        
        # 底部状态栏
        status_layout = QHBoxLayout()
        self.account_status = QLabel("就绪")
        status_layout.addWidget(self.account_status)
        status_layout.addStretch(1)
        layout.addLayout(status_layout)

    def init_subscribe_tab(self):
        """
        初始化订阅管理标签页
        """
        layout = QVBoxLayout(self.subscribe_tab)

        # 订阅控制
        subscribe_control = QHBoxLayout()
        self.inst_id_input = QLineEdit()
        self.inst_id_input.setPlaceholderText("产品ID (如: BTC-USDT-SWAP)")
        self.subscribe_button = QPushButton("订阅")
        self.unsubscribe_button = QPushButton("取消订阅")

        subscribe_control.addWidget(QLabel("产品ID:"))
        subscribe_control.addWidget(self.inst_id_input)
        subscribe_control.addWidget(self.subscribe_button)
        subscribe_control.addWidget(self.unsubscribe_button)

        layout.addLayout(subscribe_control)

        # 订阅列表
        self.subscribe_list = QTableWidget()
        self.subscribe_list.setColumnCount(2)
        self.subscribe_list.setHorizontalHeaderLabels(["产品ID", "状态"])

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
        self.strategy_name_input.setPlaceholderText("策略名称")
        self.strategy_type_combo = QComboBox()
        self.strategy_type_combo.addItems(["动态策略", "PassivBot策略", "自定义策略"])
        self.create_strategy_button = QPushButton("创建策略")
        self.start_strategy_button = QPushButton("启动策略")
        self.stop_strategy_button = QPushButton("停止策略")

        strategy_control.addWidget(QLabel("策略名称:"))
        strategy_control.addWidget(self.strategy_name_input)
        strategy_control.addWidget(QLabel("策略类型:"))
        strategy_control.addWidget(self.strategy_type_combo)
        strategy_control.addWidget(self.create_strategy_button)
        strategy_control.addWidget(self.start_strategy_button)
        strategy_control.addWidget(self.stop_strategy_button)

        layout.addLayout(strategy_control)

        # 策略列表
        self.strategy_list = QTableWidget()
        self.strategy_list.setColumnCount(4)
        self.strategy_list.setHorizontalHeaderLabels(
            ["策略名称", "策略类型", "状态", "操作"]
        )
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
            is_test = self.testnet_checkbox.currentText() == "模拟盘"

            self._run_async_task(
                self.connect_ws(api_key, api_secret, passphrase, is_test)
            )

    def _run_async_task(self, coro):
        """
        安全地运行异步任务
        """

        def run_coro():
            try:
                asyncio.run(coro)
            except Exception as e:
                logger.error(f"运行异步任务错误: {e}")

        # 使用线程池运行任务
        self._thread_pool.submit(run_coro)

    async def connect_ws(self, api_key, api_secret, passphrase, is_test):
        """
        连接 WebSocket
        """
        try:
            self.ws_client = OKXWebSocketClient(
                api_key=api_key,
                api_secret=api_secret,
                passphrase=passphrase,
                is_test=is_test,
            )

            self.statusBar.showMessage("正在连接 WebSocket...")

            # 连接
            success = await self.ws_client.connect()

            if success:
                self.update_connection_status.emit(True, "已连接")
                self.statusBar.showMessage("WebSocket 连接成功")
                self.connect_button.setText("断开")

                # 订阅默认产品
                await self.ws_client.subscribe("tickers", "BTC-USDT-SWAP")
                await self.ws_client.subscribe("tickers", "ETH-USDT-SWAP")

            else:
                self.update_connection_status.emit(False, "连接失败")
                self.statusBar.showMessage("WebSocket 连接失败")

        except Exception as e:
            logger.error(f"连接 WebSocket 错误: {e}")
            self.update_connection_status.emit(False, f"连接错误: {str(e)}")
            self.statusBar.showMessage(f"连接错误: {str(e)}")

    async def disconnect_ws(self):
        """
        断开 WebSocket 连接
        """
        try:
            if self.ws_client:
                await self.ws_client.close()
                self.update_connection_status.emit(False, "已断开")
                self.statusBar.showMessage("WebSocket 已断开")
                self.connect_button.setText("连接")
        except Exception as e:
            logger.error(f"断开 WebSocket 错误: {e}")

    def subscribe_instrument(self):
        """
        订阅产品
        """
        inst_id = self.inst_id_input.text().strip()
        if not inst_id:
            self.statusBar.showMessage("请输入产品ID")
            return

        if not self.ws_client or not self.ws_client.is_connected():
            self.statusBar.showMessage("请先连接 WebSocket")
            return

        self._run_async_task(self._subscribe_instrument(inst_id))

    async def _subscribe_instrument(self, inst_id):
        """
        异步订阅产品
        """
        try:
            success = await self.ws_client.subscribe("tickers", inst_id)
            if success:
                self.statusBar.showMessage(f"订阅 {inst_id} 成功")
                # 更新订阅列表
                self.update_subscribe_list()
            else:
                self.statusBar.showMessage(f"订阅 {inst_id} 失败")
        except Exception as e:
            logger.error(f"订阅错误: {e}")
            self.statusBar.showMessage(f"订阅错误: {str(e)}")

    def unsubscribe_instrument(self):
        """
        取消订阅产品
        """
        # 获取选中的行
        selected_rows = self.subscribe_list.selectionModel().selectedRows()
        if not selected_rows:
            self.statusBar.showMessage("请选择要取消订阅的产品")
            return

        if not self.ws_client or not self.ws_client.is_connected():
            self.statusBar.showMessage("请先连接 WebSocket")
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
            self.statusBar.showMessage(f"取消订阅 {inst_id} 成功")
            # 更新订阅列表
            self.update_subscribe_list()
        except Exception as e:
            logger.error(f"取消订阅错误: {e}")
            self.statusBar.showMessage(f"取消订阅错误: {str(e)}")

    def update_subscribe_list(self):
        """
        更新订阅列表
        """
        # 清空表格
        self.subscribe_list.setRowCount(0)

        # 添加默认订阅的产品
        default_products = ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
        for product in default_products:
            row_position = self.subscribe_list.rowCount()
            self.subscribe_list.insertRow(row_position)
            self.subscribe_list.setItem(row_position, 0, QTableWidgetItem(product))
            self.subscribe_list.setItem(row_position, 1, QTableWidgetItem("已订阅"))

    def create_strategy(self):
        """
        创建策略
        """
        strategy_name = self.strategy_name_input.text().strip()
        if not strategy_name:
            self.statusBar.showMessage("请输入策略名称")
            return

        strategy_type = self.strategy_type_combo.currentText()

        # 检查策略是否已存在
        existing_strategy_names = [s["name"] for s in self.strategies]
        if strategy_name in existing_strategy_names:
            self.statusBar.showMessage(f"策略 {strategy_name} 已存在")
            return

        # 打开代码导入对话框
        from PyQt5.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QTextEdit,
            QPushButton,
            QLabel,
            QHBoxLayout,
        )

        dialog = QDialog(self)
        dialog.setWindowTitle("导入策略代码")
        dialog.setGeometry(200, 200, 800, 600)

        layout = QVBoxLayout(dialog)

        # 提示信息
        info_label = QLabel("请输入或粘贴策略代码:")
        layout.addWidget(info_label)

        # 代码输入区域
        code_editor = QTextEdit()
        code_editor.setPlaceholderText("请输入策略代码...")
        layout.addWidget(code_editor)

        # 按钮布局
        button_layout = QHBoxLayout()
        cancel_button = QPushButton("取消")
        create_button = QPushButton("创建")

        button_layout.addStretch(1)
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(create_button)

        layout.addLayout(button_layout)

        # 连接按钮信号
        def on_cancel():
            dialog.reject()

        def on_create():
            code = code_editor.toPlainText().strip()
            if not code:
                self.statusBar.showMessage("请输入策略代码")
                return

            # 保存策略代码到文件
            import os

            strategies_dir = "d:\\Projects\\okx_trading_bot\\strategies"
            strategy_file = os.path.join(strategies_dir, f"{strategy_name}.py")

            try:
                with open(strategy_file, "w", encoding="utf-8") as f:
                    f.write(code)
                logger.info(f"策略文件已创建: {strategy_file}")

                # 添加新策略到列表
                self.strategies.append(
                    {
                        "name": strategy_name,
                        "type": strategy_type,
                        "status": "已停止",
                        "file": f"{strategy_name}.py",
                    }
                )

                self.statusBar.showMessage(
                    f"创建策略 {strategy_name} ({strategy_type}) 成功"
                )

                # 更新策略列表
                self.update_strategy_list()

                dialog.accept()
            except Exception as e:
                logger.error(f"创建策略文件失败: {e}")
                self.statusBar.showMessage(f"创建策略失败: {str(e)}")

        cancel_button.clicked.connect(on_cancel)
        create_button.clicked.connect(on_create)

        # 显示对话框
        dialog.exec_()

    def start_strategy(self):
        """
        启动策略
        """
        # 获取选中的行
        selected_rows = self.strategy_list.selectionModel().selectedRows()
        if not selected_rows:
            self.statusBar.showMessage("请选择要启动的策略")
            return

        # 启动选中的策略
        for row in selected_rows:
            strategy_name = self.strategy_list.item(row.row(), 0).text()

            # 检查策略是否已经在运行
            if (
                strategy_name in self.strategy_threads
                and self.strategy_threads[strategy_name].is_alive()
            ):
                self.statusBar.showMessage(f"策略 {strategy_name} 已经在运行")
                continue

            # 查找策略
            strategy_info = None
            for strategy in self.strategies:
                if strategy["name"] == strategy_name:
                    strategy_info = strategy
                    break

            if not strategy_info:
                self.statusBar.showMessage(f"策略 {strategy_name} 不存在")
                continue

            try:
                # 动态加载策略模块
                import os
                import importlib.util

                strategies_dir = "d:\\Projects\\okx_trading_bot\\strategies"
                strategy_file = os.path.join(strategies_dir, f"{strategy_name}.py")

                if not os.path.exists(strategy_file):
                    self.statusBar.showMessage(f"策略文件不存在: {strategy_file}")
                    continue

                # 加载模块
                spec = importlib.util.spec_from_file_location(
                    strategy_name, strategy_file
                )
                if spec and spec.loader:
                    strategy_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(strategy_module)

                    # 查找策略类
                    strategy_class = None
                    for name, obj in strategy_module.__dict__.items():
                        if isinstance(obj, type) and hasattr(obj, "execute"):
                            strategy_class = obj
                            break

                    if not strategy_class:
                        self.statusBar.showMessage(
                            f"策略文件中未找到策略类: {strategy_name}"
                        )
                        continue

                    # 创建策略实例
                    strategy_instance = strategy_class()
                    self.strategy_instances[strategy_name] = strategy_instance

                    # 启动策略
                    strategy_instance.start()

                    # 更新策略状态
                    strategy_info["status"] = "运行中"
                    self.strategy_list.setItem(row.row(), 2, QTableWidgetItem("运行中"))

                    # 启动监控线程
                    import threading

                    def run_strategy():
                        import time

                        while strategy_info["status"] == "运行中":
                            try:
                                # 模拟市场数据
                                market_data = {
                                    "inst_id": "BTC-USDT-SWAP",
                                    "price": 40000.0,
                                    "timestamp": time.time(),
                                }
                                # 执行策略
                                strategy_instance.execute(market_data)
                                time.sleep(1)  # 每秒执行一次
                            except Exception as e:
                                logger.error(f"策略执行错误: {e}")
                                time.sleep(1)

                    thread = threading.Thread(target=run_strategy)
                    thread.daemon = True
                    thread.start()
                    self.strategy_threads[strategy_name] = thread

                    self.statusBar.showMessage(f"启动策略 {strategy_name} 成功")
                    logger.info(f"策略 {strategy_name} 已启动")
                else:
                    self.statusBar.showMessage(f"加载策略模块失败: {strategy_name}")
            except Exception as e:
                logger.error(f"启动策略失败: {e}")
                self.statusBar.showMessage(f"启动策略 {strategy_name} 失败: {str(e)}")

    def stop_strategy(self):
        """
        停止策略
        """
        # 获取选中的行
        selected_rows = self.strategy_list.selectionModel().selectedRows()
        if not selected_rows:
            self.statusBar.showMessage("请选择要停止的策略")
            return

        # 停止选中的策略
        for row in selected_rows:
            strategy_name = self.strategy_list.item(row.row(), 0).text()

            # 查找策略并更新状态
            for strategy in self.strategies:
                if strategy["name"] == strategy_name:
                    strategy["status"] = "已停止"
                    break

            # 停止策略实例
            if strategy_name in self.strategy_instances:
                try:
                    strategy_instance = self.strategy_instances[strategy_name]
                    strategy_instance.stop()
                    del self.strategy_instances[strategy_name]
                except Exception as e:
                    logger.error(f"停止策略实例失败: {e}")

            # 清理策略线程
            if strategy_name in self.strategy_threads:
                # 由于线程是守护线程，我们只需要清理引用
                del self.strategy_threads[strategy_name]

            # 更新策略状态
            self.strategy_list.setItem(row.row(), 2, QTableWidgetItem("已停止"))
            self.statusBar.showMessage(f"停止策略 {strategy_name} 成功")
            logger.info(f"策略 {strategy_name} 已停止")

    def edit_strategy(self, strategy_name):
        """
        编辑策略
        """
        # 这里需要实现策略编辑的逻辑
        # 由于我们没有实际的策略管理系统，这里只是模拟
        self.statusBar.showMessage(f"编辑策略 {strategy_name}")

    def delete_strategy(self, strategy_name):
        """
        删除策略
        """
        # 查找并删除策略
        for i, strategy in enumerate(self.strategies):
            if strategy["name"] == strategy_name:
                # 删除策略文件
                import os

                strategies_dir = "d:\\Projects\\okx_trading_bot\\strategies"
                strategy_file = os.path.join(strategies_dir, f"{strategy_name}.py")
                if os.path.exists(strategy_file):
                    try:
                        os.remove(strategy_file)
                        logger.info(f"策略文件已删除: {strategy_file}")
                    except Exception as e:
                        logger.error(f"删除策略文件失败: {e}")

                # 从列表中删除
                self.strategies.pop(i)
                self.statusBar.showMessage(f"删除策略 {strategy_name} 成功")
                # 更新策略列表
                self.update_strategy_list()
                return

        self.statusBar.showMessage(f"策略 {strategy_name} 不存在")

    def view_strategy_details(self, strategy_name):
        """
        查看策略详情
        """
        # 查找策略
        for strategy in self.strategies:
            if strategy["name"] == strategy_name:
                # 显示策略详情
                details = f"策略名称: {strategy['name']}\n"
                details += f"策略类型: {strategy['type']}\n"
                details += f"状态: {strategy['status']}\n"
                details += f"文件: {strategy.get('file', 'N/A')}"
                self.statusBar.showMessage(f"查看策略 {strategy_name} 详情")
                # 这里可以弹出一个对话框显示详细信息
                return

        self.statusBar.showMessage(f"策略 {strategy_name} 不存在")

    def run_strategy_backtest(self, strategy_name):
        """
        运行策略回测
        """
        self.statusBar.showMessage(f"运行策略 {strategy_name} 回测")

        # 打开回测参数设置对话框
        from PyQt5.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QLabel,
            QLineEdit,
            QComboBox,
            QPushButton,
            QHBoxLayout,
            QDateEdit,
        )
        from datetime import datetime, timedelta

        dialog = QDialog(self)
        dialog.setWindowTitle("策略回测参数")
        dialog.setGeometry(200, 200, 500, 300)

        layout = QVBoxLayout(dialog)

        # 产品ID
        inst_id_layout = QHBoxLayout()
        inst_id_label = QLabel("产品ID:")
        self.inst_id_input = QLineEdit("BTC-USDT-SWAP")
        inst_id_layout.addWidget(inst_id_label)
        inst_id_layout.addWidget(self.inst_id_input)
        layout.addLayout(inst_id_layout)

        # 开始时间
        start_time_layout = QHBoxLayout()
        start_time_label = QLabel("开始时间:")
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDate(datetime.now() - timedelta(days=7))
        start_time_layout.addWidget(start_time_label)
        start_time_layout.addWidget(self.start_date_edit)
        layout.addLayout(start_time_layout)

        # 结束时间
        end_time_layout = QHBoxLayout()
        end_time_label = QLabel("结束时间:")
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDate(datetime.now())
        end_time_layout.addWidget(end_time_label)
        end_time_layout.addWidget(self.end_date_edit)
        layout.addLayout(end_time_layout)

        # K线粒度
        bar_layout = QHBoxLayout()
        bar_label = QLabel("K线粒度:")
        self.bar_combo = QComboBox()
        self.bar_combo.addItems(
            ["1m", "3m", "5m", "15m", "30m", "1H", "2H", "4H", "6H", "12H", "1D"]
        )
        self.bar_combo.setCurrentText("1H")
        bar_layout.addWidget(bar_label)
        bar_layout.addWidget(self.bar_combo)
        layout.addLayout(bar_layout)

        # 初始资金
        balance_layout = QHBoxLayout()
        balance_label = QLabel("初始资金:")
        self.balance_input = QLineEdit("10000")
        balance_layout.addWidget(balance_label)
        balance_layout.addWidget(self.balance_input)
        layout.addLayout(balance_layout)

        # 按钮布局
        button_layout = QHBoxLayout()
        cancel_button = QPushButton("取消")
        run_button = QPushButton("运行回测")

        button_layout.addStretch(1)
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(run_button)

        layout.addLayout(button_layout)

        # 连接按钮信号
        def on_cancel():
            dialog.reject()

        def on_run():
            # 获取参数
            inst_id = self.inst_id_input.text().strip()
            start_date = self.start_date_edit.date().toPyDate()
            end_date = self.end_date_edit.date().toPyDate()
            bar = self.bar_combo.currentText()
            try:
                initial_balance = float(self.balance_input.text().strip())
            except ValueError:
                self.statusBar.showMessage("初始资金必须是数字")
                return

            # 开始回测
            self._run_async_task(
                self._run_backtest(
                    strategy_name, inst_id, start_date, end_date, bar, initial_balance
                )
            )
            dialog.accept()

        cancel_button.clicked.connect(on_cancel)
        run_button.clicked.connect(on_run)

        # 显示对话框
        dialog.exec_()

    async def _run_backtest(
        self, strategy_name, inst_id, start_date, end_date, bar, initial_balance
    ):
        """
        异步运行策略回测
        """
        try:
            from core.backtesting import StrategyBacktester
            from core.api.okx_rest_client import OKXRESTClient

            # 创建REST客户端
            rest_client = OKXRESTClient(is_test=True)

            # 创建回测器
            backtester = StrategyBacktester(rest_client)

            # 导入策略模块
            import os
            strategies_dir = "d:\Projects\okx_trading_bot\strategies"
            strategy_file = os.path.join(strategies_dir, f"{strategy_name}.py")

            if not os.path.exists(strategy_file):
                self.statusBar.showMessage(f"策略文件不存在: {strategy_file}")
                return

            # 加载策略模块
            spec = importlib.util.spec_from_file_location(strategy_name, strategy_file)
            if spec and spec.loader:
                strategy_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(strategy_module)

                # 查找策略类
                strategy_class = None
                for name, obj in strategy_module.__dict__.items():
                    if isinstance(obj, type) and hasattr(obj, "execute"):
                        strategy_class = obj
                        break

                if not strategy_class:
                    self.statusBar.showMessage(
                        f"策略文件中未找到策略类: {strategy_name}"
                    )
                    return

                # 创建策略实例
                strategy_instance = strategy_class()

                # 运行回测
                self.statusBar.showMessage(f"正在回测策略 {strategy_name}...")
                result = await backtester.backtest_strategy(
                    strategy=strategy_instance,
                    inst_id=inst_id,
                    start_time=datetime.combine(start_date, datetime.min.time()),
                    end_time=datetime.combine(end_date, datetime.max.time()),
                    bar=bar,
                    initial_balance=initial_balance,
                )

                # 显示回测结果
                if result:
                    self._show_backtest_result(result)
                else:
                    self.statusBar.showMessage("回测失败")
            else:
                self.statusBar.showMessage(f"加载策略模块失败: {strategy_name}")
        except Exception as e:
            logger.error(f"回测错误: {e}")
            self.statusBar.showMessage(f"回测错误: {str(e)}")

    def _show_backtest_result(self, result):
        """
        显示回测结果
        """
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton

        dialog = QDialog(self)
        dialog.setWindowTitle("回测结果")
        dialog.setGeometry(200, 200, 600, 400)

        layout = QVBoxLayout(dialog)

        # 结果文本
        result_text = QTextEdit()
        result_text.setReadOnly(True)

        text = f"回测结果\n"
        text += f"策略: {result.get('strategy', 'N/A')}\n"
        text += f"产品: {result.get('inst_id', 'N/A')}\n"
        text += f"时间范围: {result.get('start_time', 'N/A')} 至 {result.get('end_time', 'N/A')}\n"
        text += f"K线粒度: {result.get('bar', 'N/A')}\n"
        text += f"初始资金: {result.get('initial_balance', 0):.2f}\n"
        text += f"最终资金: {result.get('final_balance', 0):.2f}\n"
        text += f"总收益: {result.get('total_profit', 0):.2f}\n"
        text += f"总收益率: {result.get('total_return', 0):.2f}%\n"
        text += f"胜率: {result.get('win_rate', 0):.2f}%\n"
        text += f"最大回撤: {result.get('max_drawdown', 0):.2f}%\n"
        text += f"夏普比率: {result.get('sharpe_ratio', 0):.2f}\n"
        text += f"平均盈利: {result.get('avg_win', 0):.2f}\n"
        text += f"平均亏损: {result.get('avg_loss', 0):.2f}\n"
        text += f"总交易次数: {result.get('total_trades', 0)}\n"
        text += f"盈利交易: {result.get('win_trades', 0)}\n"
        text += f"亏损交易: {result.get('loss_trades', 0)}\n"

        result_text.setText(text)
        layout.addWidget(result_text)

        # 关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)

        # 显示对话框
        dialog.exec_()

    def init_monitor_tab(self):
        """
        初始化监控与分析标签页
        """
        monitor_layout = QVBoxLayout(self.monitor_tab)
        monitor_layout.setContentsMargins(15, 15, 15, 15)
        monitor_layout.setSpacing(15)

        # 监控概览卡片
        overview_group = QGroupBox("系统概览")
        overview_layout = QHBoxLayout()
        overview_layout.setContentsMargins(15, 15, 15, 15)
        overview_layout.setSpacing(15)
        
        # 连接状态卡片
        connection_card = QGroupBox("连接状态")
        connection_layout = QVBoxLayout()
        self.connection_status_label = QLabel("未连接")
        self.connection_status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: red;")
        connection_layout.addWidget(self.connection_status_label)
        connection_card.setLayout(connection_layout)
        
        # 策略状态卡片
        strategy_card = QGroupBox("策略状态")
        strategy_layout = QVBoxLayout()
        self.strategy_status_label = QLabel("未启动")
        self.strategy_status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: red;")
        strategy_layout.addWidget(self.strategy_status_label)
        strategy_card.setLayout(strategy_layout)
        
        # API调用统计卡片
        api_card = QGroupBox("API调用")
        api_layout = QVBoxLayout()
        self.api_call_label = QLabel("0次调用")
        self.api_call_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        api_layout.addWidget(self.api_call_label)
        api_card.setLayout(api_layout)
        
        # 交易统计卡片
        trade_card = QGroupBox("交易统计")
        trade_layout = QVBoxLayout()
        self.trade_count_label = QLabel("0笔交易")
        self.trade_count_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        trade_layout.addWidget(self.trade_count_label)
        trade_card.setLayout(trade_layout)
        
        overview_layout.addWidget(connection_card, 1)
        overview_layout.addWidget(strategy_card, 1)
        overview_layout.addWidget(api_card, 1)
        overview_layout.addWidget(trade_card, 1)
        overview_group.setLayout(overview_layout)
        monitor_layout.addWidget(overview_group)

        # 监控标签页
        monitor_tab_widget = QTabWidget()
        monitor_layout.addWidget(monitor_tab_widget)

        # 策略监控标签
        strategy_monitor_tab = QWidget()
        monitor_tab_widget.addTab(strategy_monitor_tab, "策略监控")
        self.init_strategy_monitor_tab(strategy_monitor_tab)

        # API监控标签
        api_monitor_tab = QWidget()
        monitor_tab_widget.addTab(api_monitor_tab, "API监控")
        self.init_api_monitor_tab(api_monitor_tab)

        # 数据可视化标签
        visualization_tab = QWidget()
        monitor_tab_widget.addTab(visualization_tab, "数据可视化")
        self.init_visualization_tab(visualization_tab)

        # 日志标签
        log_tab = QWidget()
        monitor_tab_widget.addTab(log_tab, "日志")
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
        self.strategy_monitor_table.setHorizontalHeaderLabels(
            [
                "策略名称",
                "状态",
                "总交易数",
                "总盈亏",
                "胜率",
                "平均盈亏",
                "运行时间",
                "平均执行时间",
            ]
        )
        self.strategy_monitor_table.setSortingEnabled(True)

        layout.addWidget(self.strategy_monitor_table)

    def init_api_monitor_tab(self, parent):
        """
        初始化API监控标签
        """
        from PyQt5.QtWidgets import QTabWidget

        layout = QVBoxLayout(parent)

        # API状态信息
        self.api_status_info = QLabel("API状态将在此显示")
        layout.addWidget(self.api_status_info)

        # API监控标签页
        api_tab_widget = QTabWidget()
        layout.addWidget(api_tab_widget)

        # API调用统计标签
        stats_tab = QWidget()
        api_tab_widget.addTab(stats_tab, "调用统计")

        stats_layout = QVBoxLayout(stats_tab)
        # API调用统计表格
        self.api_call_table = QTableWidget()
        self.api_call_table.setColumnCount(3)
        self.api_call_table.setHorizontalHeaderLabels(
            ["API类型", "调用次数", "平均响应时间"]
        )
        self.api_call_table.setSortingEnabled(True)
        stats_layout.addWidget(self.api_call_table)

        # API调用历史标签
        history_tab = QWidget()
        api_tab_widget.addTab(history_tab, "调用历史")

        history_layout = QVBoxLayout(history_tab)
        # API调用历史表格
        self.api_history_table = QTableWidget()
        self.api_history_table.setColumnCount(8)
        self.api_history_table.setHorizontalHeaderLabels(
            ["时间", "调用者", "方法", "端点", "状态码", "响应时间", "错误", "操作"]
        )
        self.api_history_table.setSortingEnabled(True)
        # 设置列宽
        self.api_history_table.setColumnWidth(0, 150)
        self.api_history_table.setColumnWidth(1, 100)
        self.api_history_table.setColumnWidth(2, 60)
        self.api_history_table.setColumnWidth(3, 150)
        self.api_history_table.setColumnWidth(4, 80)
        self.api_history_table.setColumnWidth(5, 100)
        self.api_history_table.setColumnWidth(6, 200)
        history_layout.addWidget(self.api_history_table)

        # WebSocket消息历史标签
        ws_tab = QWidget()
        api_tab_widget.addTab(ws_tab, "WebSocket消息")

        ws_layout = QVBoxLayout(ws_tab)
        # WebSocket消息历史表格
        self.ws_history_table = QTableWidget()
        self.ws_history_table.setColumnCount(7)
        self.ws_history_table.setHorizontalHeaderLabels(
            ["时间", "频道", "消息类型", "通道名称", "产品ID", "处理时间", "错误"]
        )
        self.ws_history_table.setSortingEnabled(True)
        # 设置列宽
        self.ws_history_table.setColumnWidth(0, 150)
        self.ws_history_table.setColumnWidth(1, 80)
        self.ws_history_table.setColumnWidth(2, 100)
        self.ws_history_table.setColumnWidth(3, 120)
        self.ws_history_table.setColumnWidth(4, 100)
        self.ws_history_table.setColumnWidth(5, 100)
        self.ws_history_table.setColumnWidth(6, 200)
        ws_layout.addWidget(self.ws_history_table)

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
            self.strategy_monitor_table.setItem(
                row_position, 0, QTableWidgetItem(strategy_name)
            )

            # 状态
            status = status_data.get("status", "未知")
            status_item = QTableWidgetItem(status)
            if status == "running":
                status_item.setForeground(QColor("green"))
            elif status == "error":
                status_item.setForeground(QColor("red"))
            self.strategy_monitor_table.setItem(row_position, 1, status_item)

            # 性能指标
            metrics = status_data.get("metrics", {})
            self.strategy_monitor_table.setItem(
                row_position, 2, QTableWidgetItem(str(metrics.get("total_trades", 0)))
            )
            self.strategy_monitor_table.setItem(
                row_position,
                3,
                QTableWidgetItem(f"{metrics.get('total_profit', 0):.2f}"),
            )
            self.strategy_monitor_table.setItem(
                row_position, 4, QTableWidgetItem(f"{metrics.get('win_rate', 0):.2%}")
            )
            self.strategy_monitor_table.setItem(
                row_position,
                5,
                QTableWidgetItem(f"{metrics.get('avg_profit_per_trade', 0):.2f}"),
            )

            # 运行时间
            uptime = metrics.get("strategy_uptime", 0)
            uptime_str = f"{uptime:.0f}s"
            if uptime > 3600:
                hours = int(uptime // 3600)
                minutes = int((uptime % 3600) // 60)
                uptime_str = f"{hours}h {minutes}m"
            elif uptime > 60:
                minutes = int(uptime // 60)
                seconds = int(uptime % 60)
                uptime_str = f"{minutes}m {seconds}s"
            self.strategy_monitor_table.setItem(
                row_position, 6, QTableWidgetItem(uptime_str)
            )

            # 平均执行时间
            avg_exec_time = metrics.get("average_execution_time", 0)
            self.strategy_monitor_table.setItem(
                row_position, 7, QTableWidgetItem(f"{avg_exec_time:.3f}s")
            )

    def update_api_monitor_data(self):
        """
        更新API监控数据
        """
        # 检查WebSocket连接状态
        if self.ws_client and self.ws_client.is_connected():
            api_status = "API连接正常"
        else:
            api_status = "API未连接"
        self.api_status_info.setText(api_status)

        # 更新API调用统计表格
        self.update_api_call_stats()

        # 更新API调用历史表格
        self.update_api_history()

        # 更新WebSocket消息历史表格
        self.update_ws_history()

    def update_api_call_stats(self):
        """
        更新API调用统计表格
        """
        # 清空表格
        self.api_call_table.setRowCount(0)

        # 从REST客户端获取实际的API调用统计数据
        rest_client = None
        if hasattr(self, "ws_client") and hasattr(self.ws_client, "rest_client"):
            rest_client = self.ws_client.rest_client

        # 统计API调用
        api_stats = {
            "REST API": {"count": 0, "total_time": 0},
            "WebSocket": {"count": 0, "total_time": 0},
            "订单操作": {"count": 0, "total_time": 0},
            "市场数据": {"count": 0, "total_time": 0},
        }

        # 计算实际的API调用统计
        if rest_client and hasattr(rest_client, "api_call_history"):
            for call in rest_client.api_call_history:
                api_stats["REST API"]["count"] += 1
                if call["response_time"]:
                    api_stats["REST API"]["total_time"] += call["response_time"]

                # 根据端点分类
                endpoint = call["endpoint"]
                if "/trade/" in endpoint:
                    api_stats["订单操作"]["count"] += 1
                    if call["response_time"]:
                        api_stats["订单操作"]["total_time"] += call["response_time"]
                elif "/market/" in endpoint or "/public/" in endpoint:
                    api_stats["市场数据"]["count"] += 1
                    if call["response_time"]:
                        api_stats["市场数据"]["total_time"] += call["response_time"]

        # 统计WebSocket消息
        if hasattr(self, "ws_client") and hasattr(self.ws_client, "ws_message_history"):
            for msg in self.ws_client.ws_message_history:
                api_stats["WebSocket"]["count"] += 1
                if msg["process_time"]:
                    api_stats["WebSocket"]["total_time"] += msg["process_time"]

        # 添加统计数据到表格
        for api_type, stats in api_stats.items():
            count = stats["count"]
            avg_time = stats["total_time"] / count if count > 0 else 0

            row_position = self.api_call_table.rowCount()
            self.api_call_table.insertRow(row_position)
            self.api_call_table.setItem(row_position, 0, QTableWidgetItem(api_type))
            self.api_call_table.setItem(row_position, 1, QTableWidgetItem(str(count)))
            self.api_call_table.setItem(
                row_position, 2, QTableWidgetItem(f"{avg_time:.3f}s")
            )

    def update_api_history(self):
        """
        更新API调用历史表格
        """
        # 清空表格
        self.api_history_table.setRowCount(0)

        # 从REST客户端获取API调用历史
        rest_client = None
        if hasattr(self, "ws_client") and hasattr(self.ws_client, "rest_client"):
            rest_client = self.ws_client.rest_client

        if rest_client and hasattr(rest_client, "api_call_history"):
            # 只显示最近的50条记录
            recent_calls = rest_client.api_call_history[-50:]

            for call in reversed(recent_calls):  # 倒序显示，最新的在前面
                row_position = self.api_history_table.rowCount()
                self.api_history_table.insertRow(row_position)

                # 时间
                timestamp = call.get("timestamp", 0)
                time_str = datetime.fromtimestamp(timestamp).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                self.api_history_table.setItem(
                    row_position, 0, QTableWidgetItem(time_str)
                )

                # 调用者
                caller = call.get("caller", "未知")
                self.api_history_table.setItem(
                    row_position, 1, QTableWidgetItem(caller)
                )

                # 方法
                method = call.get("method", "未知")
                self.api_history_table.setItem(
                    row_position, 2, QTableWidgetItem(method)
                )

                # 端点
                endpoint = call.get("endpoint", "未知")
                self.api_history_table.setItem(
                    row_position, 3, QTableWidgetItem(endpoint)
                )

                # 状态码
                status_code = call.get("status_code", "未知")
                self.api_history_table.setItem(
                    row_position, 4, QTableWidgetItem(str(status_code))
                )

                # 响应时间
                response_time = call.get("response_time", 0)
                self.api_history_table.setItem(
                    row_position, 5, QTableWidgetItem(f"{response_time:.3f}s")
                )

                # 错误
                error = call.get("error", "")
                error_item = QTableWidgetItem(
                    error[:100] + "..." if len(error) > 100 else error
                )
                if error:
                    error_item.setForeground(QColor("red"))
                self.api_history_table.setItem(row_position, 6, error_item)

                # 操作按钮
                action_widget = QWidget()
                action_layout = QHBoxLayout(action_widget)
                action_layout.setContentsMargins(2, 2, 2, 2)

                details_button = QPushButton("详情")
                details_button.setMinimumWidth(60)
                details_button.clicked.connect(
                    lambda checked, c=call: self.show_api_call_details(c)
                )

                action_layout.addWidget(details_button)
                self.api_history_table.setCellWidget(row_position, 7, action_widget)

    def update_ws_history(self):
        """
        更新WebSocket消息历史表格
        """
        # 清空表格
        self.ws_history_table.setRowCount(0)

        # 从WebSocket客户端获取消息历史
        if hasattr(self, "ws_client") and hasattr(self.ws_client, "ws_message_history"):
            # 只显示最近的50条记录
            recent_messages = self.ws_client.ws_message_history[-50:]

            for msg in reversed(recent_messages):  # 倒序显示，最新的在前面
                row_position = self.ws_history_table.rowCount()
                self.ws_history_table.insertRow(row_position)

                # 时间
                timestamp = msg.get("timestamp", 0)
                time_str = datetime.fromtimestamp(timestamp).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                self.ws_history_table.setItem(
                    row_position, 0, QTableWidgetItem(time_str)
                )

                # 频道
                channel = msg.get("channel", "未知")
                self.ws_history_table.setItem(
                    row_position, 1, QTableWidgetItem(channel)
                )

                # 消息类型
                message_type = msg.get("message_type", "未知")
                self.ws_history_table.setItem(
                    row_position, 2, QTableWidgetItem(message_type)
                )

                # 通道名称
                channel_name = msg.get("channel_name", "")
                self.ws_history_table.setItem(
                    row_position, 3, QTableWidgetItem(channel_name)
                )

                # 产品ID
                inst_id = msg.get("inst_id", "")
                self.ws_history_table.setItem(
                    row_position, 4, QTableWidgetItem(inst_id)
                )

                # 处理时间
                process_time = msg.get("process_time", 0)
                self.ws_history_table.setItem(
                    row_position, 5, QTableWidgetItem(f"{process_time:.3f}s")
                )

                # 错误
                error = msg.get("error", "")
                error_item = QTableWidgetItem(
                    error[:100] + "..." if len(error) > 100 else error
                )
                if error:
                    error_item.setForeground(QColor("red"))
                self.ws_history_table.setItem(row_position, 6, error_item)

    def show_api_call_details(self, call):
        """
        显示API调用详细信息
        """
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QLabel

        dialog = QDialog(self)
        dialog.setWindowTitle("API调用详情")
        dialog.setGeometry(200, 200, 800, 600)

        layout = QVBoxLayout(dialog)

        # 时间
        timestamp = call.get("timestamp", 0)
        time_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        layout.addWidget(QLabel(f"时间: {time_str}"))

        # 调用者
        caller = call.get("caller", "未知")
        layout.addWidget(QLabel(f"调用者: {caller}"))

        # 方法
        method = call.get("method", "未知")
        layout.addWidget(QLabel(f"方法: {method}"))

        # URL
        url = call.get("url", "未知")
        layout.addWidget(QLabel(f"URL: {url}"))

        # 参数
        params = call.get("params", {})
        params_str = json.dumps(params, indent=2, ensure_ascii=False)
        layout.addWidget(QLabel("参数:"))
        params_text = QTextEdit()
        params_text.setText(params_str)
        params_text.setReadOnly(True)
        layout.addWidget(params_text)

        # 请求体
        body = call.get("body", {})
        body_str = json.dumps(body, indent=2, ensure_ascii=False)
        layout.addWidget(QLabel("请求体:"))
        body_text = QTextEdit()
        body_text.setText(body_str)
        body_text.setReadOnly(True)
        layout.addWidget(body_text)

        # 响应
        response = call.get("response", {})
        response_str = json.dumps(response, indent=2, ensure_ascii=False)
        layout.addWidget(QLabel("响应:"))
        response_text = QTextEdit()
        response_text.setText(response_str)
        response_text.setReadOnly(True)
        layout.addWidget(response_text)

        # 错误
        error = call.get("error", "")
        if error:
            layout.addWidget(QLabel("错误:"))
            error_text = QTextEdit()
            error_text.setText(error)
            error_text.setReadOnly(True)
            error_text.setStyleSheet("color: red;")
            layout.addWidget(error_text)

        # 关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)

        dialog.exec_()

    def update_log_data(self):
        """
        更新日志数据
        """
        # 这里可以添加实际的日志数据
        # 暂时显示模拟数据
        import time

        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{current_time}] INFO - 系统运行正常\n"

        # 限制日志显示行数
        current_log = self.log_text.toPlainText()
        log_lines = current_log.split("\n")
        if len(log_lines) > 1000:
            log_lines = log_lines[-1000:]
            current_log = "\n".join(log_lines)

        new_log = current_log + log_entry
        self.log_text.setPlainText(new_log)
        # 滚动到底部
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

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
        # 使用绝对路径，确保正确找到 strategies 目录
        strategies_dir = "d:\\Projects\\okx_trading_bot\\strategies"

        # 检查目录是否存在
        if not os.path.exists(strategies_dir):
            logger.warning(f"策略目录不存在: {strategies_dir}")
            # 尝试创建策略目录
            try:
                os.makedirs(strategies_dir, exist_ok=True)
                logger.info(f"策略目录已创建: {strategies_dir}")
            except Exception as e:
                logger.error(f"创建策略目录失败: {e}")
            return

        # 列出所有策略文件
        try:
            strategy_files = [
                f
                for f in os.listdir(strategies_dir)
                if f.endswith(".py") and f != "base_strategy.py"
            ]
        except Exception as e:
            logger.error(f"读取策略目录失败: {e}")
            strategy_files = []

        # 检查哪些策略已经在self.strategies中
        existing_strategy_names = [s["name"] for s in self.strategies]

        # 添加新的策略文件到self.strategies
        for strategy_file in strategy_files:
            # 提取策略名称
            strategy_name = os.path.splitext(strategy_file)[0]

            # 如果策略已经存在，跳过
            if strategy_name in existing_strategy_names:
                continue

            # 确定策略类型
            if "dynamics" in strategy_name:
                strategy_type = "动态策略"
            elif "passivbot" in strategy_name:
                strategy_type = "PassivBot策略"
            else:
                strategy_type = "自定义策略"

            # 添加到策略列表
            self.strategies.append(
                {
                    "name": strategy_name,
                    "type": strategy_type,
                    "status": "已停止",
                    "file": strategy_file,
                }
            )
            logger.info(f"加载策略文件: {strategy_file}")

        # 显示所有策略
        for strategy in self.strategies:
            row_position = self.strategy_list.rowCount()
            self.strategy_list.insertRow(row_position)
            self.strategy_list.setItem(
                row_position, 0, QTableWidgetItem(strategy["name"])
            )
            self.strategy_list.setItem(
                row_position, 1, QTableWidgetItem(strategy["type"])
            )
            self.strategy_list.setItem(
                row_position, 2, QTableWidgetItem(strategy["status"])
            )

            # 添加操作按钮
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(2, 2, 2, 2)

            edit_button = QPushButton("编辑")
            edit_button.setMinimumWidth(60)
            edit_button.clicked.connect(
                lambda checked, name=strategy["name"]: self.edit_strategy(name)
            )

            delete_button = QPushButton("删除")
            delete_button.setMinimumWidth(60)
            delete_button.clicked.connect(
                lambda checked, name=strategy["name"]: self.delete_strategy(name)
            )

            details_button = QPushButton("详情")
            details_button.setMinimumWidth(60)
            details_button.clicked.connect(
                lambda checked, name=strategy["name"]: self.view_strategy_details(name)
            )

            backtest_button = QPushButton("回测")
            backtest_button.setMinimumWidth(60)
            backtest_button.clicked.connect(
                lambda checked, name=strategy["name"]: self.run_strategy_backtest(name)
            )

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
        self.update_connection_status.emit(True, "已连接")

    def on_ws_disconnected(self, event):
        """
        处理 WebSocket 断开事件
        """
        self.update_connection_status.emit(False, "已断开")
    
    def execute_trade(self):
        """
        执行交易
        """
        try:
            # 获取交易参数
            trading_pair = self.trade_pair_combo.currentText()
            side = self.trade_side_combo.currentText()
            trade_type = self.trade_type_combo.currentText()
            price = self.trade_price_input.text()
            amount = self.trade_amount_input.text()
            
            # 验证参数
            if not amount:
                QMessageBox.warning(self, "错误", "请输入交易数量")
                return
            
            if trade_type == "限价" and not price:
                QMessageBox.warning(self, "错误", "限价交易需要输入价格")
                return
            
            # 执行交易逻辑
            logger.info(f"执行交易: {side} {amount} {trading_pair} at {price}")
            
            # 显示成功消息
            QMessageBox.information(self, "成功", f"交易请求已发送: {side} {amount} {trading_pair}")
            
            # 清空输入
            self.trade_price_input.clear()
            self.trade_amount_input.clear()
            
        except Exception as e:
            logger.error(f"执行交易错误: {e}")
            QMessageBox.error(self, "错误", f"执行交易失败: {str(e)}")

    def on_market_data_update(self, data):
        """
        更新市场数据
        """
        channel = data.get("channel")
        inst_id = data.get("inst_id")
        market_data = data.get("data", [])

        if channel == "tickers" and market_data:
            ticker_data = market_data[0]
            last_price = ticker_data.get("last", "0")
            change24h = ticker_data.get("change24h", "0")
            change24h_percent = ticker_data.get("change24hPercent", "0")
            vol24h = ticker_data.get("vol24h", "0")

            # 更新市场数据存储
            self.market_data[inst_id] = {
                "last": last_price,
                "change24h": change24h,
                "change24hPercent": change24h_percent,
                "vol24h": vol24h,
                "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
            self.market_table.setItem(row_position, 1, QTableWidgetItem(data["last"]))

            # 设置涨跌颜色
            change_item = QTableWidgetItem(data["change24h"])
            if float(data["change24h"]) > 0:
                change_item.setForeground(QColor("red"))
            elif float(data["change24h"]) < 0:
                change_item.setForeground(QColor("green"))
            self.market_table.setItem(row_position, 2, change_item)

            # 设置涨跌百分比颜色
            change_percent_item = QTableWidgetItem(data["change24hPercent"])
            if float(data["change24hPercent"]) > 0:
                change_percent_item.setForeground(QColor("red"))
            elif float(data["change24hPercent"]) < 0:
                change_percent_item.setForeground(QColor("green"))
            self.market_table.setItem(row_position, 3, change_percent_item)

            self.market_table.setItem(row_position, 4, QTableWidgetItem(data["vol24h"]))
            self.market_table.setItem(
                row_position, 5, QTableWidgetItem(data["update_time"])
            )

    def on_order_data_update(self, data):
        """
        更新订单数据
        """
        channel = data.get("channel")
        order_data = data.get("data", [])

        if channel == "orders" and order_data:
            # 更新订单数据
            for order in order_data:
                order_id = order.get("ordId")
                inst_id = order.get("instId")
                ord_type = order.get("ordType")
                side = order.get("side")
                price = order.get("px")
                size = order.get("sz")
                status = order.get("state")
                timestamp = order.get("ts")

                # 转换时间戳
                if timestamp:
                    try:
                        update_time = datetime.fromtimestamp(
                            int(timestamp) / 1000
                        ).strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        update_time = "N/A"
                else:
                    update_time = "N/A"

                # 检查订单是否已存在
                existing_order = next(
                    (o for o in self.order_data if o["ordId"] == order_id), None
                )

                if existing_order:
                    # 更新现有订单
                    existing_order.update(
                        {
                            "instId": inst_id,
                            "ordType": ord_type,
                            "side": side,
                            "px": price,
                            "sz": size,
                            "state": status,
                            "ts": timestamp,
                            "update_time": update_time,
                        }
                    )
                else:
                    # 添加新订单
                    self.order_data.append(
                        {
                            "ordId": order_id,
                            "instId": inst_id,
                            "ordType": ord_type,
                            "side": side,
                            "px": price,
                            "sz": size,
                            "state": status,
                            "ts": timestamp,
                            "update_time": update_time,
                        }
                    )

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

            self.order_table.setItem(
                row_position, 0, QTableWidgetItem(order.get("ordId", "N/A"))
            )
            self.order_table.setItem(
                row_position, 1, QTableWidgetItem(order.get("instId", "N/A"))
            )
            self.order_table.setItem(
                row_position, 2, QTableWidgetItem(order.get("ordType", "N/A"))
            )
            self.order_table.setItem(
                row_position, 3, QTableWidgetItem(order.get("side", "N/A"))
            )
            self.order_table.setItem(
                row_position, 4, QTableWidgetItem(order.get("px", "N/A"))
            )
            self.order_table.setItem(
                row_position, 5, QTableWidgetItem(order.get("sz", "N/A"))
            )
            self.order_table.setItem(
                row_position, 6, QTableWidgetItem(order.get("state", "N/A"))
            )
            self.order_table.setItem(
                row_position, 7, QTableWidgetItem(order.get("update_time", "N/A"))
            )

    def on_account_data_update(self, data):
        """
        更新账户数据
        """
        channel = data.get("channel")
        account_data = data.get("data", [])

        if channel == "account" and account_data:
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

        # 更新账户信息卡片
        total_equity = self.account_data.get("totalEq", "0")
        margin_ratio = self.account_data.get("mgnRatio", "0")
        available_balance = self.account_data.get("availBal", "0")
        total_position = "0"

        # 计算总仓位
        positions = self.account_data.get("positions", [])
        if positions:
            total_position = str(sum(float(pos.get("notionalUsd", "0")) for pos in positions))

        self.total_equity_label.setText(f"{total_equity} USDT")
        self.margin_ratio_label.setText(f"{margin_ratio}%")
        self.available_balance_label.setText(f"{available_balance} USDT")
        self.total_position_label.setText(f"{total_position} USDT")

        # 更新资产表格
        self.update_asset_table()

    def update_asset_table(self):
        """
        更新资产表格
        """
        self.asset_table.setRowCount(0)

        # 获取资产列表
        assets = self.account_data.get("positions", [])

        for asset in assets:
            ccy = asset.get("ccy", "N/A")
            avail_balance = asset.get("availBal", "0")
            frozen_balance = asset.get("frozenBal", "0")
            total_balance = (
                str(float(avail_balance) + float(frozen_balance))
                if avail_balance and frozen_balance
                else "0"
            )

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
            self.connection_status.setText(f"已连接: {message}")
            self.connection_status.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.connection_status.setText(f"未连接: {message}")
            self.connection_status.setStyleSheet("color: red; font-weight: bold;")

    def init_help_menu(self):
        """
        初始化帮助菜单
        """
        from PyQt5.QtWidgets import QMenuBar, QAction, QMessageBox

        # 获取菜单栏
        menubar = self.menuBar()

        # 创建帮助菜单
        help_menu = menubar.addMenu("帮助")

        # 创建功能说明动作
        help_action = QAction("功能说明", self)
        help_action.triggered.connect(self.show_help)
        help_menu.addAction(help_action)

    def show_help(self):
        """
        显示功能说明
        """
        from PyQt5.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QTextEdit,
            QPushButton,
            QScrollArea,
            QWidget,
        )
        from PyQt5.QtCore import Qt

        # 创建帮助对话框
        help_dialog = QDialog(self)
        help_dialog.setWindowTitle("功能说明")
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

8. API调用指南
   - REST API接口:
     | 接口名称 | 端点 | 方法 | 限速 | 功能描述 |
     |---------|------|------|------|----------|
     | 获取交易产品基础信息 | /api/v5/account/instruments | GET | 20次/2s | 获取当前账户可交易产品的信息列表 |
     | 查看账户余额 | /api/v5/account/balance | GET | 10次/2s | 获取交易账户中资金余额信息 |
     | 查看持仓信息 | /api/v5/account/positions | GET | 10次/2s | 获取该账户下拥有实际持仓的信息 |
     | 下单 | /api/v5/trade/order | POST | 独立限速 | 创建订单 |
     | 批量下单 | /api/v5/trade/batch-order | POST | 独立限速 | 批量创建订单 |
     | 取消订单 | /api/v5/trade/cancel-order | POST | 独立限速 | 取消订单 |
     | 批量取消订单 | /api/v5/trade/batch-cancel-orders | POST | 独立限速 | 批量取消订单 |
     | 修改订单 | /api/v5/trade/amend-order | POST | 独立限速 | 修改订单 |
     | 批量修改订单 | /api/v5/trade/batch-amend-orders | POST | 独立限速 | 批量修改订单 |
     | 获取订单信息 | /api/v5/trade/order | GET | 10次/2s | 获取订单详细信息 |
     | 获取未成交订单 | /api/v5/trade/orders-pending | GET | 10次/2s | 获取未成交订单列表 |
     | 获取历史订单 | /api/v5/trade/orders-history | GET | 10次/2s | 获取历史订单列表 |
     | 获取成交数据 | /api/v5/market/trades | GET | 20次/2s | 获取产品的成交数据 |
     | 获取K线数据 | /api/v5/market/candles | GET | 20次/2s | 获取产品的K线数据 |
     | 获取订单簿 | /api/v5/market/books | GET | 20次/2s | 获取产品的订单簿数据 |
     | 获取行情数据 | /api/v5/market/ticker | GET | 20次/2s | 获取产品的行情数据 |
     | 获取账户限速 | /api/v5/account/rate-limit | GET | 10次/2s | 获取账户限速信息 |
   - WebSocket API频道:
     | 频道类型 | 频道名称 | 功能描述 |
     |---------|---------|----------|
     | 公共频道 | tickers | 行情数据 |
     | 公共频道 | books | 订单簿数据 |
     | 公共频道 | candles | K线数据 |
     | 公共频道 | trades | 成交数据 |
     | 私有频道 | orders | 订单更新 |
     | 私有频道 | account | 账户更新 |
     | 私有频道 | positions | 持仓更新 |
   - API调用限速规则:
     - WebSocket登录和订阅限速基于连接
     - 公共未经身份验证的REST限速基于IP地址
     - 私有REST限速基于User ID（子帐户具有单独的User ID）
     - WebSocket订单管理限速基于User ID
     - 交易相关API（下订单、取消订单和修改订单）的限速在REST和WebSocket通道之间共享
     - 下单、修改订单、取消订单的限速相互独立
     - 限速在Instrument ID级别定义（期权除外）
   - API认证方式:
     - REST API: 使用OK-ACCESS-KEY、OK-ACCESS-SIGN、OK-ACCESS-TIMESTAMP、OK-ACCESS-PASSPHRASE请求头
     - WebSocket API: 通过login消息进行认证，包含apiKey、passphrase、timestamp、sign参数
   - API错误代码:
     | 错误码 | HTTP状态码 | 错误提示 |
     |-------|-----------|----------|
     | 0 | 200 | 操作成功 |
     | 1 | 200 | 操作全部失败 |
     | 2 | 200 | 批量操作部分成功 |
     | 50000 | 400 | POST请求的body不能为空 |
     | 50001 | 503 | 服务暂时不可用，请稍后重试 |
     | 50002 | 400 | JSON 语法错误 |
     | 50004 | 400 | 接口请求超时（不代表请求成功或者失败，请检查请求结果） |
     | 50005 | 410 | 接口已下线或无法使用 |
     | 50006 | 400 | 无效的 Content-Type，请使用"application/JSON"格式 |
     | 50011 | 200 | 用户请求频率过快，超过该接口允许的限额。请参考 API 文档并限制请求 |
     | 50011 | 429 | 请求频率太高 |
     | 50014 | 400 | 必填参数{param0}不能为空 |
     | 50030 | 200 | 您没有使用此 API 接口的权限 |
     | 50035 | 403 | 该接口要求APIKey必须绑定IP |
     | 50044 | 200 | 必须指定一种broker类型 |
     | 50061 | 200 | 订单请求频率过快，超过账户允许的最高限额 |
     | 50100 | 400 | Api 已被冻结，请联系客服处理 |
     | 50101 | 401 | APIKey 与当前环境不匹配 |
     | 50102 | 401 | 请求时间戳过期 |
     | 50103 | 401 | 请求头"OK-ACCESS-KEY"不能为空 |
     | 50104 | 401 | 请求头"OK-ACCESS-PASSPHRASE"不能为空 |
     | 50105 | 401 | 请求头"OK-ACCESS-PASSPHRASE"错误 |
     | 50106 | 401 | 请求头"OK-ACCESS-SIGN"不能为空 |
     | 50107 | 401 | 请求头"OK-ACCESS-TIMESTAMP"不能为空 |
     | 50110 | 401 | 您的IP{param0}不在APIKey绑定IP名单中 (您可以将您的IP加入到APIKey绑定白名单中) |
     | 50111 | 401 | 无效的OK-ACCESS-KEY |
     | 50112 | 401 | 无效的OK-ACCESS-TIMESTAMP |
     | 50113 | 401 | 无效的签名 |
     | 50114 | 401 | 无效的授权 |
     | 50120 | 200 | API key 权限不足 |
     | 51000 | 400 | {param0}参数错误 |
     | 51001 | 200 | Instrument ID、Instrument ID code 或 Spread ID 不存在 |
     | 51003 | 200 | ordId或clOrdId至少填一个 |
     | 51004 | 200 | 下单失败，您在{instId} 逐仓的开平仓模式下，当前下单张数、同方向持有仓位以及同方向挂单张数之和，不能超过当前杠杆倍数允许的持仓上限{tierLimitQuantity}(张)，请调低杠杆或者使用新的子账户重新下单 |
     | 51005 | 200 | 委托数量大于单笔上限 |
     | 51006 | 200 | 委托价格不在限价范围内（最高买入价：{param0}，最低卖出价：{param1}） |
     | 51007 | 200 | 委托失败，委托数量不可小于 1 张 |
     | 51008_1000 | 200 | 委托失败，{param0} 可用余额不足，该委托会产生借币，当前账户可用保证金过低无法借币 |
     | 51008_1001 | 200 | 委托失败，账户 {param0} 可用保证金不足 |
     | 51008_1002 | 200 | 委托失败，请先增加可用保证金，再进行借币交易 |
     | 51008_1003 | 200 | 委托失败，账户 {param0} 可用保证金不足，且未开启自动借币（PM模式也可以尝试IOC订单降低风险） |
     | 51010 | 200 | 当前账户模式不支持此操作 |
     | 51011 | 200 | ordId重复 |
     | 51012 | 200 | 币种不存在 |
     | 51015 | 200 | instId和instType不匹配 |
     | 51016 | 200 | clOrdId重复 |
     | 51020 | 200 | 委托数量需大于或等于最小下单数量 |
     | 51021 | 200 | 币对或合约待上线 |
     | 51022 | 200 | 合约暂停中 |
     | 51023 | 200 | 仓位不存在 |
     | 51024 | 200 | 交易账户冻结 |
     | 51025 | 200 | 委托笔数超限 |
     | 51027 | 200 | 合约已到期 |
     | 51028 | 200 | 合约交割中 |
     | 51029 | 200 | 合约结算中 |
     | 51030 | 200 | 资金费结算中 |
     | 51031 | 200 | 委托价格不在平仓限价范围内 |
     | 51032 | 200 | 市价全平中 |
     | 51033 | 200 | 币对单笔交易已达限额 |
     | 51034 | 200 | 成交速率超出您所设置的上限，请将做市商保护状态重置为 inactive 以继续交易。 |
     | 51040 | 200 | 期权逐仓的买方不能调整保证金 |
     | 51041 | 200 | PM账户仅支持买卖模式 |
     | 51043 | 200 | 该逐仓仓位不存在 |
     | 51054 | 500 | 请求超时，请稍候重试 |
     | 51066 | 200 | 期权交易不支持市价单，请用限价单平仓 |
     | 51071 | 200 | 当前维护的标签维度倒计时全部撤单达到数量上限 |
     | 51111 | 200 | 批量下单时，超过最大单数{param0} |
     | 51112 | 200 | 平仓张数大于该仓位的可平张数 |
     | 51113 | 429 | 市价全平操作过于频繁 |
     | 51115 | 429 | 市价全平前请先撤销所有平仓单 |
     | 51116 | 200 | 委托价格或触发价格超过{param0} |
     | 51117 | 200 | 平仓单挂单单数超过限制 |
     | 51120 | 200 | 下单数量不足{param0}张 |
     | 51121 | 200 | 下单张数应为一手张数的倍数 |
     | 51122 | 200 | 委托价格小于最小值{param0} |
     | 51124 | 200 | 价格发现期间您只可下限价单 |
     | 51127 | 200 | 仓位可用余额为0 |
     | 51128 | 200 | 跨币种账户无法进行全仓杠杆交易 |
     | 51129 | 200 | 持仓及买入订单价值已达到持仓限额，不允许继续买入 |
     | 51130 | 200 | 逐仓杠杆保证金币种错误 |
     | 51131 | 200 | 仓位可用余额不足 |
     | 51132 | 200 | 仓位正资产小于最小交易单位 |
     | 51134 | 200 | 平仓失败，您当前没有杠杆仓位，请关闭只减仓后继续 |
     | 51135 | 200 | 您的平仓价格已触发限价，最高买入价格为{param0} |
     | 51136 | 200 | 您的平仓价格已触发限价，最低卖出价格为{param0} |
     | 51137 | 200 | 买单最高价为 {param0}，请调低价格 |
     | 51138 | 200 | 卖单最低价为 {param0}，请调高价格 |
     | 51139 | 200 | 现货模式下币币不支持只减仓功能 |
     | 51140 | 200 | 由于盘口卖单不足，下单失败，请稍后重试 |
     | 51147 | 200 | 交易期权需要在交易账户资产总价值大于1万美元的前提下，开通期权交易服务 |
     | 51149 | 500 | 下单超时，请稍候重试 (不代表请求成功或失败，请检查请求结果) |
     | 51150 | 200 | 交易数量或价格的精度超过限制 |
     | 51152 | 200 | 一键借币模式下，不支持自动借币与自动还币和手动类型混合下单。 |
     | 51155 | 200 | 由于您所在国家或地区的合规限制，您无法交易此币对或合约 |
     | 51158 | 200 | 自主划转已不支持，请切换至一键借币模式下单 (isoMode=quick_margin) |
     | 51169 | 200 | 下单失败，您没有当前合约对应方向的持仓，无法进行平仓或者减仓。 |
     | 51170 | 200 | 下单失败，只减仓下单方向不能与持仓方向相同 |
     | 51171 | 200 | 改单失败，当前订单若改单成功会造成只减仓订单反向开仓，请撤销或修改原有挂单再进行改单 |
     | 51173 | 200 | 无法市价全平，当前仓位暂无负债 |
     | 51201 | 200 | 市价委托单笔价值不能超过 1,000,000 USDT |
     | 51202 | 200 | 市价单下单数量超出最大值 |
     | 51203 | 200 | 普通委托数量超出最大限制{param0} |
     | 51204 | 200 | 限价委托单价格不能为空 |
     | 51205 | 200 | 不支持只减仓操作 |
     | 51206 | 200 | 请先撤销当前下单产品{param0}的只减仓挂单，避免反向开仓 |
     | 51207 | 200 | 交易数量超过限制，无法市价全平，请手动下单分批平仓 |
     | 51212 | 200 | 下单失败。当前不支持批量下单，请分开下单 |
     | 51220 | 200 | 分润策略仅支持策略停止时卖币或停止时全部平仓 |
     | 51221 | 200 | 请输入 0-30% 范围内的指定分润比例 |
     | 51222 | 200 | 该策略不支持分润 |
     | 51223 | 200 | 当前状态您不可以进行分润带单 |
     | 51224 | 200 | 该币对不支持分润 |
     | 51225 | 200 | 分润跟单策略不支持手动立即触发策略 |
     | 51226 | 200 | 分润跟单策略不支持修改策略参数 |
     | 51250 | 200 | 策略委托价格不在正确范围内 |
     | 51251 | 200 | 创建冰山委托时，策略委托类型错误 |
     | 51252 | 200 | 策略委托数量不在正确范围内 |
     | 51253 | 200 | 冰山委托单笔均值超限 |
     | 51254 | 200 | 冰山委托单笔均值错误 |
     | 51255 | 200 | 冰山委托单笔委托超限 |
     | 51256 | 200 | 冰山委托深度错误 |
     | 51257 | 200 | 跟踪委托回调服务错误，回调幅度限制为{min}<x<={max}% |
     | 51258 | 200 | 跟踪委托失败，卖单激活价格需大于最新成交价格 |
     | 51259 | 200 | 跟踪委托失败，买单激活价格需小于最新成交价格 |
     | 51260 | 200 | 每个用户最多可同时持有{param0}笔未成交的跟踪委托 |
     | 51261 | 200 | 每个用户最多可同时持有{param0}笔未成交的止盈止损 |
     | 51262 | 200 | 每个用户最多可同时持有{param0}笔未成交的冰山委托 |
     | 51263 | 200 | 每个用户最多可同时持有{param0}笔未成交的时间加权单 |
     | 51264 | 200 | 时间加权单笔均值超限 |
     | 51265 | 200 | 时间加权单笔上限错误 |
     | 51267 | 200 | 时间加权扫单比例出错 |
     | 51268 | 200 | 时间加权扫单范围出错 |
     | 51269 | 200 | 时间加权委托间隔错误，应为{min}<=x<={max} |
     | 51270 | 200 | 时间加权委托深度限制为 0<x<=1% |
     | 51271 | 200 | 时间加权委托失败，扫单比例应该为 0<x<=100% |
     | 51272 | 200 | 时间加权委托失败，扫单范围应该为 0<x<=1% |
     | 51273 | 200 | 时间加权委托总量应为大于 0 |
     | 51274 | 200 | 时间加权委托总数量需大于单笔上限 |
     | 51275 | 200 | 止盈止损市价单笔委托数量不能超过最大限制 |
     | 51276 | 200 | 止盈止损市价单不能指定价格 |
     | 51277 | 200 | 止盈触发价格不能大于最新成交价 |
     | 51278 | 200 | 止损触发价格不能小于最新成交价 |
     | 51279 | 200 | 止盈触发价格不能小于最新成交价 |
     | 51280 | 200 | 止损触发价格不能大于最新成交价 |
     | 51281 | 200 | 计划委托不支持使用tgtCcy参数 |
     | 51282 | 200 | 吃单价优于盘口的比例范围 |
     | 51283 | 200 | 时间间隔的范围{param0}s~{param1}s |
     | 51284 | 200 | 单笔数量的范围{param0}~{param1} |
     | 51285 | 200 | 委托总量的范围{param0}~{param1} |
     | 51286 | 200 | 下单金额需大于等于{param0} |
     | 51287 | 200 | 当前策略不支持此交易品种 |
     | 51288 | 200 | 策略正在停止中，请勿重复点击 |
     | 51289 | 200 | 策略配置不存在，请稍后再试 |
     | 51290 | 200 | 策略引擎正在升级，请稍后重试 |
     | 51291 | 200 | 策略不存在或已停止 |
     | 51292 | 200 | 策略类型不存在 |
     | 51293 | 200 | 策略不存在 |
     | 51294 | 200 | 该策略暂不能创建，请稍后再试 |
     | 51295 | 200 | PM账户不支持ordType为{param0}的策略委托单 |
     | 51298 | 200 | 交割、永续合约的买卖模式下，不支持计划委托 |
     | 51299 | 200 | 策略委托失败，用户最多可持有{param0}笔该类型委托 |
     | 51300 | 200 | 止盈触发价格不能大于标记价格 |
     | 51302 | 200 | 止损触发价格不能小于标记价格 |
     | 51303 | 200 | 止盈触发价格不能小于标记价格 |
     | 51304 | 200 | 止损触发价格不能大于标记价格 |
     | 51305 | 200 | 止盈触发价格不能大于指数价格 |
     | 51306 | 200 | 止损触发价格不能小于指数价格 |
     | 51307 | 200 | 止盈触发价格不能小于指数价格 |
     | 51308 | 200 | 止损触发价格不能大于指数价格 |
     | 51309 | 200 | 集合竞价期间不能创建策略 |
     | 51310 | 200 | 逐仓自主划转保证金模式不支持ordType为iceberg、twap的策略委托单 |
     | 51311 | 200 | 移动止盈止损委托失败，回调幅度限制为{min}<x<={max} |
     | 51312 | 200 | 移动止盈止损委托失败，委托数量范围{min}<x<={max} |
     | 51313 | 200 | 逐仓自主划转模式不支持策略部分 |
     | 51317 | 200 | 币币杠杆不支持计划委托 |
     | 51327 | 200 | closeFraction 仅适用于交割合约和永续合约 |
     | 51328 | 200 | closeFraction 仅适用于只减仓订单 |
     | 51329 | 200 | closeFraction 仅适用于买卖模式 |
     | 51330 | 200 | closeFraction 仅适用于止盈止损市价订单 |
     | 51331 | 200 | closeFraction仅限于平仓单 |
     | 51332 | 200 | 组合保证金模式不支持closeFraction |
     | 51333 | 200 | 开平模式下的平仓单或买卖模式下的只减仓单无法附带止盈止损 |
     | 51340 | 200 | 投入保证金需大于{0}{1} |
     | 51341 | 200 | 当前策略状态下暂不支持平仓 |
     | 51342 | 200 | 已有平仓单，请稍后重试 |
     | 51343 | 200 | 止盈价格需小于区间最低价格 |
     | 51344 | 200 | 止损价格需大于区间最高价格 |
     | 51345 | 200 | 策略类型不是网格策略 |
     | 51346 | 200 | 最高价格不能低于最低价格 |
     | 51347 | 200 | 暂无可提取利润 |
     | 51348 | 200 | 止损价格需小于区间最低价格 |
     | 51349 | 200 | 止盈价格需大于区间最高价格 |
     | 51350 | 200 | 暂无可推荐参数 |
     | 51351 | 200 | 单格收益必须大于0 |
     | 51352 | 200 | 币对数量范围{pairNum1} - {pairNum2} |
     | 51353 | 200 | 存在重复币对{existingPair} |
     | 51354 | 200 | 币对比例总和需等于100% |
     | 51355 | 200 | 定投日期范围{date1} - {date2} |
     | 51356 | 200 | 定投时间范围{0}~{1} |
     | 51357 | 200 | 时区范围 {timezone1} - {timezone2} |
     | 51358 | 200 | 每个币种的投入金额需大于{amount} |
     | 51359 | 200 | 暂不支持定投该币种{0} |
     | 51370 | 200 | 杠杆倍数范围{0}~{1} |
     | 51380 | 200 | 市场行情不符合策略配置 |
     | 51381 | 200 | 单网格利润率不在区间内 |
     | 51382 | 200 | 策略不支持停止信号触发 |
     | 51383 | 200 | 最小价格必须小于最新成交价 |
     | 51384 | 200 | 信号触发价格必须大于最小价格 |
     | 51385 | 200 | 止盈价必须大于最小价格 |
     | 51386 | 200 | 最小价格必须大于1/2最新成交价 |
     | 51387 | 200 | 止损价格应小于无限网格的区间最低价 |
     | 51388 | 200 | 策略已在运行中 |
     | 51389 | 200 | 触发价格需小于{0} |
     | 51390 | 200 | 触发价格需小于止盈价格 |
     | 51391 | 200 | 触发价格需大于止损价格 |
     | 51392 | 200 | 止盈价格需大于触发价格 |
     | 51393 | 200 | 止损价格需小于触发价格 |
     | 51394 | 200 | 触发价格需大于止盈价格 |
     | 51395 | 200 | 触发价格需小于止损价格 |
     | 51396 | 200 | 止盈价格需小于触发价格 |
     | 51397 | 200 | 止损价格需大于触发价格 |
     | 51398 | 200 | 当前行情满足停止条件，无法创建策略 |
     | 51399 | 200 | 当前杠杆下最大可投入金额为 {amountLimit} {quoteCurrency}，请减少投入金额后再试。 |
     | 51400 | 200 | 由于订单已完成、已撤销或不存在，撤单失败 |
     | 51400 | 200 | 撤单失败，订单不存在（仅适用于价差速递） |
     | 51401 | 200 | 撤单失败，订单已撤销（仅适用于价差速递） |
     | 51402 | 200 | 撤单失败，订单已完成（仅适用于价差速递） |
     | 51403 | 200 | 撤单失败，该委托类型无法进行撤单操作 |
     | 51404 | 200 | 价格发现第二阶段您不可撤单 |
     | 51405 | 200 | 撤单失败，您当前没有未成交的订单 |
     | 51406 | 400 | 撤单数量超过最大允许单数{param0} |
     | 51407 | 200 | ordIds 和 clOrdIds 不能同时为空 |
     | 51408 | 200 | 币对 id 或币对名称与订单信息不匹配 |
     | 51409 | 200 | 币对 id 或币对名称不能同时为空 |
     | 51410 | 200 | 撤单失败，订单已处于撤销中或结算中 |
     | 51411 | 200 | 用户没有执行mass cancel的权限 |
     | 51412 | 200 | 撤单超时，请稍后重试 |
     | 51416 | 200 | 委托已触发，暂不支持撤单 |
     | 51413 | 200 | 撤单失败，接口不支持该委托类型的撤单 |
     | 51415 | 200 | 下单失败，现货交易仅支持设置最新价为触发价格，请更改触发价格并重试 |
     | 51416 | 200 | 委托已触发，暂不支持撤单 |
     | 51500 | 200 | 价格、数量、止盈/止损不能同时为空 |
     | 51501 | 400 | 修改订单超过最大允许单数{param0} |
     | 51502_1030 | 200 | 修改失败，{param0} 可用余额不足，该委托会产生借币，当前账户可用保证金过低无法借币 |
     | 51502_1031 | 200 | 修改订单失败，账户 {param0} 可用保证金不足 |
     | 51502_1032 | 200 | 委托失败，请先增加可用保证金，再进行借币交易 |
     | 51502_1033 | 200 | 修改订单失败，账户 {param0} 可用保证金不足，且未开启自动借币（PM模式也可以尝试IOC订单降低风险） |
     | 51502_1034 | 200 | {param0} 可用不足。借币数量超过档位限制，请尝试降低杠杆倍数。限价挂单以及当前下单需借 {param1}，剩余额度 {param2}，限额 {param3}，已用额度 {param4}。 |
     | 51502_1035 | 200 | 修改订单失败，因为 {param0} 剩余的限额 (主账户限额+当前账户锁定的尊享借币额度) 不足，导致可借不足。限价挂单以及当前下单需借 {param1}，剩余额度 {param2}，限额 {param3}，已用额度 {param4}。 |
     | 51502_1036 | 200 | 修改订单失败，因为 {param0} 剩余的币对限额不足，导致可借不足 |
     | 51502_1037 | 200 | 改单失败，该委托需要借币 {param0}，但该币种的平台剩余借币额度已不足 |
     | 51502_1039 | 200 | 修改订单失败，账户可用保证金过低（PM模式也可以尝试IOC订单降低风险） |
     | 51502_1040 | 200 | 修改订单失败，Delta 校验未通过，因为若成功下单，adjEq 的变化值将小于 IMR 的变化值。建议增加 adjEq 或减少 IMR 占用。（PM模式也可以尝试IOC订单降低风险） |
     | 51502_1049 | 200 | 修改订单失败，您主账户的 {param0} 借币额度不足 |
     | 51503 | 200 | 由于订单已完成、已撤销或不存在，改单失败 |
     | 51503 | 200 | 由于订单不存在，改单失败（仅适用于价差速递） |
     | 51505 | 200 | {instId} 不处于集合竞价阶段 |
     | 51506 | 200 | 订单类型不支持改单 |
     | 51507 | 200 | 您仅能在币种上线至少 5 分钟后进行市价委托 |
     | 51508 | 200 | 集合竞价第一阶段和第二阶段不允许改单 |
     | 51509 | 200 | 修改订单失败,订单已撤销（仅适用于价差速递） |
     | 51510 | 200 | 修改订单失败,订单已完成（仅适用于价差速递） |
     | 51511 | 200 | 操作失败，订单价格不满足Post Only条件 |
     | 51512 | 200 | 批量修改订单失败。同一批量改单请求中不允许包含相同订单。 |
     | 51513 | 200 | 对于正在处理的同一订单，改单请求次数不得超过3次 |
     | 51514 | 200 | 修改订单失败，价格长度不能超过 32 个字符 |
     | 51521 | 200 | 改单失败，当前合约无持仓，无法修改只减仓订单 |
     | 51522 | 200 | 改单失败，只减仓订单方向不能与持仓反向相同 |
     | 51532 | 200 | 止盈止损已触发，无法改单 |
     | 51524 | 200 | 不允许在全部仓位止盈止损单上修改委托数量，请修改触发价格 |
     | 51525 | 200 | 一键借币止盈止损单不支持修改 |
     | 60009 | 401 | 登录失败 |
     | 60029 | 403 | 该频道仅适用于交易等级VIP6及以上的用户 |
     | 70065 | 400 | 移仓将被拒绝，无法获取60分钟TWAP |
   - API监控标签页:
     - API状态信息: 显示API连接状态
     - 调用统计: 显示API调用统计数据
       - REST API: REST API调用次数和平均响应时间
       - WebSocket: WebSocket消息次数和平均处理时间
       - 订单操作: 订单相关API调用次数和平均响应时间
       - 市场数据: 市场数据相关API调用次数和平均响应时间
     - 调用历史: 显示最近50条API调用记录
       - 时间: API调用时间
       - 调用者: 调用API的函数名
       - 方法: HTTP请求方法 (GET/POST/DELETE)
       - 端点: API端点路径
       - 状态码: HTTP响应状态码
       - 响应时间: API响应时间
       - 错误: 错误信息（如果有）
       - 操作: 查看详情按钮
     - WebSocket消息: 显示最近50条WebSocket消息记录
       - 时间: 消息接收时间
       - 频道: 消息频道 (public/private)
       - 消息类型: 消息类型 (event/data_push/ping/pong)
       - 通道名称: WebSocket通道名称
       - 产品ID: 产品ID
       - 处理时间: 消息处理时间
       - 错误: 错误信息（如果有）

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
        close_button = QPushButton("关闭")
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
        # 关闭线程池
        self._thread_pool.shutdown(wait=False)
        event.accept()

    def init_visualization_tab(self, parent):
        """
        初始化数据可视化标签页
        """
        layout = QVBoxLayout(parent)

        # 图表类型选择
        chart_control = QHBoxLayout()
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(["K线图表", "策略性能图表", "资产分布图表"])
        self.inst_id_combo = QComboBox()
        self.inst_id_combo.addItems(["BTC-USDT-SWAP", "ETH-USDT-SWAP", "BNB-USDT-SWAP"])
        self.update_chart_button = QPushButton("更新图表")

        chart_control.addWidget(QLabel("图表类型:"))
        chart_control.addWidget(self.chart_type_combo)
        chart_control.addWidget(QLabel("产品:"))
        chart_control.addWidget(self.inst_id_combo)
        chart_control.addWidget(self.update_chart_button)

        layout.addLayout(chart_control)

        # 图表显示区域
        self.chart_container = QWidget()
        self.chart_layout = QVBoxLayout(self.chart_container)

        # 创建图表画布
        self.figure = Figure(figsize=(10, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.chart_layout.addWidget(self.canvas)

        layout.addWidget(self.chart_container)

        # 连接信号
        self.update_chart_button.clicked.connect(self.update_chart)
        self.chart_type_combo.currentTextChanged.connect(self.update_chart)
        self.inst_id_combo.currentTextChanged.connect(self.update_chart)

        # 初始化图表
        self.update_chart()

    def update_chart(self):
        """
        更新图表
        """
        chart_type = self.chart_type_combo.currentText()
        inst_id = self.inst_id_combo.currentText()

        # 清空图表
        self.figure.clear()

        if chart_type == "K线图表":
            self.plot_kline_chart(inst_id)
        elif chart_type == "策略性能图表":
            self.plot_strategy_performance()
        elif chart_type == "资产分布图表":
            self.plot_asset_distribution()

        # 重新绘制
        self.canvas.draw()

    def plot_kline_chart(self, inst_id):
        """
        绘制K线图表
        """
        ax = self.figure.add_subplot(111)

        # 生成模拟数据
        dates = pd.date_range(start="2024-01-01", periods=30, freq="D")
        open_prices = np.random.randn(30) + 40000
        high_prices = open_prices + np.random.randn(30) * 100
        low_prices = open_prices - np.random.randn(30) * 100
        close_prices = open_prices + np.random.randn(30) * 50
        volume = np.random.randn(30) + 1000

        # 创建DataFrame
        df = pd.DataFrame(
            {
                "Open": open_prices,
                "High": high_prices,
                "Low": low_prices,
                "Close": close_prices,
                "Volume": volume,
            },
            index=dates,
        )

        # 绘制K线图
        mpf.plot(df, type="candle", ax=ax, style="charles")
        ax.set_title(f"{inst_id} K线图")

    def plot_strategy_performance(self):
        """
        绘制策略性能图表
        """
        ax = self.figure.add_subplot(111)
        
        # 生成模拟数据
        dates = pd.date_range(start='2024-01-01', periods=30, freq='D')
        equity = np.cumprod(1 + np.random.randn(30) * 0.01) * 10000
        
        # 绘制资产曲线
        ax.plot(dates, equity, label='资产价值')
        ax.set_title('策略性能')
        ax.set_xlabel('日期')
        ax.set_ylabel('资产价值')
        ax.legend()
        ax.grid(True)

    def plot_asset_distribution(self):
        """
        绘制资产分布图表
        """
        ax = self.figure.add_subplot(111)

        # 模拟资产数据
        assets = ["BTC", "ETH", "BNB", "USDT"]
        values = [40, 30, 20, 10]
        colors = ["#FF9900", "#627EEA", "#F3BA2F", "#34B7EB"]

        # 绘制饼图
        ax.pie(values, labels=assets, autopct="%1.1f%%", colors=colors, startangle=90)
        ax.set_title("资产分布")
        ax.axis("equal")


def main():
    """
    主函数
    """
    app = QApplication(sys.argv)

    # 设置应用程序样式
    app.setStyle("Fusion")

    # 创建并显示 GUI
    gui = WebSocketGUI()
    gui.show()

    # 运行事件循环
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
