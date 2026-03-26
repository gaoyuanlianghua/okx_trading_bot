import sys
import json
import threading
import time
import os

# 禁用Qt样式表警告和其他Qt警告
os.environ["QT_LOGGING_RULES"] = "*.warning=false;qt.qpa.style.warning=false"

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget,
    QLabel, QPushButton, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QSplitter, QGroupBox, QFormLayout, QSpinBox, QDoubleSpinBox, QCheckBox,
    QTextEdit, QHeaderView, QFrame, QDialog, QScrollArea, QMessageBox, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor

# 尝试导入mplfinance和matplotlib
try:
    import mplfinance as mpf
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

# 统一的样式表
UNIFIED_STYLESHEET = """
/* 主窗口样式 */
QMainWindow {
    background-color: #f5f7fa;
    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
    font-size: 10px;
}

/* 标签页样式 */
QTabWidget {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    padding: 2px;
}

QTabBar {
    background-color: transparent;
}

QTabBar::tab {
    background-color: #f8f9fa;
    padding: 6px 10px;
    border: 1px solid #e0e0e0;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
    min-width: 70px;
    font-weight: 500;
    font-size: 10px;
}

QTabBar::tab:hover {
    background-color: #e9ecef;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    border-bottom: 1px solid #ffffff;
    font-weight: 600;
}

/* 分组框样式 */
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    margin-top: 6px;
    padding-top: 4px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px 0 4px;
    font-weight: 600;
    color: #2c3e50;
    font-size: 10px;
}

/* 按钮样式 */
QPushButton {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 3px;
    padding: 4px 8px;
    font-weight: 500;
    font-size: 10px;
    min-height: 24px;
    min-width: 60px;
}

QPushButton:hover {
    background-color: #f8f9fa;
    border-color: #d0d0d0;
}

QPushButton:pressed {
    background-color: #e9ecef;
}

/* 特殊按钮样式 */
QPushButton#primary {
    background-color: #3b82f6;
    color: white;
    border-color: #3b82f6;
    font-weight: 600;
}

QPushButton#primary:hover {
    background-color: #2563eb;
    border-color: #2563eb;
}

QPushButton#primary:pressed {
    background-color: #1d4ed8;
}

QPushButton#secondary {
    background-color: #64748b;
    color: white;
    border-color: #64748b;
    font-weight: 600;
}

QPushButton#secondary:hover {
    background-color: #475569;
    border-color: #475569;
}

QPushButton#warning {
    background-color: #f59e0b;
    color: white;
    border-color: #f59e0b;
    font-weight: 600;
}

QPushButton#warning:hover {
    background-color: #d97706;
    border-color: #d97706;
}

QPushButton#danger {
    background-color: #ef4444;
    color: white;
    border-color: #ef4444;
    font-weight: 600;
}

QPushButton#danger:hover {
    background-color: #dc2626;
    border-color: #dc2626;
}

/* 输入框样式 */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 3px;
    padding: 3px 6px;
    font-size: 10px;
    min-height: 24px;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 2px solid #3b82f6;
    outline: none;
}

/* 表格样式 */
QTableWidget {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 3px;
    gridline-color: #f0f0f0;
    font-size: 9px;
}

QTableWidget::item {
    padding: 4px 6px;
    border-bottom: 1px solid #f8f9fa;
}

QTableWidget::item:hover {
    background-color: #f8f9fa;
}

QTableWidget::item:selected {
    background-color: #dbeafe;
    color: #1e40af;
}

QHeaderView::section {
    background-color: #f8f9fa;
    padding: 4px 6px;
    border: 1px solid #e0e0e0;
    font-weight: 600;
    color: #2c3e50;
    border-top-left-radius: 3px;
    border-top-right-radius: 3px;
    font-size: 9px;
}

QHeaderView::section:hover {
    background-color: #e9ecef;
}

/* 文本编辑框样式 */
QTextEdit {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 3px;
    padding: 6px;
    font-size: 10px;
    line-height: 1.3;
}

QTextEdit[readOnly="true"] {
    background-color: #f8f9fa;
    color: #64748b;
}

/* 标签样式 */
QLabel {
    color: #2c3e50;
    font-size: 10px;
}

QLabel#status {
    font-weight: 600;
}

QLabel#success {
    color: #10b981;
    font-weight: 600;
}

QLabel#warning {
    color: #f59e0b;
    font-weight: 600;
}

QLabel#error {
    color: #ef4444;
    font-weight: 600;
}

/* 控制栏样式 */
QWidget#controlBar {
    background-color: #ffffff;
    border-bottom: 1px solid #e0e0e0;
    padding: 6px;
}

/* 滚动条样式 */
QScrollBar:vertical {
    background-color: #f8f9fa;
    width: 4px;
    border-radius: 2px;
}

QScrollBar::handle:vertical {
    background-color: #cbd5e1;
    border-radius: 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: #94a3b8;
}

QScrollBar:horizontal {
    background-color: #f8f9fa;
    height: 4px;
    border-radius: 2px;
}

QScrollBar::handle:horizontal {
    background-color: #cbd5e1;
    border-radius: 2px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #94a3b8;
}

/* 分隔器样式 */
QSplitter::handle {
    background-color: #e0e0e0;
    width: 2px;
    height: 2px;
}

QSplitter::handle:hover {
    background-color: #cbd5e1;
}

/* 对话框样式 */
QDialog {
    background-color: #ffffff;
    border-radius: 4px;
    font-size: 10px;
}

/* 表单布局样式 */
QFormLayout {
    spacing: 4px;
}

/* 表格列宽调整 */
QTableWidget QHeaderView {
    font-size: 9px;
}
"""

# 初始化日志配置
from commons.logger_config import global_logger as logger

# Import our custom modules
from okx_api_client import OKXAPIClient
from services.market_data.market_data_service import MarketDataService
from services.order_management.order_manager import OrderManager
from services.risk_management.risk_manager import RiskManager
from strategies.dynamics_strategy import DynamicsStrategy

class HelpDialog(QDialog):
    """Help dialog for OKX Trading Bot"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OKX 交易机器人 - 帮助")
        self.setGeometry(100, 100, 800, 600)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Create scroll area for long content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        # Content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # Introduction
        intro_label = QLabel("<h2>OKX 交易机器人使用说明</h2>")
        intro_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(intro_label)
        
        # 功能介绍
        features_group = QGroupBox("主要功能")
        features_layout = QVBoxLayout(features_group)
        features_text = QTextEdit()
        features_text.setReadOnly(True)
        features_text.setPlainText("""1. 基于 PyQt5 的图形用户界面
2. OKX REST API 和 WebSocket 客户端支持
3. WebSocket 连接管理和自动重连
4. 集中式配置管理
5. 增强的日志记录
6. 健康检查机制
7. 指数退避重试机制
8. 策略管理和执行
9. 策略添加功能
10. 智能体系统集成""")
        features_layout.addWidget(features_text)
        content_layout.addWidget(features_group)
        
        # 快速开始
        quickstart_group = QGroupBox("快速开始")
        quickstart_layout = QVBoxLayout(quickstart_group)
        quickstart_text = QTextEdit()
        quickstart_text.setReadOnly(True)
        quickstart_text.setPlainText("""1. 进入"配置管理"标签页
2. 输入您的 OKX API 密钥、密钥密码和密码短语
3. 点击"保存配置"按钮
4. 切换到"交易"标签页
5. 选择交易对和模式
6. 点击"更新数据"按钮获取实时行情
7. 配置交易参数并点击"下单"按钮执行交易
8. 在"策略管理"标签页中配置和启动交易策略
9. 点击"添加策略"按钮添加自定义策略
10. 系统会在启动时自动加载功能，无需手动点击"加载功能"按钮""")
        quickstart_layout.addWidget(quickstart_text)
        content_layout.addWidget(quickstart_group)
        
        # 配置说明
        config_group = QGroupBox("配置说明")
        config_layout = QVBoxLayout(config_group)
        config_text = QTextEdit()
        config_text.setReadOnly(True)
        config_text.setPlainText("""API 配置：
- API Key: OKX 交易所的 API 密钥
- API Secret: OKX 交易所的 API 密钥密码
- Passphrase: OKX 交易所的密码短语
- API URL: OKX 交易所的 API 地址
- 超时时间: API 请求的超时时间（秒）
- 环境切换: 支持在测试网和主网之间切换

注意：系统已移除所有代理相关功能，只保留基本 API 调用方式""")
        config_layout.addWidget(config_text)
        content_layout.addWidget(config_group)
        
        # 策略说明
        strategy_group = QGroupBox("策略说明")
        strategy_layout = QVBoxLayout(strategy_group)
        strategy_text = QTextEdit()
        strategy_text.setReadOnly(True)
        strategy_text.setPlainText("""1. 原子核互反动力学策略
   - 基于市场波动的动态网格策略
   - 支持多时间周期
   - 自动调整网格间距和倍数

2. passivbot_grid
   - 被动网格策略
   - 适合震荡市场
   - 低风险低收益

3. passivbot_trailing
   - 跟踪止损策略
   - 适合趋势市场
   - 能够锁定利润

4. 自定义策略
   - 点击"添加策略"按钮添加自定义策略
   - 需要提供策略名称、策略类名和模块路径
   - 自定义策略需要继承自BaseStrategy类
   - 示例模块路径：strategies.my_strategy""")
        strategy_layout.addWidget(strategy_text)
        content_layout.addWidget(strategy_group)
        
        # 常见问题
        faq_group = QGroupBox("常见问题")
        faq_layout = QVBoxLayout(faq_group)
        faq_text = QTextEdit()
        faq_text.setReadOnly(True)
        faq_text.setPlainText("""Q: 连接失败怎么办？
A: 检查 API 密钥是否正确，检查网络连接，检查防火墙设置。

Q: GUI 冻结怎么办？
A: 等待一段时间，机器人会自动恢复，或尝试重启程序。

Q: WebSocket 断开怎么办？
A: 机器人会自动重连，检查网络稳定性。

Q: 如何查看日志？
A: 进入"日志"标签页查看实时日志，日志文件位于 logs/ 目录下。

Q: 如何切换环境？
A: 在"网络状态"标签页中点击"测试网"或"主网"按钮切换环境。

Q: 如何添加自定义策略？
A: 点击"添加策略"按钮，在弹出的对话框中输入策略名称、策略类名和模块路径，然后点击"添加"按钮。

Q: 为什么没有"加载功能"按钮？
A: 系统现在会在启动时自动加载功能，无需手动点击按钮。

Q: 为什么没有代理设置选项？
A: 系统已移除所有代理相关功能，只保留基本 API 调用方式。""")
        faq_layout.addWidget(faq_text)
        content_layout.addWidget(faq_group)
        
        # 联系方式
        contact_group = QGroupBox("联系方式")
        contact_layout = QVBoxLayout(contact_group)
        contact_text = QTextEdit()
        contact_text.setReadOnly(True)
        contact_text.setPlainText("""如有问题或建议，请通过 GitHub Issues 提交。

GitHub 仓库：https://github.com/yourusername/okx_trading_bot

更新日志：
- v1.0.0: 初始版本，支持 OKX REST API 和 WebSocket，Socks5 代理支持，PyQt5 GUI 界面，集中式配置管理，增强的日志记录，健康检查机制
- v1.1.0: 移除代理功能，只保留基本 API 调用方式，添加策略添加功能
- v1.2.0: 移除"加载功能"按钮，系统启动时自动加载功能，优化智能体系统集成""")
        contact_layout.addWidget(contact_text)
        content_layout.addWidget(contact_group)
        
        # Set scroll area content
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # Add close button
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.close)
        main_layout.addWidget(close_button, alignment=Qt.AlignRight)

class ConfigFileHandler(FileSystemEventHandler):
    """Watchdog event handler for configuration file changes with debounce"""
    
    def __init__(self, gui_instance):
        self.gui_instance = gui_instance
        self.debounce_timer = None
        self.debounce_delay = 1.0  # 1秒防抖延迟
        self.last_modified_time = 0
        self.retry_count = 0
        self.max_retry = 3
        self.is_loading = False  # 防止并发加载
        self.last_config_content = None  # 保存上次配置内容，用于检测变化
    
    def get_file_content(self, file_path):
        """获取文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.gui_instance.log(f"读取配置文件失败: {e}")
            return None
    
    def check_content_changed(self):
        """检查配置文件内容是否变化"""
        config_path = "d:\Projects\okx_trading_bot\config\okx_config.json"
        current_content = self.get_file_content(config_path)
        
        # 如果获取内容失败，返回False，不重新加载
        if current_content is None:
            return False
        
        # 如果是第一次加载，保存内容并返回True
        if self.last_config_content is None:
            self.last_config_content = current_content
            return True
        
        # 比较当前内容与上次保存的内容
        if current_content != self.last_config_content:
            self.last_config_content = current_content
            return True
        
        return False
    
    def on_modified(self, event):
        """Handle file modification events with debounce"""
        if event.is_directory:
            return
        
        # Check if the modified file is our configuration file
        config_path = "d:\Projects\okx_trading_bot\config\okx_config.json"
        if event.src_path == config_path:
            current_time = time.time()
            
            # 立即更新最后修改时间
            self.last_modified_time = current_time
            
            # 防抖机制：如果有活跃的定时器，取消它并重新设置
            if self.debounce_timer and self.debounce_timer.is_alive():
                self.debounce_timer.cancel()
            
            # 设置新的定时器，延迟后重新加载
            self.debounce_timer = threading.Timer(self.debounce_delay, self.reload_config)
            self.debounce_timer.daemon = True
            self.debounce_timer.start()
    
    def reload_config(self):
        """Reload configuration with retry mechanism"""
        try:
            self.is_loading = True
            
            # 检查配置文件内容是否真的变化
            if not self.check_content_changed():
                self.gui_instance.log("配置文件内容未变化，跳过重新加载")
                return
            
            # 内容已经变化，重新加载配置
            self.gui_instance.log("检测到配置文件变化，重新加载配置...")
            self.gui_instance.load_config_file()
            
            # 重置重试计数
            self.retry_count = 0
        except Exception as e:
            self.gui_instance.log(f"重新加载配置失败: {e}")
            self.retry_count += 1
            
            # 如果重试次数未达到最大值，则延迟后重试
            if self.retry_count < self.max_retry:
                self.gui_instance.log(f"{self.retry_count}秒后重试加载配置...")
                self.debounce_timer = threading.Timer(self.retry_count, self.reload_config)
                self.debounce_timer.daemon = True
                self.debounce_timer.start()
            else:
                self.gui_instance.log(f"重新加载配置失败，已达到最大重试次数: {self.max_retry}")
                # 重置重试计数
                self.retry_count = 0
        finally:
            self.is_loading = False

class TradingGUI(QMainWindow):
    """OKX Trading Bot GUI Interface"""
    
    # Signal to update GUI from background threads
    update_ticker = pyqtSignal(dict)
    update_order_book = pyqtSignal(dict)
    update_orders = pyqtSignal(list)
    update_positions = pyqtSignal(list)
    update_balance = pyqtSignal(dict)
    update_log = pyqtSignal(str)
    
    def __init__(self, config, trading_bot):
        super().__init__()
        self.setWindowTitle("OKX交易机器人")
        self.setGeometry(100, 100, 1200, 800)
        
        # 应用统一的样式表
        self.setStyleSheet(UNIFIED_STYLESHEET)
        
        # GUI状态标志位，用于线程安全检查
        self.is_closed = False
        
        # Initialize timer for data updates
        self.timer = QTimer()
        self.timer.setInterval(5000)  # 5秒更新一次
        self.timer.timeout.connect(self.update_all_data)
        
        # Load configuration
        self.config = config
        self.trading_bot = trading_bot
        self.last_config_content = None  # 保存上次配置内容，用于检测变化
        
        # 先初始化UI，确保界面能够快速显示
        self.init_ui()
        
        # Connect signals
        self.connect_signals()
        
        # Start with BTC-USDT-SWAP as default symbol
        self.symbol_combo.setCurrentText("BTC-USDT-SWAP")
        
        # 初始化配置文件监控
        self.init_config_monitor()
        
        # 初始化网络状态监控
        self.init_network_monitoring()
        
        # 启动数据更新定时器
        self.timer.start()
        
        # 注意：智能体系统交互和服务初始化将在用户点击"加载功能"按钮后进行
    
    def init_ui(self):
        """Initialize the main UI"""
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # Top control bar
        self.init_control_bar(main_layout)
        
        # Tab widget for main content
        self.tab_widget = QTabWidget()
        
        # Trading tab
        self.init_trading_tab()
        
        # Strategy tab
        self.init_strategy_tab()
        
        # Account tab
        self.init_account_tab()
        
        # Log tab
        self.init_log_tab()
        
        # Config tab
        self.init_config_tab()
        
        # Network status tab
        self.init_network_status_tab()
        
        main_layout.addWidget(self.tab_widget)
        self.setCentralWidget(main_widget)
        
        # 设置窗口大小和最小尺寸
        self.setMinimumSize(1024, 768)
        self.resize(1200, 800)
    
    def init_control_bar(self, layout):
        """Initialize the top control bar"""
        control_bar = QWidget()
        control_bar.setObjectName("controlBar")
        control_layout = QHBoxLayout(control_bar)
        
        # Symbol selection
        control_layout.addWidget(QLabel("交易对:"))
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "BNB-USDT-SWAP"])
        self.symbol_combo.currentTextChanged.connect(self.on_symbol_change)
        control_layout.addWidget(self.symbol_combo)
        
        # Update button
        self.update_btn = QPushButton("更新数据")
        self.update_btn.setObjectName("secondary")
        self.update_btn.clicked.connect(self.update_all_data)
        control_layout.addWidget(self.update_btn)
        
        # Mode selection
        control_layout.addWidget(QLabel("模式:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["实盘", "回测"])
        control_layout.addWidget(self.mode_combo)
        
        # Status label
        self.status_label = QLabel("状态: 就绪")
        self.status_label.setStyleSheet("color: green; font-weight: bold;")
        control_layout.addWidget(self.status_label)
        
        # DNS Status label
        self.dns_status_label = QLabel("DNS状态: 未测试")
        self.dns_status_label.setStyleSheet("color: orange; font-weight: bold;")
        control_layout.addWidget(self.dns_status_label)
        
        # Font size adjustment
        control_layout.addWidget(QLabel("字体大小:"))
        self.font_size_combo = QComboBox()
        self.font_size_combo.addItems(["小", "中", "大"])
        self.font_size_combo.setCurrentIndex(1)  # 默认中等大小
        self.font_size_combo.currentIndexChanged.connect(self.on_font_size_change)
        control_layout.addWidget(self.font_size_combo)
        
        # Add strategy button
        self.add_strategy_btn = QPushButton("添加策略")
        self.add_strategy_btn.setObjectName("primary")
        self.add_strategy_btn.clicked.connect(self.add_strategy)
        control_layout.addWidget(self.add_strategy_btn)
        
        # Help button
        self.help_btn = QPushButton("帮助")
        self.help_btn.setObjectName("secondary")
        self.help_btn.clicked.connect(self.show_help)
        control_layout.addWidget(self.help_btn)
        
        # 移除适配屏幕按钮，改为使用鼠标缩放模式控制窗口大小
        # 窗口已经支持通过鼠标拖拽边缘来调整大小
        # 同时保持了内容的比例缩放
        
        control_layout.addStretch()
        layout.addWidget(control_bar)
    
    def show_help(self):
        """Show help dialog"""
        help_dialog = HelpDialog(self)
        help_dialog.exec_()
    
    def add_strategy(self):
        """Add a new strategy"""
        from PyQt5.QtWidgets import QDialog, QFormLayout, QLineEdit, QPushButton, QVBoxLayout, QMessageBox
        
        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("添加策略")
        dialog.setGeometry(300, 300, 400, 200)
        
        # Create layout
        layout = QVBoxLayout(dialog)
        form_layout = QFormLayout()
        
        # Strategy name
        self.strategy_name_edit = QLineEdit()
        self.strategy_name_edit.setPlaceholderText("策略名称")
        form_layout.addRow("策略名称:", self.strategy_name_edit)
        
        # Strategy class name
        self.strategy_class_edit = QLineEdit()
        self.strategy_class_edit.setPlaceholderText("策略类名")
        form_layout.addRow("策略类名:", self.strategy_class_edit)
        
        # Strategy module path
        self.strategy_module_edit = QLineEdit()
        self.strategy_module_edit.setPlaceholderText("模块路径 (例如: strategies.my_strategy)")
        form_layout.addRow("模块路径:", self.strategy_module_edit)
        
        # Buttons
        button_layout = QVBoxLayout()
        add_button = QPushButton("添加")
        add_button.clicked.connect(lambda: self._add_strategy_from_dialog(dialog))
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(dialog.reject)
        
        button_layout.addWidget(add_button)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(form_layout)
        layout.addLayout(button_layout)
        
        dialog.exec_()
    
    def _add_strategy_from_dialog(self, dialog):
        """Add strategy from dialog input"""
        try:
            strategy_name = self.strategy_name_edit.text().strip()
            strategy_class = self.strategy_class_edit.text().strip()
            strategy_module = self.strategy_module_edit.text().strip()
            
            if not strategy_name or not strategy_class or not strategy_module:
                QMessageBox.warning(self, "输入错误", "请填写所有字段")
                return
            
            # Import strategy module and class
            import importlib
            module = importlib.import_module(strategy_module)
            strategy_class_obj = getattr(module, strategy_class)
            
            # Register strategy
            success = self.trading_bot.register_strategy(strategy_class_obj)
            
            if success:
                self.log(f"策略添加成功: {strategy_name}")
                QMessageBox.information(self, "成功", f"策略 {strategy_name} 添加成功")
                # Reload strategy list
                if hasattr(self, 'load_strategy_list'):
                    self.load_strategy_list()
            else:
                self.log(f"策略添加失败: {strategy_name}")
                QMessageBox.error(self, "失败", f"策略 {strategy_name} 添加失败")
            
            dialog.accept()
        except Exception as e:
            self.log(f"添加策略失败: {e}")
            import traceback
            self.log(traceback.format_exc())
            QMessageBox.error(self, "错误", f"添加策略时出错: {str(e)}")
    
    def add_trading_plan(self):
        """Add a trading plan"""
        try:
            direction = self.plan_direction.currentText()
            time_horizon = self.plan_time_horizon.currentText()
            confidence = self.plan_confidence.currentText()
            notes = self.plan_notes.text().strip()
            
            # Get current time
            import datetime
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Add plan to the table
            row_position = self.plan_list.rowCount()
            self.plan_list.insertRow(row_position)
            
            # Set plan details
            self.plan_list.setItem(row_position, 0, QTableWidgetItem(direction))
            self.plan_list.setItem(row_position, 1, QTableWidgetItem(time_horizon))
            self.plan_list.setItem(row_position, 2, QTableWidgetItem(confidence))
            self.plan_list.setItem(row_position, 3, QTableWidgetItem(notes))
            self.plan_list.setItem(row_position, 4, QTableWidgetItem(current_time))
            
            # Add execute button
            execute_btn = QPushButton("执行")
            execute_btn.setObjectName("primary")
            execute_btn.clicked.connect(lambda: self.execute_plan(row_position))
            self.plan_list.setCellWidget(row_position, 5, execute_btn)
            
            # Clear input fields
            self.plan_notes.setText("")
            
            self.log(f"添加交易规划: {direction} (时间范围: {time_horizon}, 信心: {confidence})")
        except Exception as e:
            self.log(f"添加交易规划失败: {e}")
            QMessageBox.error(self, "错误", f"添加交易规划时出错: {str(e)}")
    
    def execute_plan(self, row):
        """Execute a trading plan"""
        try:
            direction = self.plan_list.item(row, 0).text()
            time_horizon = self.plan_list.item(row, 1).text()
            confidence = self.plan_list.item(row, 2).text()
            notes = self.plan_list.item(row, 3).text()
            
            # Here you would implement the actual order execution
            # For now, we'll just log the execution
            self.log(f"执行交易规划: {direction} (时间范围: {time_horizon}, 信心: {confidence})")
            
            # Remove the plan from the list
            self.plan_list.removeRow(row)
            
            QMessageBox.information(self, "成功", f"交易规划已执行")
        except Exception as e:
            self.log(f"执行交易规划失败: {e}")
            QMessageBox.error(self, "错误", f"执行交易规划时出错: {str(e)}")
    
    def apply_plans_to_strategy(self):
        """Apply trading plans to strategy"""
        try:
            # Get all plans
            plans = []
            for row in range(self.plan_list.rowCount()):
                direction = self.plan_list.item(row, 0).text()
                time_horizon = self.plan_list.item(row, 1).text()
                confidence = self.plan_list.item(row, 2).text()
                notes = self.plan_list.item(row, 3).text()
                
                plans.append({
                    "direction": direction,
                    "time_horizon": time_horizon,
                    "confidence": confidence,
                    "notes": notes
                })
            
            if not plans:
                QMessageBox.warning(self, "警告", "没有可应用的交易规划")
                return
            
            # Get current strategy
            strategy_name = self.strategy_combo.currentText()
            
            # Get strategy execution agent
            strategy_agent = self.trading_bot.get_agent("strategy_execution_agent")
            if not strategy_agent:
                QMessageBox.error(self, "错误", "策略执行智能体未初始化")
                return
            
            # Apply plans to strategy
            success = strategy_agent.apply_trading_plans(strategy_name, plans)
            
            if success:
                self.log(f"成功将 {len(plans)} 个交易规划应用到策略 {strategy_name}")
                QMessageBox.information(self, "成功", f"交易规划已应用到策略 {strategy_name}")
            else:
                self.log(f"应用交易规划到策略 {strategy_name} 失败")
                QMessageBox.error(self, "错误", f"应用交易规划到策略 {strategy_name} 失败")
        except Exception as e:
            self.log(f"应用交易规划失败: {e}")
            QMessageBox.error(self, "错误", f"应用交易规划时出错: {str(e)}")
    
    def switch_env(self, is_test):
        """Switch between testnet and mainnet"""
        try:
            env = "测试网" if is_test else "主网"
            self.log(f"切换到{env}")
            
            # Update UI to reflect the change
            if is_test:
                self.testnet_btn.setStyleSheet("background-color: #f59e0b; color: white;")
                self.mainnet_btn.setStyleSheet("")
            else:
                self.mainnet_btn.setStyleSheet("background-color: #3b82f6; color: white;")
                self.testnet_btn.setStyleSheet("")
            
            QMessageBox.information(self, "成功", f"已切换到{env}")
        except Exception as e:
            self.log(f"切换环境失败: {e}")
            QMessageBox.error(self, "错误", f"切换环境时出错: {str(e)}")
    
    def manual_network_adaptation(self):
        """Perform manual network adaptation"""
        try:
            self.log("执行手动网络适配...")
            # Here you would implement network adaptation logic
            self.log("手动网络适配完成")
            QMessageBox.information(self, "成功", "手动网络适配已完成")
        except Exception as e:
            self.log(f"手动网络适配失败: {e}")
            QMessageBox.error(self, "错误", f"手动网络适配时出错: {str(e)}")
    
    def refresh_network_status(self):
        """Refresh network status"""
        try:
            self.log("刷新网络状态...")
            # Here you would implement network status refresh logic
            self.log("网络状态刷新完成")
            QMessageBox.information(self, "成功", "网络状态已刷新")
        except Exception as e:
            self.log(f"刷新网络状态失败: {e}")
            QMessageBox.error(self, "错误", f"刷新网络状态时出错: {str(e)}")
    
    def init_trading_tab(self):
        """Initialize trading tab"""
        trading_tab = QWidget()
        trading_layout = QVBoxLayout(trading_tab)
        trading_layout.setSpacing(4)
        trading_layout.setContentsMargins(4, 4, 4, 4)
        
        # Top: Market data splitter
        market_splitter = QSplitter(Qt.Horizontal)
        market_splitter.setMinimumHeight(500)
        # 设置拉伸因子，确保左右两部分保持固定比例
        market_splitter.setStretchFactor(0, 1)  # 左侧占1份
        market_splitter.setStretchFactor(1, 2)  # 右侧占2份
        
        # Left: Ticker and Order Book
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(4)
        left_layout.setContentsMargins(4, 4, 4, 4)
        # 设置左侧布局的大小策略
        left_widget.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        
        # Ticker display
        self.init_ticker_widget(left_layout)
        
        # Order Book
        self.init_order_book_widget(left_layout)
        
        market_splitter.addWidget(left_widget)
        
        # Right: Trading controls, chart and order table
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(4)
        right_layout.setContentsMargins(4, 4, 4, 4)
        # 设置右侧布局的大小策略
        right_widget.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        
        # Chart widget
        self.init_chart_widget(right_layout)
        
        # Trading controls
        self.init_trading_controls(right_layout)
        
        # Current orders table
        self.init_orders_table(right_layout)
        
        market_splitter.addWidget(right_widget)
        # 设置初始大小比例，但允许用户调整
        market_splitter.setSizes([350, 700])
        
        trading_layout.addWidget(market_splitter)
        
        self.tab_widget.addTab(trading_tab, "交易")
    
    def init_ticker_widget(self, layout):
        """Initialize ticker display"""
        ticker_group = QGroupBox("市场数据")
        ticker_layout = QGridLayout(ticker_group)
        
        # Ticker labels
        self.ticker_price = QLabel("0.00")
        self.ticker_price.setFont(QFont("Segoe UI", 28, QFont.Bold))
        self.ticker_price.setAlignment(Qt.AlignCenter)
        self.ticker_price.setStyleSheet("color: #2c3e50; margin: 10px 0;")
        
        self.ticker_change = QLabel("0.00")
        self.ticker_change.setFont(QFont("Segoe UI", 16))
        self.ticker_change.setAlignment(Qt.AlignCenter)
        
        self.ticker_change_pct = QLabel("0.00%")
        self.ticker_change_pct.setFont(QFont("Segoe UI", 16))
        self.ticker_change_pct.setAlignment(Qt.AlignCenter)
        
        ticker_layout.addWidget(self.ticker_price, 0, 0, 1, 3)
        ticker_layout.addWidget(self.ticker_change, 1, 0)
        ticker_layout.addWidget(self.ticker_change_pct, 1, 1)
        
        # Add last update time
        self.last_update_time = QLabel("")
        self.last_update_time.setFont(QFont("Segoe UI", 10))
        self.last_update_time.setAlignment(Qt.AlignRight)
        self.last_update_time.setStyleSheet("color: #64748b;")
        ticker_layout.addWidget(self.last_update_time, 1, 2)
        
        layout.addWidget(ticker_group)
    
    def init_order_book_widget(self, layout):
        """Initialize order book display"""
        order_book_group = QGroupBox("订单簿")
        order_book_layout = QHBoxLayout(order_book_group)
        
        # Buy orders
        buy_widget = QWidget()
        buy_layout = QVBoxLayout(buy_widget)
        
        buy_header = QLabel("买单")
        buy_header.setStyleSheet("font-weight: 600; color: #10b981; margin-bottom: 8px;")
        buy_header.setAlignment(Qt.AlignCenter)
        buy_layout.addWidget(buy_header)
        
        self.buy_table = QTableWidget(10, 2)
        self.buy_table.setHorizontalHeaderLabels(["价格", "数量"])
        self.buy_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.buy_table.setStyleSheet("""
            QTableWidget { 
                background-color: #f0fff4; 
                border-radius: 6px;
                border: 1px solid #dcfce7;
            }
            QTableWidget::item {
                border-bottom: 1px solid #f0fdf4;
            }
            QTableWidget::item:hover {
                background-color: #dcfce7;
            }
        """)
        buy_layout.addWidget(self.buy_table)
        
        # Sell orders
        sell_widget = QWidget()
        sell_layout = QVBoxLayout(sell_widget)
        
        sell_header = QLabel("卖单")
        sell_header.setStyleSheet("font-weight: 600; color: #ef4444; margin-bottom: 8px;")
        sell_header.setAlignment(Qt.AlignCenter)
        sell_layout.addWidget(sell_header)
        
        self.sell_table = QTableWidget(10, 2)
        self.sell_table.setHorizontalHeaderLabels(["价格", "数量"])
        self.sell_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sell_table.setStyleSheet("""
            QTableWidget { 
                background-color: #fff1f0; 
                border-radius: 6px;
                border: 1px solid #fee2e2;
            }
            QTableWidget::item {
                border-bottom: 1px solid #fff1f0;
            }
            QTableWidget::item:hover {
                background-color: #fee2e2;
            }
        """)
        sell_layout.addWidget(self.sell_table)
        
        order_book_layout.addWidget(buy_widget)
        order_book_layout.addWidget(sell_widget)
        
        layout.addWidget(order_book_group)
    
    def init_chart_widget(self, layout):
        """Initialize chart widget for K-line display"""
        chart_group = QGroupBox("K线图")
        chart_layout = QVBoxLayout(chart_group)
        
        # Timeframe selector
        timeframe_layout = QHBoxLayout()
        timeframe_layout.addWidget(QLabel("时间周期:"))
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(["1m", "5m", "15m", "1h", "4h", "1d"])
        self.timeframe_combo.currentTextChanged.connect(self.update_chart)
        timeframe_layout.addWidget(self.timeframe_combo)
        
        # Refresh button
        self.refresh_chart_btn = QPushButton("刷新")
        self.refresh_chart_btn.setObjectName("secondary")
        self.refresh_chart_btn.clicked.connect(self.update_chart)
        timeframe_layout.addWidget(self.refresh_chart_btn)
        
        timeframe_layout.addStretch()
        chart_layout.addLayout(timeframe_layout)
        
        if HAS_MPL:
            # Create figure and canvas
            self.figure = Figure(figsize=(10, 4), dpi=100)
            self.canvas = FigureCanvas(self.figure)
            self.canvas.setMinimumHeight(300)
            chart_layout.addWidget(self.canvas)
            
            # Initialize empty chart
            self.update_chart()
        else:
            # Show placeholder if mplfinance is not installed
            placeholder_label = QLabel("K线图需要安装 mplfinance 库\n请运行: pip install mplfinance")
            placeholder_label.setAlignment(Qt.AlignCenter)
            placeholder_label.setStyleSheet("font-size: 14px; color: #64748b;")
            chart_layout.addWidget(placeholder_label)
        
        layout.addWidget(chart_group)
    
    def init_trading_controls(self, layout):
        """Initialize trading controls"""
        trading_group = QGroupBox("交易控制")
        trading_layout = QVBoxLayout(trading_group)
        trading_layout.setSpacing(6)
        
        # Main parameters section with grid layout for better organization
        main_params_group = QGroupBox("订单参数")
        main_params_layout = QGridLayout(main_params_group)
        main_params_layout.setSpacing(6)
        main_params_layout.setContentsMargins(6, 6, 6, 6)
        
        # Order type and side in first row
        main_params_layout.addWidget(QLabel("订单类型:"), 0, 0)
        self.order_type_combo = QComboBox()
        self.order_type_combo.addItems(["限价", "市价", "只做maker", "触发限价", "触发市价"])
        self.order_type_combo.setMinimumWidth(120)
        main_params_layout.addWidget(self.order_type_combo, 0, 1)
        
        main_params_layout.addWidget(QLabel("方向:"), 0, 2)
        self.side_combo = QComboBox()
        self.side_combo.addItems(["买入", "卖出"])
        self.side_combo.setMinimumWidth(80)
        main_params_layout.addWidget(self.side_combo, 0, 3)
        
        # Price and amount in second row
        main_params_layout.addWidget(QLabel("价格:"), 1, 0)
        self.price_edit = QLineEdit("0.0")
        self.price_edit.setPlaceholderText("输入价格")
        self.price_edit.setMinimumWidth(120)
        main_params_layout.addWidget(self.price_edit, 1, 1)
        
        main_params_layout.addWidget(QLabel("数量:"), 1, 2)
        self.amount_edit = QLineEdit("0.0")
        self.amount_edit.setPlaceholderText("输入数量")
        self.amount_edit.setMinimumWidth(120)
        main_params_layout.addWidget(self.amount_edit, 1, 3)
        
        # Leverage and trading mode in third row
        main_params_layout.addWidget(QLabel("杠杆:"), 2, 0)
        self.leverage_spin = QSpinBox()
        self.leverage_spin.setRange(1, 100)
        self.leverage_spin.setValue(5)
        self.leverage_spin.setMinimumWidth(80)
        main_params_layout.addWidget(self.leverage_spin, 2, 1)
        
        main_params_layout.addWidget(QLabel("交易模式:"), 2, 2)
        self.td_mode_combo = QComboBox()
        self.td_mode_combo.addItems(["逐仓", "全仓"])
        self.td_mode_combo.setCurrentText("逐仓")
        self.td_mode_combo.setMinimumWidth(80)
        main_params_layout.addWidget(self.td_mode_combo, 2, 3)
        
        # Position side and reduce only in fourth row
        main_params_layout.addWidget(QLabel("持仓方向:"), 3, 0)
        self.pos_side_combo = QComboBox()
        self.pos_side_combo.addItems(["净持仓", "多头", "空头"])
        self.pos_side_combo.setCurrentText("净持仓")
        self.pos_side_combo.setMinimumWidth(120)
        main_params_layout.addWidget(self.pos_side_combo, 3, 1)
        
        main_params_layout.addWidget(QLabel("只减仓:"), 3, 2)
        self.reduce_only_check = QCheckBox()
        self.reduce_only_check.setChecked(False)
        main_params_layout.addWidget(self.reduce_only_check, 3, 3)
        
        # Client order ID in fifth row (span across columns)
        main_params_layout.addWidget(QLabel("客户订单ID:"), 4, 0)
        self.cl_ord_id_edit = QLineEdit("")
        self.cl_ord_id_edit.setPlaceholderText("可选，客户订单ID")
        main_params_layout.addWidget(self.cl_ord_id_edit, 4, 1, 1, 3)
        
        trading_layout.addWidget(main_params_group)
        
        # Take Profit / Stop Loss settings
        self.init_tp_sl_settings(trading_layout)
        
        # Batch operations
        self.init_batch_operations(trading_layout)
        
        # Place order button with better styling
        self.place_order_btn = QPushButton("下单")
        self.place_order_btn.setObjectName("primary")
        self.place_order_btn.setMinimumHeight(32)
        self.place_order_btn.setStyleSheet("""
            QPushButton#primary {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 600;
                padding: 8px;
            }
            QPushButton#primary:hover {
                background-color: #2563eb;
            }
            QPushButton#primary:pressed {
                background-color: #1d4ed8;
            }
        """)
        self.place_order_btn.clicked.connect(self.place_order)
        trading_layout.addWidget(self.place_order_btn)
        
        layout.addWidget(trading_group)
    
    def init_tp_sl_settings(self, layout):
        """Initialize Take Profit / Stop Loss settings"""
        tp_sl_group = QGroupBox("止盈止损设置")
        tp_sl_layout = QGridLayout(tp_sl_group)
        
        # Take Profit settings with better styling
        tp_label = QLabel("止盈设置")
        tp_label.setStyleSheet("font-weight: 600; color: #10b981; margin-bottom: 8px;")
        tp_label.setAlignment(Qt.AlignCenter)
        tp_sl_layout.addWidget(tp_label, 0, 0, 1, 2)
        
        self.tp_px_edit = QLineEdit("0.0")
        self.tp_px_edit.setPlaceholderText("止盈价格")
        tp_sl_layout.addWidget(QLabel("止盈价格:"), 1, 0)
        tp_sl_layout.addWidget(self.tp_px_edit, 1, 1)
        
        self.tp_trigger_px_edit = QLineEdit("0.0")
        self.tp_trigger_px_edit.setPlaceholderText("止盈触发价格")
        tp_sl_layout.addWidget(QLabel("止盈触发价格:"), 2, 0)
        tp_sl_layout.addWidget(self.tp_trigger_px_edit, 2, 1)
        
        # Stop Loss settings with better styling
        sl_label = QLabel("止损设置")
        sl_label.setStyleSheet("font-weight: 600; color: #ef4444; margin-bottom: 8px;")
        sl_label.setAlignment(Qt.AlignCenter)
        tp_sl_layout.addWidget(sl_label, 0, 2, 1, 2)
        
        self.sl_px_edit = QLineEdit("0.0")
        self.sl_px_edit.setPlaceholderText("止损价格")
        tp_sl_layout.addWidget(QLabel("止损价格:"), 1, 2)
        tp_sl_layout.addWidget(self.sl_px_edit, 1, 3)
        
        self.sl_trigger_px_edit = QLineEdit("0.0")
        self.sl_trigger_px_edit.setPlaceholderText("止损触发价格")
        tp_sl_layout.addWidget(QLabel("止损触发价格:"), 2, 2)
        tp_sl_layout.addWidget(self.sl_trigger_px_edit, 2, 3)
        
        # Trigger price type
        self.tp_trigger_type_combo = QComboBox()
        self.tp_trigger_type_combo.addItems(["最新价", "指数价", "标记价"])
        self.tp_trigger_type_combo.setCurrentText("最新价")
        tp_sl_layout.addWidget(QLabel("止盈触发类型:"), 3, 0)
        tp_sl_layout.addWidget(self.tp_trigger_type_combo, 3, 1)
        
        self.sl_trigger_type_combo = QComboBox()
        self.sl_trigger_type_combo.addItems(["最新价", "指数价", "标记价"])
        self.sl_trigger_type_combo.setCurrentText("最新价")
        tp_sl_layout.addWidget(QLabel("止损触发类型:"), 3, 2)
        tp_sl_layout.addWidget(self.sl_trigger_type_combo, 3, 3)
        
        layout.addWidget(tp_sl_group)
    
    def init_batch_operations(self, layout):
        """Initialize batch operations controls"""
        batch_group = QGroupBox("批量操作")
        batch_layout = QHBoxLayout(batch_group)
        
        # Batch place orders button with better styling
        self.batch_place_btn = QPushButton("批量下单")
        self.batch_place_btn.setObjectName("secondary")
        self.batch_place_btn.setMinimumHeight(36)
        self.batch_place_btn.clicked.connect(self.batch_place_orders)
        batch_layout.addWidget(self.batch_place_btn)
        
        # Batch cancel orders button with better styling
        self.batch_cancel_btn = QPushButton("批量撤单")
        self.batch_cancel_btn.setObjectName("warning")
        self.batch_cancel_btn.setMinimumHeight(36)
        self.batch_cancel_btn.clicked.connect(self.batch_cancel_orders)
        batch_layout.addWidget(self.batch_cancel_btn)
        
        # Batch amend orders button with better styling
        self.batch_amend_btn = QPushButton("批量修改")
        self.batch_amend_btn.setObjectName("secondary")
        self.batch_amend_btn.setMinimumHeight(36)
        self.batch_amend_btn.clicked.connect(self.batch_amend_orders)
        batch_layout.addWidget(self.batch_amend_btn)
        
        layout.addWidget(batch_group)
    
    def init_orders_table(self, layout):
        """Initialize current orders table"""
        orders_group = QGroupBox("当前订单")
        orders_layout = QVBoxLayout(orders_group)
        
        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(10)
        self.orders_table.setHorizontalHeaderLabels(["订单ID", "交易对", "方向", "类型", "价格", "数量", "状态", "持仓方向", "交易模式", "客户订单ID"])
        
        # 设置表格列宽调整模式
        header = self.orders_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        
        # 设置表格最小高度
        self.orders_table.setMinimumHeight(150)
        
        # Order operations buttons
        order_ops_layout = QHBoxLayout()
        order_ops_layout.setSpacing(6)
        
        # Cancel selected order button with styling
        self.cancel_order_btn = QPushButton("取消选中订单")
        self.cancel_order_btn.setObjectName("danger")
        self.cancel_order_btn.setMinimumHeight(28)
        self.cancel_order_btn.setMinimumWidth(100)
        self.cancel_order_btn.clicked.connect(self.cancel_selected_order)
        order_ops_layout.addWidget(self.cancel_order_btn)
        
        # Amend selected order button with styling
        self.amend_order_btn = QPushButton("修改选中订单")
        self.amend_order_btn.setObjectName("secondary")
        self.amend_order_btn.setMinimumHeight(28)
        self.amend_order_btn.setMinimumWidth(100)
        self.amend_order_btn.clicked.connect(self.amend_selected_order)
        order_ops_layout.addWidget(self.amend_order_btn)
        
        # Select all orders button with styling
        self.select_all_orders_btn = QPushButton("全选订单")
        self.select_all_orders_btn.setMinimumHeight(28)
        self.select_all_orders_btn.setMinimumWidth(80)
        self.select_all_orders_btn.clicked.connect(self.select_all_orders)
        order_ops_layout.addWidget(self.select_all_orders_btn)
        
        # Clear selection button with styling
        self.clear_selection_btn = QPushButton("清空选择")
        self.clear_selection_btn.setMinimumHeight(28)
        self.clear_selection_btn.setMinimumWidth(80)
        self.clear_selection_btn.clicked.connect(self.clear_order_selection)
        order_ops_layout.addWidget(self.clear_selection_btn)
        
        orders_layout.addWidget(self.orders_table)
        orders_layout.addLayout(order_ops_layout)
        
        layout.addWidget(orders_group)
    
    def init_strategy_tab(self):
        """Initialize strategy configuration tab"""
        strategy_tab = QWidget()
        strategy_layout = QVBoxLayout(strategy_tab)
        strategy_layout.setSpacing(4)
        strategy_layout.setContentsMargins(4, 4, 4, 4)
        
        # Strategy controls
        strategy_group = QGroupBox("策略配置")
        strategy_form = QFormLayout(strategy_group)
        strategy_form.setSpacing(4)
        
        # Strategy selection
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["passivbot_grid", "passivbot_trailing", "原子核互反动力学策略"])
        strategy_form.addRow("策略:", self.strategy_combo)
        
        # Mode selection
        self.strategy_mode_combo = QComboBox()
        self.strategy_mode_combo.addItems(["回测", "实盘"])
        strategy_form.addRow("模式:", self.strategy_mode_combo)
        
        # Timeframe
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(["1m", "5m", "15m", "1h", "4h", "1d"])
        strategy_form.addRow("时间周期:", self.timeframe_combo)
        
        # Grid parameters
        self.grid_spacing = QDoubleSpinBox()
        self.grid_spacing.setRange(0.001, 0.1)
        self.grid_spacing.setValue(0.01)
        self.grid_spacing.setSuffix(" %")
        strategy_form.addRow("网格间距:", self.grid_spacing)
        
        self.grid_multiplier = QDoubleSpinBox()
        self.grid_multiplier.setRange(1.1, 5.0)
        self.grid_multiplier.setValue(2.0)
        strategy_form.addRow("网格倍数:", self.grid_multiplier)
        
        # Risk parameters
        self.max_leverage = QSpinBox()
        self.max_leverage.setRange(1, 100)
        self.max_leverage.setValue(5)
        strategy_form.addRow("最大杠杆:", self.max_leverage)
        
        self.stop_loss_pct = QDoubleSpinBox()
        self.stop_loss_pct.setRange(0.01, 0.5)
        self.stop_loss_pct.setValue(0.03)
        self.stop_loss_pct.setSuffix(" %")
        strategy_form.addRow("止损:", self.stop_loss_pct)
        
        self.take_profit_pct = QDoubleSpinBox()
        self.take_profit_pct.setRange(0.01, 0.5)
        self.take_profit_pct.setValue(0.05)
        self.take_profit_pct.setSuffix(" %")
        strategy_form.addRow("止盈:", self.take_profit_pct)
        
        strategy_layout.addWidget(strategy_group)
        
        # Strategy control buttons
        control_layout = QHBoxLayout()
        
        self.start_strategy_btn = QPushButton("启动策略")
        self.start_strategy_btn.setObjectName("primary")
        self.start_strategy_btn.clicked.connect(self.start_strategy)
        
        self.stop_strategy_btn = QPushButton("停止策略")
        self.stop_strategy_btn.setObjectName("danger")
        self.stop_strategy_btn.clicked.connect(self.stop_strategy)
        
        self.strategy_status = QLabel("状态: 已停止")
        self.strategy_status.setStyleSheet("font-weight: bold;")
        
        control_layout.addWidget(self.start_strategy_btn)
        control_layout.addWidget(self.stop_strategy_btn)
        control_layout.addStretch()
        control_layout.addWidget(self.strategy_status)
        
        strategy_layout.addLayout(control_layout)
        
        # Strategy trading information
        trading_info_group = QGroupBox("策略交易信息")
        trading_info_layout = QGridLayout(trading_info_group)
        trading_info_layout.setSpacing(4)
        
        # Trading statistics
        self.total_trades_label = QLabel("0")
        self.total_pnl_label = QLabel("0.00")
        self.current_position_label = QLabel("0.00")
        self.win_rate_label = QLabel("0%")
        
        trading_info_layout.addWidget(QLabel("总交易量:"), 0, 0)
        trading_info_layout.addWidget(self.total_trades_label, 0, 1)
        trading_info_layout.addWidget(QLabel("总盈亏:"), 0, 2)
        trading_info_layout.addWidget(self.total_pnl_label, 0, 3)
        
        trading_info_layout.addWidget(QLabel("当前持仓:"), 1, 0)
        trading_info_layout.addWidget(self.current_position_label, 1, 1)
        trading_info_layout.addWidget(QLabel("胜率:"), 1, 2)
        trading_info_layout.addWidget(self.win_rate_label, 1, 3)
        
        strategy_layout.addWidget(trading_info_group)
        
        # Order information
        order_info_group = QGroupBox("订单信息")
        order_info_layout = QVBoxLayout(order_info_group)
        order_info_layout.setSpacing(4)
        
        # Order table
        self.order_table = QTableWidget()
        self.order_table.setColumnCount(6)
        self.order_table.setHorizontalHeaderLabels(["订单ID", "方向", "价格", "数量", "状态", "时间"])
        self.order_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.order_table.horizontalHeader().setStretchLastSection(True)
        # 设置表格的最小高度
        self.order_table.setMinimumHeight(120)
        order_info_layout.addWidget(self.order_table)
        
        # Manual planning functionality
        planning_group = QGroupBox("手动规划")
        planning_layout = QVBoxLayout(planning_group)
        planning_layout.setSpacing(4)
        
        # Planning controls
        planning_controls = QGridLayout()
        planning_controls.setSpacing(4)
        
        # Direction - 主要关注买入卖出方向
        planning_controls.addWidget(QLabel("交易方向:"), 0, 0)
        self.plan_direction = QComboBox()
        self.plan_direction.addItems(["买入", "卖出"])
        planning_controls.addWidget(self.plan_direction, 0, 1)
        
        # Time horizon - 时间范围
        planning_controls.addWidget(QLabel("时间范围:"), 0, 2)
        self.plan_time_horizon = QComboBox()
        self.plan_time_horizon.addItems(["短期", "中期", "长期"])
        planning_controls.addWidget(self.plan_time_horizon, 0, 3)
        
        # Confidence level - 信心程度
        planning_controls.addWidget(QLabel("信心程度:"), 1, 0)
        self.plan_confidence = QComboBox()
        self.plan_confidence.addItems(["低", "中", "高"])
        planning_controls.addWidget(self.plan_confidence, 1, 1)
        
        # Notes - 备注
        planning_controls.addWidget(QLabel("备注:"), 1, 2)
        self.plan_notes = QLineEdit("")
        self.plan_notes.setPlaceholderText("可选，添加备注")
        planning_controls.addWidget(self.plan_notes, 1, 3)
        
        # Add plan button
        self.add_plan_btn = QPushButton("添加规划")
        self.add_plan_btn.setObjectName("primary")
        self.add_plan_btn.clicked.connect(self.add_trading_plan)
        planning_controls.addWidget(self.add_plan_btn, 2, 0, 1, 4)
        
        # Apply to strategy button
        self.apply_to_strategy_btn = QPushButton("应用到策略")
        self.apply_to_strategy_btn.setObjectName("secondary")
        self.apply_to_strategy_btn.clicked.connect(self.apply_plans_to_strategy)
        planning_controls.addWidget(self.apply_to_strategy_btn, 3, 0, 1, 4)
        
        planning_layout.addLayout(planning_controls)
        
        # Plan list
        self.plan_list = QTableWidget()
        self.plan_list.setColumnCount(6)
        self.plan_list.setHorizontalHeaderLabels(["方向", "时间范围", "信心程度", "备注", "创建时间", "操作"])
        self.plan_list.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.plan_list.horizontalHeader().setStretchLastSection(True)
        # 设置表格的最小高度
        self.plan_list.setMinimumHeight(120)
        planning_layout.addWidget(self.plan_list)
        
        strategy_layout.addWidget(order_info_group)
        strategy_layout.addWidget(planning_group)
        
        # Strategy log
        self.strategy_log = QTextEdit()
        self.strategy_log.setReadOnly(True)
        self.strategy_log.setStyleSheet("background-color: #f5f5f5;")
        # 设置日志窗口的最小高度
        self.strategy_log.setMinimumHeight(150)
        strategy_layout.addWidget(self.strategy_log)
        
        self.tab_widget.addTab(strategy_tab, "策略")
    
    def init_account_tab(self):
        """Initialize account information tab"""
        account_tab = QWidget()
        account_layout = QVBoxLayout(account_tab)
        account_layout.setSpacing(4)
        account_layout.setContentsMargins(4, 4, 4, 4)
        
        # Account info
        account_group = QGroupBox("账户信息")
        account_layout.addWidget(account_group)
        
        # Balance and positions
        balance_layout = QHBoxLayout(account_group)
        balance_layout.setSpacing(4)
        balance_layout.setContentsMargins(4, 4, 4, 4)
        
        # Balance info
        balance_widget = QWidget()
        balance_form = QFormLayout(balance_widget)
        balance_form.setSpacing(4)
        
        self.available_balance = QLabel("0.00")
        balance_form.addRow("可用余额:", self.available_balance)
        
        self.total_balance = QLabel("0.00")
        balance_form.addRow("总余额:", self.total_balance)
        
        self.unrealized_pnl = QLabel("0.00")
        balance_form.addRow("未实现盈亏:", self.unrealized_pnl)
        
        balance_layout.addWidget(balance_widget)
        
        # Positions table placeholder
        positions_widget = QWidget()
        positions_layout = QVBoxLayout(positions_widget)
        positions_layout.setSpacing(4)
        positions_label = QLabel("持仓信息将在连接后显示")
        positions_label.setAlignment(Qt.AlignCenter)
        positions_layout.addWidget(positions_label)
        balance_layout.addWidget(positions_widget)
    
    def init_network_status_tab(self):
        """Initialize network status display tab"""
        network_tab = QWidget()
        network_layout = QVBoxLayout(network_tab)
        network_layout.setSpacing(4)
        network_layout.setContentsMargins(4, 4, 4, 4)
        
        # Network info group - current connection
        current_group = QGroupBox("当前连接信息")
        current_layout = QFormLayout(current_group)
        current_layout.setSpacing(4)
        
        # Current IP address
        self.current_ip_label = QLabel("未检测")
        current_layout.addRow("当前IP:", self.current_ip_label)
        
        # Current port
        self.current_port_label = QLabel("443")
        current_layout.addRow("当前端口:", self.current_port_label)
        
        # Connection status
        self.connection_status_label = QLabel("未连接")
        self.connection_status_label.setStyleSheet("color: red; font-weight: bold;")
        current_layout.addRow("连接状态:", self.connection_status_label)
        
        # API response time
        self.response_time_label = QLabel("0 ms")
        current_layout.addRow("API响应时间:", self.response_time_label)
        
        # WebSocket status
        self.ws_status_label = QLabel("未连接")
        self.ws_status_label.setStyleSheet("color: red; font-weight: bold;")
        current_layout.addRow("WebSocket状态:", self.ws_status_label)
        
        network_layout.addWidget(current_group)
        
        # Network health group
        health_group = QGroupBox("网络健康状况")
        health_layout = QGridLayout(health_group)
        health_layout.setSpacing(4)
        
        # DNS resolution status
        self.dns_status_label = QLabel("正常")
        self.dns_status_label.setStyleSheet("color: green; font-weight: bold;")
        health_layout.addWidget(QLabel("DNS解析状态:"), 0, 0)
        health_layout.addWidget(self.dns_status_label, 0, 1)
        
        # SSL certificate status
        self.ssl_status_label = QLabel("有效")
        self.ssl_status_label.setStyleSheet("color: green; font-weight: bold;")
        health_layout.addWidget(QLabel("SSL证书状态:"), 0, 2)
        health_layout.addWidget(self.ssl_status_label, 0, 3)
        
        # Packet loss rate
        self.packet_loss_label = QLabel("0%")
        self.packet_loss_label.setStyleSheet("color: green; font-weight: bold;")
        health_layout.addWidget(QLabel("丢包率:"), 1, 0)
        health_layout.addWidget(self.packet_loss_label, 1, 1)
        
        # Connection stability
        self.stability_label = QLabel("稳定")
        self.stability_label.setStyleSheet("color: green; font-weight: bold;")
        health_layout.addWidget(QLabel("连接稳定性:"), 1, 2)
        health_layout.addWidget(self.stability_label, 1, 3)
        
        network_layout.addWidget(health_group)
        
        # API connection data group
        api_group = QGroupBox("API连接数据")
        api_layout = QVBoxLayout(api_group)
        api_layout.setSpacing(4)
        
        # Connection stats table
        self.connection_stats_table = QTableWidget()
        self.connection_stats_table.setColumnCount(4)
        self.connection_stats_table.setHorizontalHeaderLabels(["IP地址", "端口", "响应时间(ms)", "状态"])
        self.connection_stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.connection_stats_table.horizontalHeader().setStretchLastSection(True)
        self.connection_stats_table.setMinimumHeight(120)
        api_layout.addWidget(self.connection_stats_table)
        
        network_layout.addWidget(api_group)
        
        # Network adaptation controls
        controls_group = QGroupBox("网络适配控制")
        controls_layout = QHBoxLayout(controls_group)
        controls_layout.setSpacing(4)
        
        # Environment switch buttons
        env_layout = QVBoxLayout()
        env_label = QLabel("环境切换")
        env_label.setAlignment(Qt.AlignCenter)
        env_layout.addWidget(env_label)
        
        env_btn_layout = QHBoxLayout()
        self.testnet_btn = QPushButton("测试网")
        self.testnet_btn.setObjectName("warning")
        self.testnet_btn.clicked.connect(lambda: self.switch_env(is_test=True))
        env_btn_layout.addWidget(self.testnet_btn)
        
        self.mainnet_btn = QPushButton("主网")
        self.mainnet_btn.setObjectName("primary")
        self.mainnet_btn.clicked.connect(lambda: self.switch_env(is_test=False))
        env_btn_layout.addWidget(self.mainnet_btn)
        
        env_layout.addLayout(env_btn_layout)
        controls_layout.addLayout(env_layout)
        
        # Manual adaptation button
        self.manual_adapt_btn = QPushButton("手动适配网络")
        self.manual_adapt_btn.setObjectName("secondary")
        self.manual_adapt_btn.clicked.connect(self.manual_network_adaptation)
        controls_layout.addWidget(self.manual_adapt_btn)
        
        # Refresh status button
        self.refresh_status_btn = QPushButton("刷新状态")
        self.refresh_status_btn.setObjectName("secondary")
        self.refresh_status_btn.clicked.connect(self.refresh_network_status)
        controls_layout.addWidget(self.refresh_status_btn)
        
        controls_layout.addStretch()
        network_layout.addWidget(controls_group)
        
        # Add to tab widget
        self.tab_widget.addTab(network_tab, "网络状态")
    
    def init_log_tab(self):
        """Initialize log tab"""
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        log_layout.setSpacing(4)
        log_layout.setContentsMargins(4, 4, 4, 4)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #f5f5f5; font-family: Consolas, monospace;")
        
        log_layout.addWidget(self.log_text)
        self.tab_widget.addTab(log_tab, "日志")
    
    def init_config_tab(self):
        """Initialize configuration management tab focused on API login"""
        config_tab = QWidget()
        config_layout = QVBoxLayout(config_tab)
        config_layout.setSpacing(4)
        config_layout.setContentsMargins(4, 4, 4, 4)
        
        # API Login Status
        # Initialize with login state from config
        if self.config['api'].get('is_logged_in', False):
            self.login_status = QLabel("登录状态: 已登录")
            self.login_status.setStyleSheet("font-weight: bold; color: green;")
        else:
            self.login_status = QLabel("登录状态: 未登录")
            self.login_status.setStyleSheet("font-weight: bold; color: red;")
        config_layout.addWidget(self.login_status)
        
        # API Configuration Group
        api_config_group = QGroupBox("API登录配置")
        api_config_layout = QFormLayout(api_config_group)
        api_config_layout.setSpacing(4)
        
        # API Key
        self.api_key_edit = QLineEdit(self.config['api']['api_key'])
        api_config_layout.addRow("API Key:", self.api_key_edit)
        
        # API Secret (masked)
        self.api_secret_edit = QLineEdit(self.config['api']['api_secret'])
        self.api_secret_edit.setEchoMode(QLineEdit.Password)
        api_config_layout.addRow("API Secret:", self.api_secret_edit)
        
        # Passphrase
        self.passphrase_edit = QLineEdit(self.config['api']['passphrase'])
        self.passphrase_edit.setEchoMode(QLineEdit.Password)
        api_config_layout.addRow("Passphrase:", self.passphrase_edit)
        
        # API URL
        self.api_url_edit = QLineEdit(self.config['api']['api_url'])
        api_config_layout.addRow("API URL:", self.api_url_edit)
        
        # Timeout
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 120)
        self.timeout_spin.setValue(self.config['api']['timeout'])
        api_config_layout.addRow("超时时间 (秒):", self.timeout_spin)
        
        # Login/Logout Buttons
        auth_layout = QHBoxLayout()
        auth_layout.setSpacing(4)
        
        self.api_login_btn = QPushButton("登录API")
        self.api_login_btn.clicked.connect(self.api_login)
        self.api_login_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        auth_layout.addWidget(self.api_login_btn)
        
        self.api_logout_btn = QPushButton("登出API")
        self.api_logout_btn.clicked.connect(self.api_logout)
        self.api_logout_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        auth_layout.addWidget(self.api_logout_btn)
        
        # Set button states based on login state
        is_logged_in = self.config['api'].get('is_logged_in', False)
        self.api_login_btn.setEnabled(not is_logged_in)
        self.api_logout_btn.setEnabled(is_logged_in)
        
        # Test Connection Button
        self.test_conn_btn = QPushButton("测试连接")
        self.test_conn_btn.clicked.connect(self.test_api_connection)
        self.test_conn_btn.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold;")
        auth_layout.addWidget(self.test_conn_btn)
        
        # Save Configuration Button
        self.save_config_btn = QPushButton("保存配置")
        self.save_config_btn.clicked.connect(self.save_config)
        self.save_config_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        auth_layout.addWidget(self.save_config_btn)
        
        # Connection Status
        self.connection_status = QLabel("连接状态: 未测试")
        self.connection_status.setStyleSheet("font-weight: bold; color: orange;")
        
        # Monitoring Configuration Group
        monitoring_group = QGroupBox("监控配置")
        
        # 结束配置页面的布局
        config_layout.addWidget(api_config_group)
        config_layout.addLayout(auth_layout)
        config_layout.addWidget(self.connection_status)
        config_layout.addWidget(monitoring_group)
        
        # 添加标签页
        self.tab_widget.addTab(config_tab, "配置")
        
        # 显示主窗口
        self.show()
        
    def save_config(self):
        """保存配置"""
        try:
            # 更新配置
            self.config['api']['api_key'] = self.api_key_edit.text()
            self.config['api']['api_secret'] = self.api_secret_edit.text()
            self.config['api']['passphrase'] = self.passphrase_edit.text()
            
            # 保存到文件
            import json
            import os
            config_path = "config/okx_config.json"
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            
            QMessageBox.information(self, "成功", "配置保存成功！")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置失败: {str(e)}")
    
    def on_symbol_change(self, symbol):
        """交易对变更处理"""
        self.current_symbol = symbol
        self.update_market_data()
    
    def update_market_data(self):
        """更新市场数据"""
        try:
            # 获取当前选中的交易对
            symbol = self.symbol_combo.currentText()
            
            # 从交易机器人获取市场数据智能体
            market_data_agent = self.trading_bot.get_agent("market_data_agent")
            if not market_data_agent:
                self.log("市场数据智能体未初始化")
                return
            
            # 确保交易对已订阅
            if symbol not in market_data_agent.get_subscribed_symbols():
                market_data_agent.subscribe_symbol(symbol)
            
            # 直接获取市场数据
            market_data = market_data_agent.get_market_data(symbol)
            if market_data:
                # 更新行情数据
                self.ticker_price.setText(f"{market_data['price']:.2f}")
                
                # 计算涨跌幅
                change = market_data['change']
                change_pct = market_data['change_pct'] * 100
                
                # 设置涨跌颜色
                if change >= 0:
                    self.ticker_change.setStyleSheet("color: #10b981; font-weight: bold;")
                    self.ticker_change_pct.setStyleSheet("color: #10b981; font-weight: bold;")
                else:
                    self.ticker_change.setStyleSheet("color: #ef4444; font-weight: bold;")
                    self.ticker_change_pct.setStyleSheet("color: #ef4444; font-weight: bold;")
                
                self.ticker_change.setText(f"{change:.2f}")
                self.ticker_change_pct.setText(f"{change_pct:.2f}%")
                
                # 更新最后更新时间
                from datetime import datetime
                current_time = datetime.now().strftime("%H:%M:%S")
                self.last_update_time.setText(f"更新时间: {current_time}")
                
                self.log(f"更新市场数据成功: {symbol}")
            else:
                self.log("获取市场数据失败")
        except Exception as e:
            self.log(f"更新市场数据失败: {e}")
    
    def update_all_data(self):
        """更新所有数据"""
        try:
            # 更新市场数据
            self.update_market_data()
            
            # 更新K线图
            self.update_chart()
            
            # 更新订单信息
            self.update_orders()
            
            # 更新账户信息
            self.update_account_info()
            
            # 更新网络状态
            self.update_network_status()
            
            self.log("更新所有数据完成")
        except Exception as e:
            self.log(f"更新所有数据失败: {e}")
    
    def update_orders(self):
        """更新订单信息"""
        try:
            # 从交易机器人获取订单管理智能体
            order_agent = self.trading_bot.get_agent("order_agent")
            if not order_agent:
                self.log("订单管理智能体未初始化")
                return
            
            # 获取当前选中的交易对
            symbol = self.symbol_combo.currentText()
            
            # 获取订单信息
            orders = order_agent.get_orders(symbol)
            if orders:
                # 清空订单表格
                self.orders_table.setRowCount(0)
                
                # 填充订单数据
                for order in orders:
                    row_position = self.orders_table.rowCount()
                    self.orders_table.insertRow(row_position)
                    
                    # 填充订单信息
                    self.orders_table.setItem(row_position, 0, QTableWidgetItem(order.get('ordId', '')))
                    self.orders_table.setItem(row_position, 1, QTableWidgetItem(order.get('instId', '')))
                    self.orders_table.setItem(row_position, 2, QTableWidgetItem(order.get('side', '')))
                    self.orders_table.setItem(row_position, 3, QTableWidgetItem(order.get('ordType', '')))
                    self.orders_table.setItem(row_position, 4, QTableWidgetItem(str(order.get('px', 0))))
                    self.orders_table.setItem(row_position, 5, QTableWidgetItem(str(order.get('sz', 0))))
                    self.orders_table.setItem(row_position, 6, QTableWidgetItem(order.get('state', '')))
                    self.orders_table.setItem(row_position, 7, QTableWidgetItem(order.get('posSide', '')))
                    self.orders_table.setItem(row_position, 8, QTableWidgetItem(order.get('tdMode', '')))
                    self.orders_table.setItem(row_position, 9, QTableWidgetItem(order.get('clOrdId', '')))
                
                self.log(f"更新订单信息成功，共 {len(orders)} 个订单")
            else:
                self.log("获取订单信息失败")
        except Exception as e:
            self.log(f"更新订单信息失败: {e}")
    
    def update_account_info(self):
        """更新账户信息"""
        try:
            # 从交易机器人获取风险控制智能体
            risk_agent = self.trading_bot.get_agent("risk_management_agent")
            if not risk_agent:
                self.log("风险控制智能体未初始化")
                return
            
            # 获取账户余额
            balance = risk_agent.get_account_balance()
            if balance:
                # 更新余额信息
                self.available_balance.setText(f"{balance.get('availBal', 0):.2f}")
                self.total_balance.setText(f"{balance.get('totalEq', 0):.2f}")
                
                # 获取持仓信息
                positions = risk_agent.get_positions()
                if positions:
                    # 计算未实现盈亏
                    unrealized_pnl = sum(float(pos.get('upl', 0)) for pos in positions)
                    self.unrealized_pnl.setText(f"{unrealized_pnl:.2f}")
                
                self.log("更新账户信息成功")
            else:
                self.log("获取账户信息失败")
        except Exception as e:
            self.log(f"更新账户信息失败: {e}")
    
    def update_network_status(self):
        """更新网络状态"""
        try:
            # 从交易机器人获取市场数据智能体
            market_data_agent = self.trading_bot.get_agent("market_data_agent")
            if not market_data_agent:
                self.log("市场数据智能体未初始化")
                return
            
            # 获取网络状态
            network_status = market_data_agent.get_network_status()
            if network_status:
                # 更新网络状态信息
                self.current_ip_label.setText(network_status.get('current_ip', '未检测'))
                self.response_time_label.setText(f"{network_status.get('response_times', {}).get(network_status.get('current_ip'), 0)} ms")
                
                # 更新连接状态
                if network_status.get('connection_status', False):
                    self.connection_status_label.setText("正常")
                    self.connection_status_label.setStyleSheet("color: green; font-weight: bold;")
                else:
                    self.connection_status_label.setText("异常")
                    self.connection_status_label.setStyleSheet("color: red; font-weight: bold;")
                
                # 更新DNS状态
                dns_stats = network_status.get('dns_stats', {})
                if dns_stats.get('success_count', 0) > 0:
                    self.dns_status_label.setText("正常")
                    self.dns_status_label.setStyleSheet("color: green; font-weight: bold;")
                else:
                    self.dns_status_label.setText("异常")
                    self.dns_status_label.setStyleSheet("color: red; font-weight: bold;")
                
                self.log("更新网络状态成功")
            else:
                self.log("获取网络状态失败")
        except Exception as e:
            self.log(f"更新网络状态失败: {e}")
    
    def update_chart(self):
        """更新K线图数据"""
        if not HAS_MPL:
            return
        
        try:
            # 获取当前选中的交易对和时间周期
            symbol = self.symbol_combo.currentText()
            timeframe = self.timeframe_combo.currentText()
            
            # 从交易机器人获取市场数据智能体
            market_data_agent = self.trading_bot.get_agent("market_data_agent")
            if not market_data_agent:
                self.log("市场数据智能体未初始化")
                return
            
            # 尝试从API获取K线数据
            try:
                from okx_api_client import OKXAPIClient
                api_client = OKXAPIClient()
                candles = api_client.get_candlesticks(symbol, timeframe, limit=100)
                
                if candles:
                    # 处理K线数据
                    import pandas as pd
                    import numpy as np
                    
                    # 转换数据格式
                    data = []
                    for candle in candles:
                        timestamp, open_price, high, low, close, volume = candle[:6]
                        data.append({
                            'Date': pd.to_datetime(int(timestamp), unit='ms'),
                            'Open': float(open_price),
                            'High': float(high),
                            'Low': float(low),
                            'Close': float(close),
                            'Volume': float(volume)
                        })
                    
                    # 创建DataFrame
                    df = pd.DataFrame(data)
                    df.set_index('Date', inplace=True)
                    
                    # 清空当前图表
                    self.figure.clear()
                    
                    # 创建子图
                    ax = self.figure.add_subplot(111)
                    
                    # 绘制K线图
                    mpf.plot(
                        df, 
                        type='candle', 
                        style='charles', 
                        ax=ax, 
                        show_nontrading=False,
                        volume=True
                    )
                    
                    # 刷新画布
                    self.canvas.draw()
                    
                    self.log(f"更新K线图成功: {symbol} {timeframe}")
                else:
                    self.log("获取K线数据失败")
                    
            except Exception as e:
                self.log(f"获取K线数据失败: {e}")
                
                # 生成模拟数据用于测试
                import pandas as pd
                import numpy as np
                
                # 生成模拟数据
                dates = pd.date_range(end=pd.Timestamp.now(), periods=100, freq=timeframe)
                np.random.seed(42)
                close = 50000 + np.cumsum(np.random.randn(100) * 100)
                open_ = close.shift(1).fillna(50000)
                high = np.maximum(open_, close) + np.random.randn(100) * 50
                low = np.minimum(open_, close) - np.random.randn(100) * 50
                volume = np.random.randint(100, 1000, 100)
                
                df = pd.DataFrame({
                    'Open': open_,
                    'High': high,
                    'Low': low,
                    'Close': close,
                    'Volume': volume
                }, index=dates)
                
                # 清空当前图表
                self.figure.clear()
                
                # 创建子图
                ax = self.figure.add_subplot(111)
                
                # 绘制K线图
                mpf.plot(
                    df, 
                    type='candle', 
                    style='charles', 
                    ax=ax, 
                    show_nontrading=False,
                    volume=True
                )
                
                # 刷新画布
                self.canvas.draw()
                
                self.log("使用模拟数据更新K线图")
                
        except Exception as e:
            self.log(f"更新K线图失败: {e}")
    
    def batch_place_orders(self):
        """批量下单"""
        # 这里可以添加批量下单的逻辑
        pass
    
    def batch_cancel_orders(self):
        """批量撤单"""
        # 这里可以添加批量撤单的逻辑
        pass
    
    def batch_amend_orders(self):
        """批量改单"""
        # 这里可以添加批量改单的逻辑
        pass
    
    def place_order(self):
        """下单"""
        # 这里可以添加下单的逻辑
        pass
    
    def cancel_selected_order(self):
        """取消选中的订单"""
        # 这里可以添加取消选中订单的逻辑
        pass
    
    def amend_selected_order(self):
        """修改选中的订单"""
        # 这里可以添加修改选中订单的逻辑
        pass
    
    def select_all_orders(self):
        """选择所有订单"""
        # 这里可以添加选择所有订单的逻辑
        pass
    
    def clear_order_selection(self):
        """清除订单选择"""
        # 这里可以添加清除订单选择的逻辑
        pass
    
    def start_strategy(self):
        """启动策略"""
        try:
            # 获取策略配置
            strategy_name = self.strategy_combo.currentText()
            mode = self.strategy_mode_combo.currentText()
            timeframe = self.timeframe_combo.currentText()
            grid_spacing = self.grid_spacing.value()
            grid_multiplier = self.grid_multiplier.value()
            max_leverage = self.max_leverage.value()
            stop_loss_pct = self.stop_loss_pct.value()
            take_profit_pct = self.take_profit_pct.value()
            
            # 从交易机器人中获取策略执行智能体
            strategy_agent = self.trading_bot.get_agent("strategy_execution_agent")
            if not strategy_agent:
                QMessageBox.error(self, "错误", "策略执行智能体未初始化")
                return
            
            # 构建策略配置
            strategy_config = {
                "mode": mode,
                "timeframe": timeframe,
                "grid_spacing": grid_spacing,
                "grid_multiplier": grid_multiplier,
                "max_leverage": max_leverage,
                "stop_loss_pct": stop_loss_pct,
                "take_profit_pct": take_profit_pct
            }
            
            # 启动策略
            success = strategy_agent.activate_strategy(strategy_name, strategy_config)
            
            if success:
                self.strategy_status.setText("状态: 运行中")
                self.strategy_status.setStyleSheet("font-weight: bold; color: green;")
                self.log(f"策略 {strategy_name} 启动成功")
                QMessageBox.information(self, "成功", f"策略 {strategy_name} 启动成功")
            else:
                self.strategy_status.setText("状态: 启动失败")
                self.strategy_status.setStyleSheet("font-weight: bold; color: red;")
                self.log(f"策略 {strategy_name} 启动失败")
                QMessageBox.error(self, "错误", f"策略 {strategy_name} 启动失败")
        except Exception as e:
            self.log(f"启动策略失败: {e}")
            QMessageBox.error(self, "错误", f"启动策略时出错: {str(e)}")
    
    def stop_strategy(self):
        """停止策略"""
        try:
            # 获取当前策略名称
            strategy_name = self.strategy_combo.currentText()
            
            # 从交易机器人中获取策略执行智能体
            strategy_agent = self.trading_bot.get_agent("strategy_execution_agent")
            if not strategy_agent:
                QMessageBox.error(self, "错误", "策略执行智能体未初始化")
                return
            
            # 停止策略
            success = strategy_agent.deactivate_strategy(strategy_name)
            
            if success:
                self.strategy_status.setText("状态: 已停止")
                self.strategy_status.setStyleSheet("font-weight: bold; color: black;")
                self.log(f"策略 {strategy_name} 停止成功")
                QMessageBox.information(self, "成功", f"策略 {strategy_name} 停止成功")
            else:
                self.strategy_status.setText("状态: 停止失败")
                self.strategy_status.setStyleSheet("font-weight: bold; color: red;")
                self.log(f"策略 {strategy_name} 停止失败")
                QMessageBox.error(self, "错误", f"策略 {strategy_name} 停止失败")
        except Exception as e:
            self.log(f"停止策略失败: {e}")
            QMessageBox.error(self, "错误", f"停止策略时出错: {str(e)}")
    
    def api_login(self):
        """API登录"""
        try:
            from okx_api_client import OKXAPIClient
            api_client = OKXAPIClient(
                api_key=self.api_key_edit.text(),
                api_secret=self.api_secret_edit.text(),
                passphrase=self.passphrase_edit.text(),
                is_test=self.config['api'].get('is_test', False)
            )
            
            # 测试获取服务器时间，验证API连接
            server_time = api_client.get_server_time()
            if server_time:
                # 登录成功
                self.config['api']['is_logged_in'] = True
                self.login_status.setText("登录状态: 已登录")
                self.login_status.setStyleSheet("font-weight: bold; color: green;")
                self.api_login_btn.setEnabled(False)
                self.api_logout_btn.setEnabled(True)
                QMessageBox.information(self, "成功", "API登录成功！")
            else:
                QMessageBox.warning(self, "警告", "API登录失败，请检查配置！")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"登录失败: {str(e)}")
    
    def api_logout(self):
        """API登出"""
        try:
            # 登出操作
            self.config['api']['is_logged_in'] = False
            self.login_status.setText("登录状态: 未登录")
            self.login_status.setStyleSheet("font-weight: bold; color: red;")
            self.api_login_btn.setEnabled(True)
            self.api_logout_btn.setEnabled(False)
            QMessageBox.information(self, "成功", "API登出成功！")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"登出失败: {str(e)}")
    
    def manual_network_adaptation(self):
        """手动网络适配"""
        # 这里可以添加手动网络适配的逻辑
        pass
    
    def refresh_network_status(self):
        """刷新网络状态"""
        # 这里可以添加刷新网络状态的逻辑
        pass
    
    def connect_signals(self):
        """连接信号"""
        # 连接日志更新信号
        self.update_log.connect(self.on_log_update)
        
        # 设置日志处理器，将日志输出到GUI
        from loguru import logger
        
        def gui_log_handler(message):
            """将日志消息发送到GUI"""
            log_message = message
            self.update_log.emit(log_message)
        
        # 添加日志处理器
        logger.add(gui_log_handler, format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}")
        
        # 订阅市场数据更新事件
        from commons.event_bus import global_event_bus
        global_event_bus.subscribe('market_data_updated', self.on_market_data_updated)
    
    def on_log_update(self, message):
        """处理日志更新信号"""
        if not self.is_closed:
            self.log_text.append(message)
    
    def on_market_data_updated(self, data):
        """处理市场数据更新事件"""
        try:
            symbol = data.get('symbol')
            market_data = data.get('data')
            
            # 只有当更新的交易对是当前选中的交易对时才更新界面
            if symbol == self.symbol_combo.currentText() and market_data:
                # 更新行情数据
                self.ticker_price.setText(f"{market_data['price']:.2f}")
                
                # 计算涨跌幅
                change = market_data['change']
                change_pct = market_data['change_pct'] * 100
                
                # 设置涨跌颜色
                if change >= 0:
                    self.ticker_change.setStyleSheet("color: #10b981; font-weight: bold;")
                    self.ticker_change_pct.setStyleSheet("color: #10b981; font-weight: bold;")
                else:
                    self.ticker_change.setStyleSheet("color: #ef4444; font-weight: bold;")
                    self.ticker_change_pct.setStyleSheet("color: #ef4444; font-weight: bold;")
                
                self.ticker_change.setText(f"{change:.2f}")
                self.ticker_change_pct.setText(f"{change_pct:.2f}%")
                
                # 更新最后更新时间
                from datetime import datetime
                current_time = datetime.now().strftime("%H:%M:%S")
                self.last_update_time.setText(f"更新时间: {current_time}")
        except Exception as e:
            self.log(f"处理市场数据更新事件失败: {e}")
    
    def log(self, message):
        """添加日志消息"""
        if not self.is_closed:
            self.update_log.emit(message)
    
    def init_config_monitor(self):
        """初始化配置监控"""
        # 这里可以添加初始化配置监控的逻辑
        pass
    
    def init_network_monitoring(self):
        """初始化网络监控"""
        try:
            # 从交易机器人获取市场数据智能体
            market_data_agent = self.trading_bot.get_agent("market_data_agent")
            if market_data_agent:
                # 订阅默认交易对
                market_data_agent.subscribe_symbol(self.symbol_combo.currentText())
                
                # 立即更新一次网络状态
                self.update_network_status()
                
                # 立即更新一次市场数据
                self.update_market_data()
                
                self.log("网络状态监控初始化完成")
            else:
                self.log("市场数据智能体未初始化，网络状态监控暂时不可用")
        except Exception as e:
            self.log(f"初始化网络状态监控失败: {e}")
    
    def on_font_size_change(self, index):
        """处理字体大小变化"""
        # 根据选择的索引获取字体大小
        font_sizes = {
            0: 8,   # 小
            1: 10,  # 中
            2: 12   # 大
        }
        
        font_size = font_sizes.get(index, 10)  # 默认中等大小
        
        # 生成新的样式表
        new_stylesheet = f"""
/* 主窗口样式 */
QMainWindow {{
    background-color: #f5f7fa;
    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
    font-size: {font_size}px;
}}

/* 标签页样式 */
QTabWidget {{
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    padding: 2px;
}}

QTabBar {{
    background-color: transparent;
}}

QTabBar::tab {{
    background-color: #f8f9fa;
    padding: 6px 10px;
    border: 1px solid #e0e0e0;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
    min-width: 70px;
    font-weight: 500;
    font-size: {font_size}px;
}}

QTabBar::tab:hover {{
    background-color: #e9ecef;
}}

QTabBar::tab:selected {{
    background-color: #ffffff;
    border-bottom: 1px solid #ffffff;
    font-weight: 600;
}}

/* 分组框样式 */
QGroupBox {{
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    margin-top: 6px;
    padding-top: 4px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px 0 4px;
    font-weight: 600;
    color: #2c3e50;
    font-size: {font_size}px;
}}

/* 按钮样式 */
QPushButton {{
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 3px;
    padding: 4px 8px;
    font-weight: 500;
    font-size: {font_size}px;
    min-height: 24px;
    min-width: 60px;
}}

QPushButton:hover {{
    background-color: #f8f9fa;
    border-color: #d0d0d0;
}}

QPushButton:pressed {{
    background-color: #e9ecef;
}}

/* 特殊按钮样式 */
QPushButton#primary {{
    background-color: #3b82f6;
    color: white;
    border-color: #3b82f6;
    font-weight: 600;
}}

QPushButton#primary:hover {{
    background-color: #2563eb;
    border-color: #2563eb;
}}

QPushButton#primary:pressed {{
    background-color: #1d4ed8;
}}

QPushButton#secondary {{
    background-color: #64748b;
    color: white;
    border-color: #64748b;
    font-weight: 600;
}}

QPushButton#secondary:hover {{
    background-color: #475569;
    border-color: #475569;
}}

QPushButton#warning {{
    background-color: #f59e0b;
    color: white;
    border-color: #f59e0b;
    font-weight: 600;
}}

QPushButton#warning:hover {{
    background-color: #d97706;
    border-color: #d97706;
}}

QPushButton#danger {{
    background-color: #ef4444;
    color: white;
    border-color: #ef4444;
    font-weight: 600;
}}

QPushButton#danger:hover {{
    background-color: #dc2626;
    border-color: #dc2626;
}}

/* 输入框样式 */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 3px;
    padding: 3px 6px;
    font-size: {font_size}px;
    min-height: 24px;
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 2px solid #3b82f6;
    outline: none;
}}

/* 表格样式 */
QTableWidget {{
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 3px;
    gridline-color: #f0f0f0;
    font-size: {font_size - 1}px;
}}

QTableWidget::item {{
    padding: 4px 6px;
    border-bottom: 1px solid #f8f9fa;
}}

QTableWidget::item:hover {{
    background-color: #f8f9fa;
}}

QTableWidget::item:selected {{
    background-color: #dbeafe;
    color: #1e40af;
}}

QHeaderView::section {{
    background-color: #f8f9fa;
    padding: 4px 6px;
    border: 1px solid #e0e0e0;
    font-weight: 600;
    color: #2c3e50;
    border-top-left-radius: 3px;
    border-top-right-radius: 3px;
    font-size: {font_size - 1}px;
}}

QHeaderView::section:hover {{
    background-color: #e9ecef;
}}

/* 文本编辑框样式 */
QTextEdit {{
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 3px;
    padding: 6px;
    font-size: {font_size}px;
    line-height: 1.3;
}}

QTextEdit[readOnly="true"] {{
    background-color: #f8f9fa;
    color: #64748b;
}}

/* 标签样式 */
QLabel {{
    color: #2c3e50;
    font-size: {font_size}px;
}}

QLabel#status {{
    font-weight: 600;
}}

QLabel#success {{
    color: #10b981;
    font-weight: 600;
}}

QLabel#warning {{
    color: #f59e0b;
    font-weight: 600;
}}

QLabel#error {{
    color: #ef4444;
    font-weight: 600;
}}

/* 控制栏样式 */
QWidget#controlBar {{
    background-color: #ffffff;
    border-bottom: 1px solid #e0e0e0;
    padding: 6px;
}}

/* 滚动条样式 */
QScrollBar:vertical {{
    background-color: #f8f9fa;
    width: 4px;
    border-radius: 2px;
}}

QScrollBar::handle:vertical {{
    background-color: #cbd5e1;
    border-radius: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: #94a3b8;
}}

QScrollBar:horizontal {{
    background-color: #f8f9fa;
    height: 4px;
    border-radius: 2px;
}}

QScrollBar::handle:horizontal {{
    background-color: #cbd5e1;
    border-radius: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: #94a3b8;
}}

/* 分隔器样式 */
QSplitter::handle {{
    background-color: #e0e0e0;
    width: 2px;
    height: 2px;
}}

QSplitter::handle:hover {{
    background-color: #cbd5e1;
}}

/* 对话框样式 */
QDialog {{
    background-color: #ffffff;
    border-radius: 4px;
    font-size: {font_size}px;
}}

/* 表单布局样式 */
QFormLayout {{
    spacing: 4px;
}}

/* 表格列宽调整 */
QTableWidget QHeaderView {{
    font-size: {font_size - 1}px;
}}
"""
        
        # 应用新的样式表
        self.setStyleSheet(new_stylesheet)
        
        # 递归更新所有子部件的字体大小
        def update_font_recursive(widget):
            if hasattr(widget, 'setFont'):
                font = widget.font()
                font.setPointSize(font_size)
                widget.setFont(font)
            
            # 特殊处理表格和表头
            if hasattr(widget, 'horizontalHeader'):
                header = widget.horizontalHeader()
                if header:
                    header_font = header.font()
                    header_font.setPointSize(font_size - 1)
                    header.setFont(header_font)
            
            # 递归处理子部件
            for child in widget.children():
                if isinstance(child, QWidget):
                    update_font_recursive(child)
        
        # 从主窗口开始递归更新
        update_font_recursive(self)
        
        # 记录字体大小变更
        size_names = ["小", "中", "大"]
        self.log(f"字体大小已调整为: {size_names[index]}")
    
    def closeEvent(self, event):
        """处理窗口关闭事件"""
        # 只是隐藏窗口，不退出应用程序
        self.hide()
        # 阻止默认的关闭行为
        event.ignore()
        # 记录日志
        self.log("交易界面已最小化到后台运行")
    
    def resize_to_fit_screen(self):
        """调整窗口大小以适配屏幕分辨率"""
        try:
            # 获取屏幕几何信息
            screen = self.screen()
            screen_geometry = screen.geometry()
            screen_width = screen_geometry.width()
            screen_height = screen_geometry.height()
            
            # 计算适合的窗口大小（屏幕的80%）
            window_width = int(screen_width * 0.8)
            window_height = int(screen_height * 0.8)
            
            # 确保窗口大小不小于最小尺寸
            window_width = max(window_width, 1024)
            window_height = max(window_height, 768)
            
            # 计算窗口位置（居中）
            window_x = (screen_width - window_width) // 2
            window_y = (screen_height - window_height) // 2
            
            # 设置窗口大小和位置
            self.setGeometry(window_x, window_y, window_width, window_height)
            
            # 记录日志
            self.log(f"窗口大小已调整为: {window_width}x{window_height}")
        except Exception as e:
            self.log(f"调整窗口大小失败: {e}")
    
    def resize_window(self, width, height):
        """调整窗口大小为指定尺寸"""
        try:
            # 获取屏幕几何信息
            screen = self.screen()
            screen_geometry = screen.geometry()
            screen_width = screen_geometry.width()
            screen_height = screen_geometry.height()
            
            # 确保窗口大小不小于最小尺寸
            width = max(width, 1024)
            height = max(height, 768)
            
            # 计算窗口位置（居中）
            window_x = (screen_width - width) // 2
            window_y = (screen_height - height) // 2
            
            # 设置窗口大小和位置
            self.setGeometry(window_x, window_y, width, height)
            
            # 记录日志
            self.log(f"窗口大小已调整为: {width}x{height}")
        except Exception as e:
            self.log(f"调整窗口大小失败: {e}")
    
    def test_api_connection(self):
        """测试API连接"""
        try:
            from okx_api_client import OKXAPIClient
            api_client = OKXAPIClient(
                api_key=self.api_key_edit.text(),
                api_secret=self.api_secret_edit.text(),
                passphrase=self.passphrase_edit.text(),
                is_test=self.config['api'].get('is_test', False)
            )
            
            # 测试获取服务器时间
            server_time = api_client.get_server_time()
            if server_time:
                self.connection_status.setText("连接状态: 正常")
                self.connection_status.setStyleSheet("font-weight: bold; color: green;")
                QMessageBox.information(self, "成功", "API连接测试成功！")
            else:
                self.connection_status.setText("连接状态: 失败")
                self.connection_status.setStyleSheet("font-weight: bold; color: red;")
                QMessageBox.warning(self, "警告", "API连接测试失败，请检查配置！")
        except Exception as e:
            self.connection_status.setText("连接状态: 错误")
            self.connection_status.setStyleSheet("font-weight: bold; color: red;")
            QMessageBox.critical(self, "错误", f"测试连接失败: {str(e)}")

if __name__ == "__main__":
    import sys
    # 禁用PyQt5样式表警告
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    # 禁用样式表解析警告
    import os
    os.environ["QT_LOGGING_RULES"] = "qt.qpa.style.warning=false"
    app = QApplication(sys.argv)
    import json
    with open('config/okx_config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    # 创建一个模拟的trading_bot对象
    class MockTradingBot:
        def __init__(self):
            pass
    gui = TradingGUI(config, MockTradingBot())
    sys.exit(app.exec_())