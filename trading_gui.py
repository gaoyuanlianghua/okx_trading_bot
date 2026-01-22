import sys
import json
import threading
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget,
    QLabel, QPushButton, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QSplitter, QGroupBox, QFormLayout, QSpinBox, QDoubleSpinBox, QCheckBox,
    QTextEdit, QHeaderView, QFrame, QDialog, QScrollArea, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor

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
3. Socks5、HTTPS、HTTP 代理配置
4. WebSocket 连接管理和自动重连
5. 集中式配置管理
6. 增强的日志记录
7. 健康检查机制
8. 指数退避重试机制
9. DNS 解析和 SSL/TLS 指纹识别
10. 策略管理和执行""")
        features_layout.addWidget(features_text)
        content_layout.addWidget(features_group)
        
        # 快速开始
        quickstart_group = QGroupBox("快速开始")
        quickstart_layout = QVBoxLayout(quickstart_group)
        quickstart_text = QTextEdit()
        quickstart_text.setReadOnly(True)
        quickstart_text.setPlainText("""1. 进入"配置管理"标签页
2. 输入您的 OKX API 密钥、密钥密码和密码短语
3. 配置代理信息（如果需要）
4. 点击"保存配置"按钮
5. 切换到"交易"标签页
6. 选择交易对和模式
7. 点击"更新数据"按钮获取实时行情
8. 配置交易参数并点击"下单"按钮执行交易
9. 在"策略"标签页中配置和启动交易策略""")
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

代理配置：
- 启用代理: 勾选后启用代理
- 代理类型: 支持 SOCKS5、HTTP、HTTPS
- 代理地址: 代理服务器地址和端口，格式为：协议://IP:端口

网络适配：
- 环境切换: 支持在测试网和主网之间切换
- DNS 配置: 可以选择 DNS 区域和服务器
- 负载均衡: 支持轮询和响应时间优先策略""")
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
   - 能够锁定利润""")
        strategy_layout.addWidget(strategy_text)
        content_layout.addWidget(strategy_group)
        
        # 常见问题
        faq_group = QGroupBox("常见问题")
        faq_layout = QVBoxLayout(faq_group)
        faq_text = QTextEdit()
        faq_text.setReadOnly(True)
        faq_text.setPlainText("""Q: 连接失败怎么办？
A: 检查 API 密钥是否正确，检查网络连接和代理配置，检查防火墙设置。

Q: GUI 冻结怎么办？
A: 等待一段时间，机器人会自动恢复，或尝试重启程序。

Q: WebSocket 断开怎么办？
A: 机器人会自动重连，检查网络稳定性。

Q: 如何查看日志？
A: 进入"日志"标签页查看实时日志，日志文件位于 logs/ 目录下。

Q: 如何切换环境？
A: 在"网络状态"标签页中点击"测试网"或"主网"按钮切换环境。""")
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
- v1.0.0: 初始版本，支持 OKX REST API 和 WebSocket，Socks5 代理支持，PyQt5 GUI 界面，集中式配置管理，增强的日志记录，健康检查机制""")
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
        config_path = "d:\\Projects\\okx_trading_bot\\config\\okx_config.json"
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
        config_path = "d:\\Projects\\okx_trading_bot\\config\\okx_config.json"
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
        
        # GUI状态标志位，用于线程安全检查
        self.is_closed = False
        
        # Initialize timer for data updates
        self.timer = QTimer()
        
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
        
        # 初始化智能体系统交互
        self.init_agent_interaction()
        
        # 初始化配置文件监控
        self.init_config_monitor()
        
        # 初始化网络状态监控
        self.init_network_monitoring()
    
    def init_agent_interaction(self):
        """
        初始化智能体系统交互
        """
        try:
            self.log("开始初始化智能体系统交互...")
            
            # 从commons导入事件总线和智能体注册表
            from commons.event_bus import global_event_bus
            
            # 注册事件监听器
            self.register_event_listeners(global_event_bus)
            
            # 初始化服务
            self.init_services()
            
            # 初始化策略管理UI
            self.init_strategy_management()
            
            # 初始化智能体状态监控
            self.init_agent_status_monitor()
            
            self.log("智能体系统交互初始化完成")
        except Exception as e:
            self.log(f"初始化智能体系统交互失败: {e}")
            import traceback
            self.log(traceback.format_exc())
    
    def register_event_listeners(self, event_bus):
        """
        注册事件监听器
        """
        try:
            # 注册市场数据更新事件
            event_bus.subscribe('market_data_updated', self.on_market_data_updated)
            
            # 注册订单相关事件
            event_bus.subscribe('order_placed', self.on_order_placed)
            event_bus.subscribe('order_updated', self.on_order_updated)
            event_bus.subscribe('order_canceled', self.on_order_canceled)
            
            # 注册风险相关事件
            event_bus.subscribe('risk_alert', self.on_risk_alert)
            event_bus.subscribe('risk_state_updated', self.on_risk_state_updated)
            
            # 注册策略相关事件
            event_bus.subscribe('strategy_registered', self.on_strategy_registered)
            event_bus.subscribe('strategy_activated', self.on_strategy_activated)
            event_bus.subscribe('strategy_deactivated', self.on_strategy_deactivated)
            event_bus.subscribe('strategy_paused', self.on_strategy_paused)
            event_bus.subscribe('strategy_resumed', self.on_strategy_resumed)
            
            # 注册系统状态事件
            event_bus.subscribe('system_state_updated', self.on_system_state_updated)
            
            self.log("事件监听器注册完成")
        except Exception as e:
            self.log(f"注册事件监听器失败: {e}")
            import traceback
            self.log(traceback.format_exc())
    
    def on_strategy_paused(self, data):
        """
        处理策略暂停事件
        """
        try:
            strategy_name = data.get("strategy_name")
            self.log(f"策略已暂停: {strategy_name}")
            # 更新策略列表
            if hasattr(self, 'load_strategy_list'):
                self.load_strategy_list()
        except Exception as e:
            self.log(f"处理策略暂停事件失败: {e}")
    
    def on_strategy_resumed(self, data):
        """
        处理策略恢复事件
        """
        try:
            strategy_name = data.get("strategy_name")
            self.log(f"策略已恢复: {strategy_name}")
            # 更新策略列表
            if hasattr(self, 'load_strategy_list'):
                self.load_strategy_list()
        except Exception as e:
            self.log(f"处理策略恢复事件失败: {e}")
    
    def init_config_monitor(self):
        """Initialize configuration file monitoring"""
        try:
            # Create watchdog observer
            self.config_observer = Observer()
            config_path = "d:\Projects\okx_trading_bot\config"
            self.config_observer.schedule(
                ConfigFileHandler(self),
                config_path,
                recursive=False
            )
            self.config_observer.start()
            self.log("配置文件监控已启动")
        except Exception as e:
            self.log(f"初始化配置文件监控失败: {e}")
    
    def init_services(self):
        """
        在后台线程中初始化服务
        """
        try:
            self.log("开始初始化服务...")
            
            # 初始化API客户端和相关服务
            self.restart_api_client()
            
            # 初始化WebSocket client
            self.init_websocket_client()
            
            # Initialize data update timers
            self.init_data_updates()
            
            # Initialize health check timer
            self.init_health_check()
            
            # 初始数据更新
            self.update_all_data()
            
            self.log("服务初始化完成")
        except Exception as e:
            self.log(f"初始化服务失败: {e}")
            import traceback
            self.log(traceback.format_exc())
    
    def init_strategy_management(self):
        """
        初始化策略管理UI
        """
        try:
            self.log("开始初始化策略管理UI...")
            
            # 查找现有的标签页
            tab_widget = None
            for widget in self.centralWidget().children():
                if isinstance(widget, QTabWidget):
                    tab_widget = widget
                    break
            
            if not tab_widget:
                self.log("未找到标签页控件，无法初始化策略管理UI")
                return
            
            # 创建策略管理标签页
            strategy_tab = QWidget()
            strategy_layout = QVBoxLayout(strategy_tab)
            
            # 策略列表
            strategy_list_group = QGroupBox("策略列表")
            strategy_list_layout = QVBoxLayout(strategy_list_group)
            
            # 策略选择器
            strategy_layout_1 = QHBoxLayout()
            strategy_layout_1.addWidget(QLabel("策略:"))
            self.strategy_combo = QComboBox()
            strategy_layout_1.addWidget(self.strategy_combo)
            
            # 策略控制按钮
            self.activate_strategy_btn = QPushButton("激活策略")
            self.activate_strategy_btn.clicked.connect(self.activate_strategy)
            self.activate_strategy_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
            strategy_layout_1.addWidget(self.activate_strategy_btn)
            
            self.deactivate_strategy_btn = QPushButton("停用策略")
            self.deactivate_strategy_btn.clicked.connect(self.deactivate_strategy)
            self.deactivate_strategy_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
            strategy_layout_1.addWidget(self.deactivate_strategy_btn)
            
            self.reload_strategy_btn = QPushButton("重新加载")
            self.reload_strategy_btn.clicked.connect(self.reload_strategy)
            strategy_layout_1.addWidget(self.reload_strategy_btn)
            
            strategy_list_layout.addLayout(strategy_layout_1)
            
            # 策略列表表格
            self.strategy_table = QTableWidget()
            self.strategy_table.setColumnCount(5)
            self.strategy_table.setHorizontalHeaderLabels(["策略名称", "状态", "类型", "总交易次数", "总收益"])
            self.strategy_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            strategy_list_layout.addWidget(self.strategy_table)
            
            # 策略参数设置
            strategy_params_group = QGroupBox("策略参数设置")
            strategy_params_layout = QVBoxLayout(strategy_params_group)
            
            # 参数编辑区域
            self.strategy_params_edit = QTextEdit()
            self.strategy_params_edit.setPlaceholderText("策略参数JSON格式")
            strategy_params_layout.addWidget(self.strategy_params_edit)
            
            # 保存参数按钮
            self.save_params_btn = QPushButton("保存参数")
            self.save_params_btn.clicked.connect(self.save_strategy_params)
            self.save_params_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
            strategy_params_layout.addWidget(self.save_params_btn)
            
            # 添加到主布局
            strategy_layout.addWidget(strategy_list_group)
            strategy_layout.addWidget(strategy_params_group)
            
            # 添加策略管理标签页
            tab_widget.addTab(strategy_tab, "策略管理")
            
            # 加载策略列表
            self.load_strategy_list()
            
            self.log("策略管理UI初始化完成")
        except Exception as e:
            self.log(f"初始化策略管理UI失败: {e}")
            import traceback
            self.log(traceback.format_exc())
    
    def init_agent_status_monitor(self):
        """
        初始化智能体状态监控
        """
        try:
            self.log("开始初始化智能体状态监控...")
            
            # 查找现有的标签页
            tab_widget = None
            for widget in self.centralWidget().children():
                if isinstance(widget, QTabWidget):
                    tab_widget = widget
                    break
            
            if not tab_widget:
                self.log("未找到标签页控件，无法初始化智能体状态监控")
                return
            
            # 创建智能体状态标签页
            agent_tab = QWidget()
            agent_layout = QVBoxLayout(agent_tab)
            
            # 智能体状态列表
            agent_status_group = QGroupBox("智能体状态")
            agent_status_layout = QVBoxLayout(agent_status_group)
            
            # 智能体状态表格
            self.agent_status_table = QTableWidget()
            self.agent_status_table.setColumnCount(4)
            self.agent_status_table.setHorizontalHeaderLabels(["智能体ID", "类型", "状态", "运行时间"])
            self.agent_status_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            agent_status_layout.addWidget(self.agent_status_table)
            
            # 系统状态
            system_status_group = QGroupBox("系统状态")
            system_status_layout = QGridLayout(system_status_group)
            
            # 系统状态指标
            self.system_status_labels = {
                "total_agents": QLabel("0"),
                "running_agents": QLabel("0"),
                "active_strategies": QLabel("0"),
                "active_symbols": QLabel("0")
            }
            
            system_status_layout.addWidget(QLabel("总智能体数:"), 0, 0)
            system_status_layout.addWidget(self.system_status_labels["total_agents"], 0, 1)
            system_status_layout.addWidget(QLabel("运行中智能体:"), 0, 2)
            system_status_layout.addWidget(self.system_status_labels["running_agents"], 0, 3)
            system_status_layout.addWidget(QLabel("活跃策略数:"), 1, 0)
            system_status_layout.addWidget(self.system_status_labels["active_strategies"], 1, 1)
            system_status_layout.addWidget(QLabel("活跃交易对:"), 1, 2)
            system_status_layout.addWidget(self.system_status_labels["active_symbols"], 1, 3)
            
            # 风险状态
            risk_status_group = QGroupBox("风险状态")
            risk_status_layout = QGridLayout(risk_status_group)
            
            self.risk_status_labels = {
                "total_position_value": QLabel("0"),
                "total_orders": QLabel("0"),
                "current_drawdown": QLabel("0%")
            }
            
            risk_status_layout.addWidget(QLabel("总持仓价值:"), 0, 0)
            risk_status_layout.addWidget(self.risk_status_labels["total_position_value"], 0, 1)
            risk_status_layout.addWidget(QLabel("总订单数:"), 0, 2)
            risk_status_layout.addWidget(self.risk_status_labels["total_orders"], 0, 3)
            risk_status_layout.addWidget(QLabel("当前回撤:"), 1, 0)
            risk_status_layout.addWidget(self.risk_status_labels["current_drawdown"], 1, 1)
            
            # 添加到主布局
            agent_layout.addWidget(agent_status_group)
            agent_layout.addWidget(system_status_group)
            agent_layout.addWidget(risk_status_group)
            
            # 添加智能体状态标签页
            tab_widget.addTab(agent_tab, "智能体状态")
            
            # 加载智能体状态
            self.load_agent_status()
            
            # 定时更新智能体状态
            self.agent_status_timer = QTimer()
            self.agent_status_timer.timeout.connect(self.load_agent_status)
            self.agent_status_timer.start(5000)  # 每5秒更新一次
            
            self.log("智能体状态监控初始化完成")
        except Exception as e:
            self.log(f"初始化智能体状态监控失败: {e}")
            import traceback
            self.log(traceback.format_exc())
    
    def update_dns_config_display(self):
        """
        更新DNS配置显示
        """
        current_region = self.api_client.get_dns_config().get('region', 'global')
        self.dns_region_combo.setCurrentText(current_region)
        self.current_dns_servers.setText(", ".join(self.api_client.get_dns_config()['servers']))
    
    def manual_network_adaptation(self):
        """Handle manual network adaptation request"""
        self.log("开始手动网络适配...")
        self.manual_adapt_btn.setEnabled(False)
        
        # Run network adaptation in a separate thread to avoid blocking GUI
        def run_adaptation():
            try:
                from okx_api_client import OKXAPIClient
                api_client = OKXAPIClient()
                success = api_client.run_network_adapter(auto_update=True)
                
                # Update GUI on main thread
                self.app.thread().postEvent(self, type("Event", (), {}))
                
                if success:
                    self.log("手动网络适配完成，配置已更新")
                    self.refresh_network_status()
                else:
                    self.log("手动网络适配失败")
            except Exception as e:
                self.log(f"手动网络适配出错: {e}")
            finally:
                # Re-enable button on main thread
                self.app.thread().postEvent(self, type("Event", (), {}))
        
        import threading
        thread = threading.Thread(target=run_adaptation)
        thread.daemon = True
        thread.start()
        
        # Re-enable button
        self.manual_adapt_btn.setEnabled(True)
    
    def refresh_network_status(self):
        """Refresh network status display"""
        self.log("刷新网络状态...")
        self.update_network_status()
    
    def update_network_status(self):
        """Update network status from API client with detailed health indicators"""
        try:
            from okx_api_client import OKXAPIClient
            
            # Get network status from API client
            api_client = OKXAPIClient()
            network_status = api_client.get_network_status()
            
            # Update current IP address
            current_ip = network_status.get("current_ip", "未检测")
            self.current_ip_label.setText(current_ip)
            
            # Test connection and get response time
            start_time = time.time()
            connection_ok = api_client.test_network_connection()
            response_time = int((time.time() - start_time) * 1000)
            
            # Update connection status
            if connection_ok:
                self.connection_status_label.setText("已连接")
                self.connection_status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.connection_status_label.setText("连接失败")
                self.connection_status_label.setStyleSheet("color: red; font-weight: bold;")
            
            # Update response time with color coding
            self.response_time_label.setText(f"{response_time} ms")
            if response_time < 200:
                self.response_time_label.setStyleSheet("color: green; font-weight: bold;")
            elif response_time < 500:
                self.response_time_label.setStyleSheet("color: orange; font-weight: bold;")
            else:
                self.response_time_label.setStyleSheet("color: red; font-weight: bold;")
            
            # Update WebSocket status if available
            if hasattr(self, 'ws_client') and self.ws_client:
                # 检查WebSocket连接状态，使用实际存在的属性
                try:
                    # 检查public_connected和private_connected属性
                    public_connected = hasattr(self.ws_client, 'public_connected') and self.ws_client.public_connected
                    private_connected = hasattr(self.ws_client, 'private_connected') and self.ws_client.private_connected
                    ws_connected = public_connected or private_connected
                    
                    if ws_connected:
                        self.ws_status_label.setText("已连接")
                        self.ws_status_label.setStyleSheet("color: green; font-weight: bold;")
                    else:
                        self.ws_status_label.setText("未连接")
                        self.ws_status_label.setStyleSheet("color: red; font-weight: bold;")
                except Exception as e:
                    self.log(f"获取WebSocket连接状态失败: {e}")
                    self.ws_status_label.setText("未知")
                    self.ws_status_label.setStyleSheet("color: orange; font-weight: bold;")
            
            # Get and update DNS stats with more detail
            dns_stats = network_status.get("dns_stats", {})
            success_rate = dns_stats.get('success_rate', 0)
            total_queries = dns_stats.get('total_queries', 0)
            avg_dns_time = dns_stats.get('avg_resolve_time', 0)
            
            # Update DNS status with detailed information
            if success_rate > 0.9:
                dns_status_text = f"正常 (成功率: {success_rate:.1%}, 查询: {total_queries}, 平均耗时: {avg_dns_time:.1f}ms)"
                self.dns_status_label.setStyleSheet("color: green; font-weight: bold;")
            elif success_rate > 0.5:
                dns_status_text = f"不稳定 (成功率: {success_rate:.1%}, 查询: {total_queries}, 平均耗时: {avg_dns_time:.1f}ms)"
                self.dns_status_label.setStyleSheet("color: orange; font-weight: bold;")
            else:
                dns_status_text = f"异常 (成功率: {success_rate:.1%}, 查询: {total_queries}, 平均耗时: {avg_dns_time:.1f}ms)"
                self.dns_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.dns_status_label.setText(dns_status_text)
            
            # Update SSL certificate status (mock for now, can be enhanced with actual SSL check)
            self.ssl_status_label.setText("有效")
            self.ssl_status_label.setStyleSheet("color: green; font-weight: bold;")
            
            # Update packet loss rate (mock for now, can be enhanced with actual ping test)
            packet_loss = 0.0  # Mock value
            self.packet_loss_label.setText(f"{packet_loss:.1f}%")
            if packet_loss < 1.0:
                self.packet_loss_label.setStyleSheet("color: green; font-weight: bold;")
            elif packet_loss < 5.0:
                self.packet_loss_label.setStyleSheet("color: orange; font-weight: bold;")
            else:
                self.packet_loss_label.setStyleSheet("color: red; font-weight: bold;")
            
            # Update connection stability based on response time and success rate
            if response_time < 200 and success_rate > 0.9:
                stability_text = "稳定"
                self.stability_label.setStyleSheet("color: green; font-weight: bold;")
            elif response_time < 500 and success_rate > 0.7:
                stability_text = "一般"
                self.stability_label.setStyleSheet("color: orange; font-weight: bold;")
            else:
                stability_text = "不稳定"
                self.stability_label.setStyleSheet("color: red; font-weight: bold;")
            self.stability_label.setText(stability_text)
            
            # Update connection stats table
            self.update_connection_stats()
            
        except Exception as e:
            self.log(f"更新网络状态出错: {e}")
            import traceback
            self.log(traceback.format_exc())
    
    def switch_env(self, is_test=True):
        """Switch between testnet and mainnet environments"""
        self.log(f"正在切换到{'测试网' if is_test else '主网'}...")
        
        try:
            # Update the is_test flag in configuration
            self.config['api']['is_test'] = is_test
            
            # Update API IP list based on environment
            if is_test:
                # Testnet recommended IPs
                valid_ips = ["172.64.144.82", "104.18.43.174"]
            else:
                # Mainnet recommended IPs
                valid_ips = ["172.64.144.82", "104.18.43.174"]
            
            # Update API IP list in UI
            if hasattr(self, 'api_ip_list'):
                self.api_ip_list.setPlainText('\n'.join(valid_ips))
            
            # Save configuration
            self.save_config()
            
            # Restart API client with new configuration
            self.restart_api_client()
            
            # Update network status
            self.refresh_network_status()
            
            self.log(f"已成功切换到{'测试网' if is_test else '主网'}")
        except Exception as e:
            self.log(f"切换环境失败: {e}")
    
    def update_connection_stats(self):
        """Update connection statistics table"""
        try:
            from okx_api_client import OKXAPIClient
            
            # Get API IPs from config
            config_path = "d:\Projects\okx_trading_bot\config\okx_config.json"
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            api_ips = config['api'].get('api_ips', [])
            if not api_ips and 'api_ip' in config['api']:
                api_ips = [config['api']['api_ip']]
            
            # Clear table
            self.connection_stats_table.setRowCount(0)
            
            # Test each IP and add to table
            for i, ip in enumerate(api_ips):
                # Test connection
                start_time = time.time()
                connection_ok = self.test_ip_connection(ip, 443)
                response_time = int((time.time() - start_time) * 1000)
                
                # Add row to table
                self.connection_stats_table.insertRow(i)
                
                # IP address
                self.connection_stats_table.setItem(i, 0, QTableWidgetItem(ip))
                
                # Port
                self.connection_stats_table.setItem(i, 1, QTableWidgetItem("443"))
                
                # Response time
                self.connection_stats_table.setItem(i, 2, QTableWidgetItem(str(response_time)))
                
                # Status
                if connection_ok:
                    status_item = QTableWidgetItem("可用")
                    status_item.setForeground(QColor(0, 128, 0))
                else:
                    status_item = QTableWidgetItem("不可用")
                    status_item.setForeground(QColor(255, 0, 0))
                self.connection_stats_table.setItem(i, 3, status_item)
                
                # Update current IP if first available IP
                if i == 0 and connection_ok:
                    self.current_ip_label.setText(ip)
            
        except Exception as e:
            self.log(f"更新连接统计出错: {e}")
    
    def test_ip_connection(self, ip, port=443, timeout=2):
        """Test if IP:port is reachable"""
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect((ip, port))
            s.close()
            return True
        except:
            return False
    
    def init_network_monitoring(self):
        """Initialize network status monitoring"""
        # Set up timer to update network status every 5 seconds
        self.network_timer = QTimer()
        self.network_timer.timeout.connect(self.update_network_status)
        self.network_timer.start(5000)  # Update every 5 seconds
        
        # Initial update
        self.update_network_status()
    
    def init_websocket_client(self):
        """Initialize WebSocket client for real-time data"""
        try:
            from okx_websocket_client import OKXWebsocketClient
            self.ws_client = OKXWebsocketClient(
                api_key=self.config['api']['api_key'],
                api_secret=self.config['api']['api_secret'],
                passphrase=self.config['api']['passphrase'],
                is_test=self.config['api']['is_test'],
                api_ip=self.config['api'].get('api_ip'),
                api_ips=self.config['api'].get('api_ips', []),
                proxy=self.config['api'].get('proxy', {})
            )
            
            # Start WebSocket client
            self.ws_client.start()
            
            # Define message handlers
            def handle_ticker_message(msg):
                """Handle ticker update messages"""
                if msg['data'] and len(msg['data']) > 0:
                    ticker_data = msg['data'][0]
                    ticker_dict = {
                        'last': ticker_data.get('last', '0.0'),
                        'change': ticker_data.get('change', '0.0'),
                        'change_pct': ticker_data.get('changePct', '0.0')
                    }
                    self.update_ticker.emit(ticker_dict)
            
            # Add message handlers
            self.ws_client.add_message_handler("tickers", handle_ticker_message)
            
            self.log("WebSocket客户端已初始化")
        except Exception as e:
            self.log(f"初始化WebSocket客户端失败: {e}")
            import traceback
            traceback.print_exc()
    
    def closeEvent(self, event):
        """处理GUI关闭事件，确保线程安全"""
        # 设置关闭标志位
        self.is_closed = True
        
        # 停止数据更新定时器
        self.timer.stop()
        
        # 停止健康检查定时器
        if hasattr(self, 'health_check_timer'):
            self.health_check_timer.stop()
        
        # 停止WebSocket客户端
        if hasattr(self, 'ws_client'):
            self.ws_client.stop()
            self.log("WebSocket客户端已停止")
        
        # 停止配置文件监控
        if hasattr(self, 'config_observer') and self.config_observer.is_alive():
            self.config_observer.stop()
            self.config_observer.join()
            self.log("配置文件监控已停止")
        
        # 停止智能体状态更新定时器
        if hasattr(self, 'agent_status_timer'):
            self.agent_status_timer.stop()
            self.log("智能体状态更新定时器已停止")
        
        # 调用父类的关闭事件处理
        super().closeEvent(event)
    
    def load_strategy_list(self):
        """
        加载策略列表
        """
        try:
            # 获取策略执行智能体
            strategy_agent = self.trading_bot.get_agent("strategy_execution_agent")
            if not strategy_agent:
                self.log("未找到策略执行智能体")
                return
            
            # 获取策略列表
            strategies = strategy_agent.list_strategies()
            
            # 清空表格
            self.strategy_table.setRowCount(0)
            
            # 添加策略到表格
            for i, strategy in enumerate(strategies):
                self.strategy_table.insertRow(i)
                self.strategy_table.setItem(i, 0, QTableWidgetItem(strategy.get("name", "")))
                self.strategy_table.setItem(i, 1, QTableWidgetItem(strategy.get("status", "")))
                self.strategy_table.setItem(i, 2, QTableWidgetItem(strategy.get("class", "")))
                self.strategy_table.setItem(i, 3, QTableWidgetItem(str(strategy.get("performance", {}).get("total_trades", 0))))
                self.strategy_table.setItem(i, 4, QTableWidgetItem(str(strategy.get("performance", {}).get("total_profit", 0))))
            
            # 更新策略选择器
            self.strategy_combo.clear()
            for strategy in strategies:
                self.strategy_combo.addItem(strategy.get("name", ""))
            
            self.log(f"策略列表加载完成，共 {len(strategies)} 个策略")
        except Exception as e:
            self.log(f"加载策略列表失败: {e}")
            import traceback
            self.log(traceback.format_exc())
    
    def activate_strategy(self):
        """
        激活策略
        """
        try:
            # 获取选中的策略
            strategy_name = self.strategy_combo.currentText()
            if not strategy_name:
                self.log("未选中策略")
                return
            
            # 获取策略执行智能体
            strategy_agent = self.trading_bot.get_agent("strategy_execution_agent")
            if not strategy_agent:
                self.log("未找到策略执行智能体")
                return
            
            # 激活策略
            strategy_agent.activate_strategy(strategy_name)
            self.log(f"正在激活策略: {strategy_name}")
        except Exception as e:
            self.log(f"激活策略失败: {e}")
            import traceback
            self.log(traceback.format_exc())
    
    def deactivate_strategy(self):
        """
        停用策略
        """
        try:
            # 获取选中的策略
            strategy_name = self.strategy_combo.currentText()
            if not strategy_name:
                self.log("未选中策略")
                return
            
            # 获取策略执行智能体
            strategy_agent = self.trading_bot.get_agent("strategy_execution_agent")
            if not strategy_agent:
                self.log("未找到策略执行智能体")
                return
            
            # 停用策略
            strategy_agent.deactivate_strategy(strategy_name)
            self.log(f"正在停用策略: {strategy_name}")
        except Exception as e:
            self.log(f"停用策略失败: {e}")
            import traceback
            self.log(traceback.format_exc())
    
    def reload_strategy(self):
        """
        重新加载策略
        """
        try:
            # 获取选中的策略
            strategy_name = self.strategy_combo.currentText()
            if not strategy_name:
                self.log("未选中策略")
                return
            
            # 获取策略执行智能体
            strategy_agent = self.trading_bot.get_agent("strategy_execution_agent")
            if not strategy_agent:
                self.log("未找到策略执行智能体")
                return
            
            # 重新加载策略
            strategy_agent.reload_strategy(strategy_name)
            self.log(f"正在重新加载策略: {strategy_name}")
        except Exception as e:
            self.log(f"重新加载策略失败: {e}")
            import traceback
            self.log(traceback.format_exc())
    
    def save_strategy_params(self):
        """
        保存策略参数
        """
        try:
            # 获取选中的策略
            strategy_name = self.strategy_combo.currentText()
            if not strategy_name:
                self.log("未选中策略")
                return
            
            # 获取策略执行智能体
            strategy_agent = self.trading_bot.get_agent("strategy_execution_agent")
            if not strategy_agent:
                self.log("未找到策略执行智能体")
                return
            
            # 获取参数
            params_text = self.strategy_params_edit.toPlainText()
            if not params_text:
                self.log("参数不能为空")
                return
            
            # 解析参数
            import json
            params = json.loads(params_text)
            
            # 更新策略参数
            strategy_agent.update_strategy_params(strategy_name, params)
            self.log(f"正在更新策略参数: {strategy_name}")
        except json.JSONDecodeError as e:
            self.log(f"参数格式错误: {e}")
        except Exception as e:
            self.log(f"保存策略参数失败: {e}")
            import traceback
            self.log(traceback.format_exc())
    
    def load_agent_status(self):
        """
        加载智能体状态
        """
        try:
            # 获取所有智能体
            from commons.agent_registry import global_agent_registry
            all_agents = global_agent_registry.get_all_agents()
            
            # 清空表格
            self.agent_status_table.setRowCount(0)
            
            # 添加智能体到表格
            for i, agent in enumerate(all_agents):
                status = agent.get_status()
                self.agent_status_table.insertRow(i)
                # 使用中文名称显示智能体
                self.agent_status_table.setItem(i, 0, QTableWidgetItem(status.get("agent_name", status.get("agent_id", ""))))
                # 使用中文类型显示智能体
                self.agent_status_table.setItem(i, 1, QTableWidgetItem(status.get("agent_type", "")))
                self.agent_status_table.setItem(i, 2, QTableWidgetItem(status.get("status", "")))
                self.agent_status_table.setItem(i, 3, QTableWidgetItem(""))  # 运行时间
            
            self.log(f"智能体状态加载完成，共 {len(all_agents)} 个智能体")
        except Exception as e:
            self.log(f"加载智能体状态失败: {e}")
            import traceback
            self.log(traceback.format_exc())
    
    # 事件处理方法
    def on_market_data_updated(self, data):
        """
        处理市场数据更新事件
        """
        try:
            symbol = data.get("symbol")
            market_data = data.get("data")
            if not market_data or not symbol:
                return
            
            # 更新GUI中的市场数据
            if hasattr(self, 'last_price_label'):
                self.last_price_label.setText(f"{market_data.get('price', 0):.2f}")
            
            # 更新其他市场数据显示
            self.log(f"收到 {symbol} 市场数据更新")
        except Exception as e:
            self.log(f"处理市场数据更新事件失败: {e}")
    
    def on_order_placed(self, data):
        """
        处理订单已下单事件
        """
        try:
            order = data.get("order")
            if not order:
                return
            
            self.log(f"订单已下单: {order.get('ordId')}")
            # 更新订单列表
            if hasattr(self, 'update_orders_table'):
                self.update_orders_table()
        except Exception as e:
            self.log(f"处理订单已下单事件失败: {e}")
    
    def on_order_updated(self, data):
        """
        处理订单更新事件
        """
        try:
            order = data.get("order")
            if not order:
                return
            
            self.log(f"订单已更新: {order.get('ordId')}, 状态: {order.get('state')}")
            # 更新订单列表
            if hasattr(self, 'update_orders_table'):
                self.update_orders_table()
        except Exception as e:
            self.log(f"处理订单更新事件失败: {e}")
    
    def on_order_canceled(self, data):
        """
        处理订单取消事件
        """
        try:
            order_id = data.get("order_id")
            if not order_id:
                return
            
            self.log(f"订单已取消: {order_id}")
            # 更新订单列表
            if hasattr(self, 'update_orders_table'):
                self.update_orders_table()
        except Exception as e:
            self.log(f"处理订单取消事件失败: {e}")
    
    def on_risk_alert(self, data):
        """
        处理风险告警事件
        """
        try:
            alert_type = data.get("type")
            self.log(f"风险告警: {alert_type}, 详情: {data}")
            
            # 更新风险状态显示
            if hasattr(self, 'risk_status_labels'):
                self.risk_status_labels["current_drawdown"].setText(f"{data.get('current_value', 0):.2f}%")
        except Exception as e:
            self.log(f"处理风险告警事件失败: {e}")
    
    def on_risk_state_updated(self, data):
        """
        处理风险状态更新事件
        """
        try:
            state = data.get("state")
            if not state:
                return
            
            # 更新风险状态显示
            if hasattr(self, 'risk_status_labels'):
                self.risk_status_labels["total_position_value"].setText(f"{state.get('total_position_value', 0):.2f}")
                self.risk_status_labels["total_orders"].setText(str(state.get('total_orders', 0)))
                active_symbols = list(state.get('active_symbols', set()))
                self.risk_status_labels["current_drawdown"].setText(str(len(active_symbols)))
        except Exception as e:
            self.log(f"处理风险状态更新事件失败: {e}")
    
    def on_strategy_registered(self, data):
        """
        处理策略注册事件
        """
        try:
            strategy_name = data.get("strategy_name")
            self.log(f"策略已注册: {strategy_name}")
            # 更新策略列表
            if hasattr(self, 'load_strategy_list'):
                self.load_strategy_list()
        except Exception as e:
            self.log(f"处理策略注册事件失败: {e}")
    
    def on_strategy_activated(self, data):
        """
        处理策略激活事件
        """
        try:
            strategy_name = data.get("strategy_name")
            self.log(f"策略已激活: {strategy_name}")
            # 更新策略列表
            if hasattr(self, 'load_strategy_list'):
                self.load_strategy_list()
        except Exception as e:
            self.log(f"处理策略激活事件失败: {e}")
    
    def on_strategy_deactivated(self, data):
        """
        处理策略停用事件
        """
        try:
            strategy_name = data.get("strategy_name")
            self.log(f"策略已停用: {strategy_name}")
            # 更新策略列表
            if hasattr(self, 'load_strategy_list'):
                self.load_strategy_list()
        except Exception as e:
            self.log(f"处理策略停用事件失败: {e}")
    
    def on_system_state_updated(self, data):
        """
        处理系统状态更新事件
        """
        try:
            state = data.get("state")
            if not state:
                return
            
            # 更新系统状态显示
            if hasattr(self, 'system_status_labels'):
                self.system_status_labels["total_agents"].setText(str(state.get('total_agents', 0)))
                self.system_status_labels["running_agents"].setText(str(state.get('running_agents', 0)))
                self.system_status_labels["active_strategies"].setText(str(state.get('active_strategies', 0)))
                active_symbols = list(state.get('active_symbols', set()))
                self.system_status_labels["active_symbols"].setText(str(len(active_symbols)))
        except Exception as e:
            self.log(f"处理系统状态更新事件失败: {e}")
        
    def _load_config_internal(self):
        """Internal method to load configuration on the main thread"""
        import os
        import time
        
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'okx_config.json')
        config = None
        
        # 添加超时机制，防止文件IO操作长时间阻塞
        start_time = time.time()
        timeout = 5.0  # 5秒超时
        
        try:
            with open(config_path, 'r') as f:
                # 读取文件内容，带超时检查
                while time.time() - start_time < timeout:
                    content = f.read()
                    if content:
                        break
                    time.sleep(0.1)
                
                if not content:
                    raise TimeoutError("读取配置文件超时")
                
                self.log(f"从配置文件加载配置: {config_path}")
                config = json.loads(content)
                
                # 验证配置格式
                if not self.validate_config(config):
                    raise ValueError("配置文件格式验证失败")
                    
                return config
        except FileNotFoundError as e:
            self.log(f"配置文件不存在: {config_path}")
            # 返回默认配置，确保程序可以继续运行
            return self.get_default_config()
        except json.JSONDecodeError as e:
            self.log(f"配置文件格式错误: {e}")
            # 返回默认配置，确保程序可以继续运行
            return self.get_default_config()
        except TimeoutError as e:
            self.log(f"读取配置文件超时: {e}")
            # 返回默认配置，确保程序可以继续运行
            return self.get_default_config()
        except Exception as e:
            self.log(f"加载配置文件失败: {e}")
            # 返回默认配置，确保程序可以继续运行
            return self.get_default_config()
    
    def load_config(self):
        """Load configuration from file with timeout and validation"""
        import os
        import time
        from PyQt5.QtCore import QThread, QTimer
        
        # 确保在主线程中执行文件操作，避免阻塞GUI
        from PyQt5.QtWidgets import QApplication
        main_thread = QApplication.instance().thread()
        
        if QThread.currentThread() == main_thread:
            # 已经在主线程中，直接执行内部方法
            return self._load_config_internal()
        else:
            # 不在主线程中，使用QTimer.singleShot确保主线程执行
            self.log("在非主线程中调用load_config方法，将切换到主线程执行")
            
            # 创建结果容器
            result = [None]
            
            # 定义在主线程中执行的函数
            def load_on_main():
                result[0] = self._load_config_internal()
            
            # 在主线程中执行
            QTimer.singleShot(0, load_on_main)
            
            # 等待结果（最多等待5秒）
            start_wait = time.time()
            while result[0] is None and time.time() - start_wait < 5.0:
                time.sleep(0.1)
            
            return result[0] if result[0] is not None else self.get_default_config()
    
    def validate_config(self, config):
        """Validate configuration format"""
        try:
            # 基本配置验证
            if not isinstance(config, dict):
                self.log("配置文件不是有效的JSON对象")
                return False
            
            # 验证api配置
            if 'api' not in config or not isinstance(config['api'], dict):
                self.log("配置文件缺少api配置")
                return False
            
            # 验证代理配置
            if 'proxy' in config['api'] and not isinstance(config['api']['proxy'], dict):
                self.log("配置文件中proxy配置格式错误")
                return False
            
            # 验证api必需字段
            required_api_fields = ['api_key', 'api_secret', 'passphrase', 'is_test', 'api_url', 'timeout']
            for field in required_api_fields:
                if field not in config['api']:
                    self.log(f"配置文件缺少必需字段: api.{field}")
                    # 不是致命错误，继续验证
                    continue
            
            return True
        except Exception as e:
            self.log(f"配置验证失败: {e}")
            return False
    
    def get_default_config(self):
        """Return default configuration if loading fails"""
        self.log("使用默认配置")
        return {
            "api": {
                "api_key": "",
                "api_secret": "",
                "passphrase": "",
                "is_test": True,
                "api_url": "https://www.okx.com",
                "timeout": 30,
                "proxy": {
                    "enabled": False,
                    "http": "",
                    "https": "",
                    "socks5": ""
                },
                "is_logged_in": False
            },
            "market_data": {
                "update_interval": 10
            }
        }
    
    def _load_config_file_internal(self):
        """Internal method to reload configuration file on the main thread"""
        try:
            # Load new configuration
            new_config = self.load_config()
            
            # Check if configuration has actually changed
            import json
            if json.dumps(new_config, sort_keys=True) == json.dumps(self.config, sort_keys=True):
                # Configuration hasn't changed, skip update
                self.log("配置文件内容未变化，跳过重新加载")
                return
            
            # Configuration has changed, update
            self.config = new_config
            
            # Update API client
            self.restart_api_client()
            
            # Update GUI elements if they exist
            if hasattr(self, 'api_key_edit'):
                self.api_key_edit.setText(self.config['api']['api_key'])
                self.api_secret_edit.setText(self.config['api']['api_secret'])
                self.passphrase_edit.setText(self.config['api']['passphrase'])
                self.api_url_edit.setText(self.config['api']['api_url'])
                
                # Update API IP list
                api_ips = self.config['api'].get('api_ips', [self.config['api'].get('api_ip', '')])
                self.api_ip_list.setPlainText('\n'.join(api_ips))
                
                self.timeout_spin.setValue(self.config['api']['timeout'])
                
                # Load login state if available
                if hasattr(self, 'login_status') and self.config['api'].get('is_logged_in', False):
                    self.login_status.setText("登录状态: 已登录")
                    self.login_status.setStyleSheet("font-weight: bold; color: green;")
                    if hasattr(self, 'api_login_btn'):
                        self.api_login_btn.setEnabled(False)
                    if hasattr(self, 'api_logout_btn'):
                        self.api_logout_btn.setEnabled(True)
            
            self.log("配置文件重新加载成功")
        except Exception as e:
            self.log(f"重新加载配置文件失败: {e}")
            self.show_alert("配置加载错误", f"重新加载配置文件失败: {e}")
    
    def load_config_file(self):
        """Reload configuration file and update GUI, ensuring main thread execution"""
        from PyQt5.QtCore import QThread, QTimer
        from PyQt5.QtWidgets import QApplication
        
        # Get the main thread
        main_thread = QApplication.instance().thread()
        
        if QThread.currentThread() == main_thread:
            # Already on main thread, execute directly
            self._load_config_file_internal()
        else:
            # Not on main thread, use QTimer.singleShot to ensure main thread execution
            self.log("在非主线程中调用load_config_file方法，将切换到主线程执行")
            
            # Use QTimer.singleShot to execute on main thread
            QTimer.singleShot(0, self._load_config_file_internal)
    
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
    
    def init_control_bar(self, layout):
        """Initialize the top control bar"""
        control_bar = QWidget()
        control_layout = QHBoxLayout(control_bar)
        
        # Symbol selection
        control_layout.addWidget(QLabel("交易对:"))
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "BNB-USDT-SWAP"])
        self.symbol_combo.currentTextChanged.connect(self.on_symbol_change)
        control_layout.addWidget(self.symbol_combo)
        
        # Update button
        self.update_btn = QPushButton("更新数据")
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
        
        # Help button
        self.help_btn = QPushButton("帮助")
        self.help_btn.clicked.connect(self.show_help)
        control_layout.addWidget(self.help_btn)
        
        control_layout.addStretch()
        layout.addWidget(control_bar)
    
    def show_help(self):
        """Show help dialog"""
        help_dialog = HelpDialog(self)
        help_dialog.exec_()
    
    def init_trading_tab(self):
        """Initialize the trading tab"""
        trading_tab = QWidget()
        trading_layout = QVBoxLayout(trading_tab)
        
        # Top: Market data splitter
        market_splitter = QSplitter(Qt.Horizontal)
        
        # Left: Ticker and Order Book
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Ticker display
        self.init_ticker_widget(left_layout)
        
        # Order Book
        self.init_order_book_widget(left_layout)
        
        market_splitter.addWidget(left_widget)
        
        # Right: Trading controls and order table
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Trading controls
        self.init_trading_controls(right_layout)
        
        # Current orders table
        self.init_orders_table(right_layout)
        
        market_splitter.addWidget(right_widget)
        market_splitter.setSizes([500, 700])
        
        trading_layout.addWidget(market_splitter)
        self.tab_widget.addTab(trading_tab, "交易")
    
    def init_ticker_widget(self, layout):
        """Initialize ticker display"""
        ticker_group = QGroupBox("市场数据")
        ticker_layout = QGridLayout(ticker_group)
        
        # Ticker labels
        self.ticker_price = QLabel("0.00")
        self.ticker_price.setFont(QFont("Arial", 24, QFont.Bold))
        self.ticker_price.setAlignment(Qt.AlignCenter)
        
        self.ticker_change = QLabel("0.00")
        self.ticker_change.setFont(QFont("Arial", 14))
        self.ticker_change.setAlignment(Qt.AlignCenter)
        
        self.ticker_change_pct = QLabel("0.00%")
        self.ticker_change_pct.setFont(QFont("Arial", 14))
        self.ticker_change_pct.setAlignment(Qt.AlignCenter)
        
        ticker_layout.addWidget(self.ticker_price, 0, 0, 1, 3)
        ticker_layout.addWidget(self.ticker_change, 1, 0)
        ticker_layout.addWidget(self.ticker_change_pct, 1, 1)
        
        layout.addWidget(ticker_group)
    
    def init_order_book_widget(self, layout):
        """Initialize order book display"""
        order_book_group = QGroupBox("订单簿")
        order_book_layout = QHBoxLayout(order_book_group)
        
        # Buy orders
        buy_widget = QWidget()
        buy_layout = QVBoxLayout(buy_widget)
        buy_layout.addWidget(QLabel("买单"))
        
        self.buy_table = QTableWidget(10, 2)
        self.buy_table.setHorizontalHeaderLabels(["价格", "数量"])
        self.buy_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.buy_table.setStyleSheet("QTableWidget { background-color: #f0fff0; }")
        buy_layout.addWidget(self.buy_table)
        
        # Sell orders
        sell_widget = QWidget()
        sell_layout = QVBoxLayout(sell_widget)
        sell_layout.addWidget(QLabel("卖单"))
        
        self.sell_table = QTableWidget(10, 2)
        self.sell_table.setHorizontalHeaderLabels(["价格", "数量"])
        self.sell_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sell_table.setStyleSheet("QTableWidget { background-color: #fff0f0; }")
        sell_layout.addWidget(self.sell_table)
        
        order_book_layout.addWidget(buy_widget)
        order_book_layout.addWidget(sell_widget)
        
        layout.addWidget(order_book_group)
    
    def init_trading_controls(self, layout):
        """Initialize trading controls"""
        trading_group = QGroupBox("交易控制")
        trading_layout = QVBoxLayout(trading_group)
        
        # Order form - Main parameters
        order_form = QFormLayout()
        
        # Order type
        self.order_type_combo = QComboBox()
        self.order_type_combo.addItems(["限价", "市价", "只做maker", "触发限价", "触发市价"])
        order_form.addRow("订单类型:", self.order_type_combo)
        
        # Side
        self.side_combo = QComboBox()
        self.side_combo.addItems(["买入", "卖出"])
        order_form.addRow("方向:", self.side_combo)
        
        # Price
        self.price_edit = QLineEdit("0.0")
        order_form.addRow("价格:", self.price_edit)
        
        # Amount
        self.amount_edit = QLineEdit("0.0")
        order_form.addRow("数量:", self.amount_edit)
        
        # Leverage
        self.leverage_spin = QSpinBox()
        self.leverage_spin.setRange(1, 100)
        self.leverage_spin.setValue(5)
        order_form.addRow("杠杆:", self.leverage_spin)
        
        # Trading mode (td_mode)
        self.td_mode_combo = QComboBox()
        self.td_mode_combo.addItems(["逐仓", "全仓"])
        self.td_mode_combo.setCurrentText("逐仓")
        order_form.addRow("交易模式:", self.td_mode_combo)
        
        # Position side
        self.pos_side_combo = QComboBox()
        self.pos_side_combo.addItems(["净持仓", "多头", "空头"])
        self.pos_side_combo.setCurrentText("净持仓")
        order_form.addRow("持仓方向:", self.pos_side_combo)
        
        # Reduce only
        self.reduce_only_check = QCheckBox()
        self.reduce_only_check.setChecked(False)
        order_form.addRow("只减仓:", self.reduce_only_check)
        
        # Client order ID
        self.cl_ord_id_edit = QLineEdit("")
        self.cl_ord_id_edit.setPlaceholderText("可选，客户订单ID")
        order_form.addRow("客户订单ID:", self.cl_ord_id_edit)
        
        trading_layout.addLayout(order_form)
        
        # Take Profit / Stop Loss settings
        self.init_tp_sl_settings(trading_layout)
        
        # Batch operations
        self.init_batch_operations(trading_layout)
        
        # Place order button
        self.place_order_btn = QPushButton("下单")
        self.place_order_btn.clicked.connect(self.place_order)
        self.place_order_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        trading_layout.addWidget(self.place_order_btn)
        
        layout.addWidget(trading_group)
    
    def init_tp_sl_settings(self, layout):
        """Initialize Take Profit / Stop Loss settings"""
        tp_sl_group = QGroupBox("止盈止损设置")
        tp_sl_layout = QGridLayout(tp_sl_group)
        
        # Take Profit settings
        tp_label = QLabel("止盈设置")
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
        
        # Stop Loss settings
        sl_label = QLabel("止损设置")
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
        
        # Batch place orders button
        self.batch_place_btn = QPushButton("批量下单")
        self.batch_place_btn.clicked.connect(self.batch_place_orders)
        self.batch_place_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        batch_layout.addWidget(self.batch_place_btn)
        
        # Batch cancel orders button
        self.batch_cancel_btn = QPushButton("批量撤单")
        self.batch_cancel_btn.clicked.connect(self.batch_cancel_orders)
        self.batch_cancel_btn.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold;")
        batch_layout.addWidget(self.batch_cancel_btn)
        
        # Batch amend orders button
        self.batch_amend_btn = QPushButton("批量修改")
        self.batch_amend_btn.clicked.connect(self.batch_amend_orders)
        self.batch_amend_btn.setStyleSheet("background-color: #9C27B0; color: white; font-weight: bold;")
        batch_layout.addWidget(self.batch_amend_btn)
        
        layout.addWidget(batch_group)
    
    def init_orders_table(self, layout):
        """Initialize current orders table"""
        orders_group = QGroupBox("当前订单")
        orders_layout = QVBoxLayout(orders_group)
        
        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(10)
        self.orders_table.setHorizontalHeaderLabels(["订单ID", "交易对", "方向", "类型", "价格", "数量", "状态", "持仓方向", "交易模式", "客户订单ID"])
        self.orders_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Order operations buttons
        order_ops_layout = QHBoxLayout()
        
        # Cancel selected order button
        self.cancel_order_btn = QPushButton("取消选中订单")
        self.cancel_order_btn.clicked.connect(self.cancel_selected_order)
        order_ops_layout.addWidget(self.cancel_order_btn)
        
        # Amend selected order button
        self.amend_order_btn = QPushButton("修改选中订单")
        self.amend_order_btn.clicked.connect(self.amend_selected_order)
        order_ops_layout.addWidget(self.amend_order_btn)
        
        # Select all orders button
        self.select_all_orders_btn = QPushButton("全选订单")
        self.select_all_orders_btn.clicked.connect(self.select_all_orders)
        order_ops_layout.addWidget(self.select_all_orders_btn)
        
        # Clear selection button
        self.clear_selection_btn = QPushButton("清空选择")
        self.clear_selection_btn.clicked.connect(self.clear_order_selection)
        order_ops_layout.addWidget(self.clear_selection_btn)
        
        orders_layout.addWidget(self.orders_table)
        orders_layout.addLayout(order_ops_layout)
        
        layout.addWidget(orders_group)
    
    def init_strategy_tab(self):
        """Initialize strategy configuration tab"""
        strategy_tab = QWidget()
        strategy_layout = QVBoxLayout(strategy_tab)
        
        # Strategy controls
        strategy_group = QGroupBox("策略配置")
        strategy_form = QFormLayout(strategy_group)
        
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
        self.start_strategy_btn.clicked.connect(self.start_strategy)
        self.start_strategy_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        
        self.stop_strategy_btn = QPushButton("停止策略")
        self.stop_strategy_btn.clicked.connect(self.stop_strategy)
        self.stop_strategy_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        
        self.strategy_status = QLabel("状态: 已停止")
        self.strategy_status.setStyleSheet("font-weight: bold;")
        
        control_layout.addWidget(self.start_strategy_btn)
        control_layout.addWidget(self.stop_strategy_btn)
        control_layout.addStretch()
        control_layout.addWidget(self.strategy_status)
        
        strategy_layout.addLayout(control_layout)
        
        # Strategy log
        self.strategy_log = QTextEdit()
        self.strategy_log.setReadOnly(True)
        self.strategy_log.setStyleSheet("background-color: #f5f5f5;")
        strategy_layout.addWidget(self.strategy_log)
        
        self.tab_widget.addTab(strategy_tab, "策略")
    
    def init_account_tab(self):
        """Initialize account information tab"""
        account_tab = QWidget()
        account_layout = QVBoxLayout(account_tab)
        
        # Account info
        account_group = QGroupBox("账户信息")
        account_layout.addWidget(account_group)
        
        # Balance and positions
        balance_layout = QHBoxLayout(account_group)
        
        # Balance info
        balance_widget = QWidget()
        balance_form = QFormLayout(balance_widget)
        
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
        positions_label = QLabel("持仓信息将在连接后显示")
        positions_label.setAlignment(Qt.AlignCenter)
        positions_layout.addWidget(positions_label)
        balance_layout.addWidget(positions_widget)
    
    def init_network_status_tab(self):
        """Initialize network status display tab"""
        network_tab = QWidget()
        network_layout = QVBoxLayout(network_tab)
        
        # Network info group - current connection
        current_group = QGroupBox("当前连接信息")
        current_layout = QFormLayout(current_group)
        
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
        
        # Connection stats table
        self.connection_stats_table = QTableWidget()
        self.connection_stats_table.setColumnCount(4)
        self.connection_stats_table.setHorizontalHeaderLabels(["IP地址", "端口", "响应时间(ms)", "状态"])
        self.connection_stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        api_layout.addWidget(self.connection_stats_table)
        
        network_layout.addWidget(api_group)
        
        # Network adaptation controls
        controls_group = QGroupBox("网络适配控制")
        controls_layout = QHBoxLayout(controls_group)
        
        # Environment switch buttons
        env_layout = QVBoxLayout()
        env_label = QLabel("环境切换")
        env_label.setAlignment(Qt.AlignCenter)
        env_layout.addWidget(env_label)
        
        env_btn_layout = QHBoxLayout()
        self.testnet_btn = QPushButton("测试网")
        self.testnet_btn.clicked.connect(lambda: self.switch_env(is_test=True))
        self.testnet_btn.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold;")
        env_btn_layout.addWidget(self.testnet_btn)
        
        self.mainnet_btn = QPushButton("主网")
        self.mainnet_btn.clicked.connect(lambda: self.switch_env(is_test=False))
        self.mainnet_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        env_btn_layout.addWidget(self.mainnet_btn)
        
        env_layout.addLayout(env_btn_layout)
        controls_layout.addLayout(env_layout)
        
        # Manual adaptation button
        self.manual_adapt_btn = QPushButton("手动适配网络")
        self.manual_adapt_btn.clicked.connect(self.manual_network_adaptation)
        self.manual_adapt_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        controls_layout.addWidget(self.manual_adapt_btn)
        
        # Refresh status button
        self.refresh_status_btn = QPushButton("刷新状态")
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
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #f5f5f5; font-family: Consolas, monospace;")
        
        log_layout.addWidget(self.log_text)
        self.tab_widget.addTab(log_tab, "日志")
    
    def init_config_tab(self):
        """Initialize configuration management tab focused on API login"""
        config_tab = QWidget()
        config_layout = QVBoxLayout(config_tab)
        
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
        monitoring_layout = QFormLayout(monitoring_group)
        
        # Health Check Interval
        self.health_check_interval = QSpinBox()
        self.health_check_interval.setRange(60, 3600)
        self.health_check_interval.setValue(self.config.get('market_data', {}).get('update_interval', 10) * 6)
        monitoring_layout.addRow("健康检查间隔 (秒):", self.health_check_interval)
        
        # Enable Health Check
        self.enable_health_check = QCheckBox("启用自动健康检查")
        self.enable_health_check.setChecked(True)
        monitoring_layout.addRow(self.enable_health_check)
        
        # Load Balancing Configuration Group
        lb_group = QGroupBox("负载均衡配置")
        lb_layout = QFormLayout(lb_group)
        
        # Load Balancing Strategy
        self.lb_strategy_combo = QComboBox()
        self.lb_strategy_combo.addItems(["轮询", "响应时间优先"])
        lb_layout.addRow("负载均衡策略:", self.lb_strategy_combo)
        
        # Current Active IP
        self.current_active_ip = QLabel("当前活跃IP: " + (self.config['api'].get('api_ip', '未设置')))
        self.current_active_ip.setStyleSheet("font-weight: bold;")
        lb_layout.addRow(self.current_active_ip)
        
        # DNS Configuration Group
        dns_group = QGroupBox("DNS配置")
        dns_layout = QFormLayout(dns_group)
        
        # DNS Region Selection
        self.dns_region_combo = QComboBox()
        self.dns_region_combo.addItems(["global", "asia", "europe", "north_america"])
        # Set default to 'global' initially, will be updated when API client is ready
        self.dns_region_combo.setCurrentText("global")
        dns_layout.addRow("DNS区域:", self.dns_region_combo)
        
        # Current DNS Servers Display
        self.current_dns_servers = QLabel("初始化中...")
        self.current_dns_servers.setStyleSheet("font-weight: bold;")
        dns_layout.addRow("当前DNS服务器:", self.current_dns_servers)
        
        # DNS Stats Button
        self.view_dns_stats_btn = QPushButton("查看DNS统计信息")
        self.view_dns_stats_btn.clicked.connect(self.show_dns_stats)
        dns_layout.addRow(self.view_dns_stats_btn)
        
        # Update DNS Configuration Button
        self.update_dns_config_btn = QPushButton("更新DNS配置")
        self.update_dns_config_btn.clicked.connect(self.update_dns_configuration)
        self.update_dns_config_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        dns_layout.addRow(self.update_dns_config_btn)
        
        # Proxy Configuration Group
        proxy_group = QGroupBox("代理配置")
        proxy_layout = QFormLayout(proxy_group)
        
        # Proxy Enabled Checkbox
        self.proxy_enabled = QCheckBox("启用代理")
        self.proxy_enabled.setChecked(self.config['api'].get('proxy', {}).get('enabled', False))
        proxy_layout.addRow(self.proxy_enabled)
        
        # Proxy Type Selection
        proxy_type_layout = QHBoxLayout()
        proxy_layout.addRow("代理类型:", proxy_type_layout)
        
        self.proxy_type = QComboBox()
        self.proxy_type.addItems(["SOCKS5", "HTTP", "HTTPS"])
        # Determine current proxy type
        proxy_config = self.config['api'].get('proxy', {})
        if proxy_config.get('socks5'):
            self.proxy_type.setCurrentText("SOCKS5")
        elif proxy_config.get('https'):
            self.proxy_type.setCurrentText("HTTPS")
        elif proxy_config.get('http'):
            self.proxy_type.setCurrentText("HTTP")
        proxy_type_layout.addWidget(self.proxy_type)
        
        # Proxy Address Input
        self.proxy_address = QLineEdit()
        # Set appropriate proxy address based on selected type
        proxy_address = proxy_config.get('socks5') or proxy_config.get('https') or proxy_config.get('http') or ''
        self.proxy_address.setText(proxy_address)
        self.proxy_address.setPlaceholderText("例如: socks5://127.0.0.1:1080 或 http://127.0.0.1:8080")
        proxy_layout.addRow("代理地址:", self.proxy_address)
        
        # Proxy Test Button
        self.test_proxy_btn = QPushButton("测试代理连接")
        self.test_proxy_btn.clicked.connect(self.test_proxy_connection)
        self.test_proxy_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        proxy_layout.addRow(self.test_proxy_btn)
        
        # Advanced Settings Group
        advanced_group = QGroupBox("高级设置")
        advanced_layout = QFormLayout(advanced_group)
        
        # API IP List in advanced settings
        self.api_ip_list = QTextEdit()
        api_ips = self.config['api'].get('api_ips', [self.config['api'].get('api_ip', '')])
        self.api_ip_list.setPlainText('\n'.join(api_ips))
        advanced_layout.addRow("API IP地址列表 (每行一个):", self.api_ip_list)
        
        # Add all groups to main layout
        config_layout.addWidget(api_config_group)
        config_layout.addLayout(auth_layout)
        config_layout.addWidget(self.connection_status)
        config_layout.addWidget(monitoring_group)
        config_layout.addWidget(lb_group)
        config_layout.addWidget(dns_group)
        config_layout.addWidget(proxy_group)
        
        # DPI Interception Detection Group
        dpi_group = QGroupBox("DPI拦截检测")
        dpi_layout = QFormLayout(dpi_group)
        
        # DPI Detection Result
        self.dpi_detection_result = QLabel("未检测")
        self.dpi_detection_result.setStyleSheet("font-weight: bold; color: orange;")
        dpi_layout.addRow("检测结果:", self.dpi_detection_result)
        
        # DPI Detection Button
        self.detect_dpi_btn = QPushButton("检测DPI拦截")
        self.detect_dpi_btn.clicked.connect(self.detect_dpi_interception)
        self.detect_dpi_btn.setStyleSheet("background-color: #9C27B0; color: white; font-weight: bold;")
        dpi_layout.addRow(self.detect_dpi_btn)
        
        # DPI Detection Details
        self.dpi_detection_details = QTextEdit()
        self.dpi_detection_details.setReadOnly(True)
        self.dpi_detection_details.setMinimumHeight(100)
        self.dpi_detection_details.setPlaceholderText("检测结果详情将显示在这里...")
        dpi_layout.addRow("检测详情:", self.dpi_detection_details)
        
        config_layout.addWidget(dpi_group)
        config_layout.addWidget(advanced_group)
        
        self.tab_widget.addTab(config_tab, "配置管理")
        
        # 在后台线程中初始化DNS配置显示，避免阻塞GUI
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, self.update_dns_config_display)
    
    def connect_signals(self):
        """Connect signals for GUI updates"""
        self.update_ticker.connect(self.update_ticker_display)
        self.update_order_book.connect(self.update_order_book_display)
        self.update_orders.connect(self.update_orders_display)
        self.update_positions.connect(self.update_positions_display)
        self.update_log.connect(self.append_log)
    
    def on_symbol_change(self, symbol):
        """Handle symbol change"""
        self.log(f"切换交易对为 {symbol}")
        self.update_all_data()
    
    def update_all_data(self):
        """Update all market data"""
        threading.Thread(target=self.fetch_market_data).start()
        threading.Thread(target=self.fetch_account_data).start()
        threading.Thread(target=self.fetch_orders).start()
        threading.Thread(target=self.fetch_positions).start()
    
    def fetch_market_data(self):
        """Fetch market data in a background thread"""
        symbol = self.symbol_combo.currentText()
        
        try:
            # Check if market_data_service is initialized
            if hasattr(self, 'market_data_service') and self.market_data_service:
                # Fetch ticker
                ticker = self.market_data_service.get_real_time_ticker(symbol)
                
                # 检查GUI是否已关闭
                if not self.is_closed:
                    if ticker:
                        self.update_ticker.emit(ticker)
                    else:
                        # Emit an empty dict if ticker is None
                        self.update_ticker.emit({})
                    
                    # Fetch order book
                    order_book = self.market_data_service.get_order_book(symbol, 10)
                    if order_book:
                        self.update_order_book.emit(order_book)
                    else:
                        # Emit an empty dict if order_book is None
                        self.update_order_book.emit({})
                    
                    # Update status to ready if data is fetched successfully
                    self.status_label.setText("状态: 就绪")
                    self.status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                # Service not initialized yet, skip this update
                if not self.is_closed:
                    self.log("市场数据服务未初始化，跳过数据更新")
            
        except Exception as e:
            error_msg = f"获取市场数据失败: {e}"
            
            # 只在GUI未关闭时记录日志和更新状态
            if not self.is_closed:
                self.log(error_msg)
                
                # Update status bar with error
                if "getaddrinfo failed" in str(e):
                    self.status_label.setText("状态: DNS解析失败，请检查网络连接")
                    self.status_label.setStyleSheet("color: red; font-weight: bold;")
                else:
                    self.status_label.setText(f"状态: 数据获取失败")
                    self.status_label.setStyleSheet("color: red; font-weight: bold;")
                
                # Emit empty dicts to prevent GUI errors
                self.update_ticker.emit({})
                self.update_order_book.emit({})
    
    def fetch_account_data(self):
        """Fetch account data in a background thread"""
        try:
            # Check if api_client is initialized
            if hasattr(self, 'api_client') and self.api_client:
                # Fetch account balance
                balance_info = self.api_client.get_account_balance()
                
                # 只在GUI未关闭时更新UI
                if not self.is_closed and balance_info:
                    # Extract balance information
                    total_eq = balance_info[0].get('totalEq', '0')
                    available_balance = balance_info[0].get('details', [{}])[0].get('availBal', '0')
                    self.available_balance.setText(available_balance)
                    self.total_balance.setText(total_eq)
                    # Unrealized PnL is not available in get_account_balance, leave it as-is
            else:
                # API client not initialized yet, skip this update
                if not self.is_closed:
                    self.log("API客户端未初始化，跳过账户数据更新")
            
        except Exception as e:
            # 只在GUI未关闭时记录日志
            if not self.is_closed:
                self.log(f"获取账户数据失败: {e}")
    
    def fetch_orders(self):
        """Fetch orders in a background thread"""
        try:
            # Check if order_manager is initialized
            if hasattr(self, 'order_manager') and self.order_manager:
                symbol = self.symbol_combo.currentText()
                orders = self.order_manager.get_pending_orders(symbol)
                
                # 只在GUI未关闭时发送信号
                if not self.is_closed:
                    # 确保传递的是列表类型，即使API返回None
                    self.update_orders.emit(orders if orders is not None else [])
            else:
                # Order manager not initialized yet, skip this update
                if not self.is_closed:
                    self.log("订单管理器未初始化，跳过订单数据更新")
            
        except Exception as e:
            # 只在GUI未关闭时记录日志
            if not self.is_closed:
                self.log(f"获取订单数据失败: {e}")
    
    def fetch_positions(self):
        """Fetch positions in a background thread"""
        try:
            # Check if api_client is initialized
            if hasattr(self, 'api_client') and self.api_client:
                positions = self.api_client.get_positions()
                
                # 只在GUI未关闭时发送信号
                if not self.is_closed:
                    # 确保传递的是列表类型，即使API返回None
                    self.update_positions.emit(positions if positions is not None else [])
            else:
                # API client not initialized yet, skip this update
                if not self.is_closed:
                    self.log("API客户端未初始化，跳过持仓数据更新")
            
        except Exception as e:
            # 只在GUI未关闭时记录日志
            if not self.is_closed:
                self.log(f"获取持仓数据失败: {e}")
    
    def update_ticker_display(self, ticker):
        """Update ticker display"""
        if ticker:
            self.ticker_price.setText(str(ticker.get('last', '0.00')))
            
            change = float(ticker.get('change', '0.0'))
            change_pct = float(ticker.get('change_pct', '0.0'))
            
            self.ticker_change.setText(f"{change:.2f}")
            self.ticker_change_pct.setText(f"{change_pct:.2f}%")
            
            # Set color based on change
            if change > 0:
                self.ticker_change.setStyleSheet("color: green; font-weight: bold;")
                self.ticker_change_pct.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.ticker_change.setStyleSheet("color: red; font-weight: bold;")
                self.ticker_change_pct.setStyleSheet("color: red; font-weight: bold;")
    
    def update_order_book_display(self, order_book):
        """Update order book display"""
        if order_book:
            # Update buy orders
            self.buy_table.setRowCount(0)
            for i, order in enumerate(order_book.get('bids', [])):
                self.buy_table.insertRow(i)
                self.buy_table.setItem(i, 0, QTableWidgetItem(str(order[0])))
                self.buy_table.setItem(i, 1, QTableWidgetItem(str(order[1])))
            
            # Update sell orders
            self.sell_table.setRowCount(0)
            for i, order in enumerate(order_book.get('asks', [])):
                self.sell_table.insertRow(i)
                self.sell_table.setItem(i, 0, QTableWidgetItem(str(order[0])))
                self.sell_table.setItem(i, 1, QTableWidgetItem(str(order[1])))
    
    def update_orders_display(self, orders):
        """Update orders table"""
        self.orders_table.setRowCount(0)
        
        # Define mappings for order status, side, type, etc.
        side_mapping = {
            "buy": "买入",
            "sell": "卖出"
        }
        
        ord_type_mapping = {
            "limit": "限价",
            "market": "市价",
            "post_only": "只做maker",
            "conditional": "触发限价",
            "trigger_market": "触发市价"
        }
        
        state_mapping = {
            "live": "等待成交",
            "partially_filled": "部分成交",
            "filled": "完全成交",
            "cancelled": "已撤销",
            "failed": "失败",
            "rejected": "已拒绝"
        }
        
        pos_side_mapping = {
            "net": "净持仓",
            "long": "多头",
            "short": "空头"
        }
        
        td_mode_mapping = {
            "isolated": "逐仓",
            "cross": "全仓"
        }
        
        for i, order in enumerate(orders):
            self.orders_table.insertRow(i)
            self.orders_table.setItem(i, 0, QTableWidgetItem(order.get('ordId', '')))
            self.orders_table.setItem(i, 1, QTableWidgetItem(order.get('instId', '')))
            self.orders_table.setItem(i, 2, QTableWidgetItem(side_mapping.get(order.get('side', ''), order.get('side', ''))))
            self.orders_table.setItem(i, 3, QTableWidgetItem(ord_type_mapping.get(order.get('ordType', ''), order.get('ordType', ''))))
            self.orders_table.setItem(i, 4, QTableWidgetItem(str(order.get('px', '0.0'))))
            self.orders_table.setItem(i, 5, QTableWidgetItem(str(order.get('sz', '0.0'))))
            self.orders_table.setItem(i, 6, QTableWidgetItem(state_mapping.get(order.get('state', ''), order.get('state', ''))))
            self.orders_table.setItem(i, 7, QTableWidgetItem(pos_side_mapping.get(order.get('posSide', ''), order.get('posSide', ''))))
            self.orders_table.setItem(i, 8, QTableWidgetItem(td_mode_mapping.get(order.get('tdMode', ''), order.get('tdMode', ''))))
            self.orders_table.setItem(i, 9, QTableWidgetItem(order.get('clOrdId', '')))
    
    def update_positions_display(self, positions):
        """Update positions table"""
        self.positions_table.setRowCount(0)
        
        # Define mappings for position side
        pos_side_mapping = {
            "net": "净持仓",
            "long": "多头",
            "short": "空头"
        }
        
        for i, position in enumerate(positions):
            self.positions_table.insertRow(i)
            self.positions_table.setItem(i, 0, QTableWidgetItem(position.get('instId', '')))
            self.positions_table.setItem(i, 1, QTableWidgetItem(pos_side_mapping.get(position.get('posSide', ''), position.get('posSide', ''))))
            self.positions_table.setItem(i, 2, QTableWidgetItem(str(position.get('pos', '0.0'))))
            self.positions_table.setItem(i, 3, QTableWidgetItem(str(position.get('avgPx', '0.0'))))
            self.positions_table.setItem(i, 4, QTableWidgetItem(str(position.get('upl', '0.0'))))
    
    def place_order(self):
        """Place an order"""
        symbol = self.symbol_combo.currentText()
        order_type_text = self.order_type_combo.currentText()
        side_text = self.side_combo.currentText()
        
        try:
            price = float(self.price_edit.text()) if self.price_edit.text() else None
            amount = float(self.amount_edit.text())
            leverage = self.leverage_spin.value()
            td_mode = self.td_mode_combo.currentText()
            pos_side = self.pos_side_combo.currentText()
            reduce_only = self.reduce_only_check.isChecked()
            cl_ord_id = self.cl_ord_id_edit.text() or None
            
            # Translate Chinese to English for API
            order_type_mapping = {
                "限价": "limit",
                "市价": "market",
                "只做maker": "post_only",
                "触发限价": "conditional",
                "触发市价": "trigger_market"
            }
            
            side_mapping = {
                "买入": "buy",
                "卖出": "sell"
            }
            
            td_mode_mapping = {
                "逐仓": "isolated",
                "全仓": "cross"
            }
            
            pos_side_mapping = {
                "净持仓": "net",
                "多头": "long",
                "空头": "short"
            }
            
            order_type = order_type_mapping[order_type_text]
            side = side_mapping[side_text]
            td_mode = td_mode_mapping[self.td_mode_combo.currentText()]
            pos_side = pos_side_mapping[self.pos_side_combo.currentText()]
            
            # Validate inputs
            if amount <= 0:
                self.log("无效的数量")
                return
            
            if order_type in ["limit", "post_only", "conditional"] and price is not None and price <= 0:
                self.log("无效的价格")
                return
            
            # Set leverage first
            self.api_client.set_leverage(symbol, leverage, mgn_mode=td_mode, pos_side=pos_side)
            
            # Get TP/SL settings
            tp_px = float(self.tp_px_edit.text()) if self.tp_px_edit.text() and float(self.tp_px_edit.text()) > 0 else None
            tp_trigger_px = float(self.tp_trigger_px_edit.text()) if self.tp_trigger_px_edit.text() and float(self.tp_trigger_px_edit.text()) > 0 else None
            sl_px = float(self.sl_px_edit.text()) if self.sl_px_edit.text() and float(self.sl_px_edit.text()) > 0 else None
            sl_trigger_px = float(self.sl_trigger_px_edit.text()) if self.sl_trigger_px_edit.text() and float(self.sl_trigger_px_edit.text()) > 0 else None
            
            # Translate TP/SL trigger types from Chinese to English
            trigger_type_mapping = {
                "最新价": "last",
                "指数价": "index",
                "标记价": "mark"
            }
            
            tp_trigger_px_type = trigger_type_mapping[self.tp_trigger_type_combo.currentText()]
            sl_trigger_px_type = trigger_type_mapping[self.sl_trigger_type_combo.currentText()]
            
            # Place order using the order manager
            order_id = self.order_manager.place_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                price=price,
                amount=amount,
                td_mode=td_mode,
                cl_ord_id=cl_ord_id,
                pos_side=pos_side,
                reduce_only=reduce_only,
                tp_px=tp_px,
                tp_trigger_px=tp_trigger_px,
                sl_px=sl_px,
                sl_trigger_px=sl_trigger_px,
                tp_trigger_px_type=tp_trigger_px_type,
                sl_trigger_px_type=sl_trigger_px_type
            )
            
            if order_id:
                self.log(f"下单成功: {order_id}")
                self.refresh_orders()
            else:
                self.log("下单失败")
                
        except Exception as e:
            self.log(f"下单失败: {e}")
    
    def batch_place_orders(self):
        """Batch place orders"""
        # This is a placeholder for batch place orders functionality
        # In a real implementation, you would open a dialog to collect multiple orders
        self.log("批量下单功能开发中")
    
    def batch_cancel_orders(self):
        """Batch cancel orders"""
        selected_rows = self.orders_table.selectionModel().selectedRows()
        if not selected_rows:
            self.log("未选择订单")
            return
        
        cancel_orders = []
        for index in selected_rows:
            order_id = self.orders_table.item(index.row(), 0).text()
            symbol = self.orders_table.item(index.row(), 1).text()
            cancel_orders.append({
                "instId": symbol,
                "ordId": order_id
            })
        
        try:
            # Batch cancel orders
            result = self.api_client.batch_cancel_orders(cancel_orders)
            if result:
                self.log(f"批量撤单成功，共撤销 {len(result)} 个订单")
                self.refresh_orders()
            else:
                self.log("批量撤单失败")
        except Exception as e:
            self.log(f"批量撤单失败: {e}")
    
    def batch_amend_orders(self):
        """Batch amend orders"""
        # This is a placeholder for batch amend orders functionality
        # In a real implementation, you would open a dialog to collect amendment information
        self.log("批量修改订单功能开发中")
    
    def amend_selected_order(self):
        """Amend selected order"""
        selected_rows = self.orders_table.selectionModel().selectedRows()
        if not selected_rows:
            self.log("未选择订单")
            return
        
        if len(selected_rows) > 1:
            self.log("只能修改一个订单")
            return
        
        index = selected_rows[0]
        order_id = self.orders_table.item(index.row(), 0).text()
        
        # This is a placeholder for amend order functionality
        # In a real implementation, you would open a dialog to collect amendment information
        self.log(f"修改订单功能开发中，订单ID: {order_id}")
    
    def select_all_orders(self):
        """Select all orders"""
        self.orders_table.selectAll()
    
    def clear_order_selection(self):
        """Clear order selection"""
        self.orders_table.clearSelection()
    
    def refresh_orders(self):
        """Refresh orders display"""
        threading.Thread(target=self.fetch_orders).start()
    
    def cancel_selected_order(self):
        """Cancel selected order"""
        selected_rows = self.orders_table.selectionModel().selectedRows()
        if not selected_rows:
            self.log("未选择订单")
            return
        
        for index in selected_rows:
            order_id = self.orders_table.item(index.row(), 0).text()
            symbol = self.orders_table.item(index.row(), 1).text()
            
            try:
                success = self.order_manager.cancel_order(symbol, order_id)
                if success:
                    self.log(f"取消订单成功: {order_id}")
                    self.update_orders()
                else:
                    self.log(f"取消订单失败: {order_id}")
            except Exception as e:
                self.log(f"取消订单失败: {e}")
    
    def start_strategy(self):
        """Start trading strategy"""
        strategy = self.strategy_combo.currentText()
        mode = self.strategy_mode_combo.currentText()
        symbol = self.symbol_combo.currentText()
        
        self.log(f"启动策略: {strategy}，模式: {mode}，交易对: {symbol}")
        self.strategy_status.setText("状态: 运行中")
        self.strategy_status.setStyleSheet("color: green; font-weight: bold;")
        
        # Start strategy thread
        threading.Thread(target=self.run_strategy, args=(strategy, mode, symbol)).start()
    
    def stop_strategy(self):
        """Stop trading strategy"""
        self.log("停止策略")
        self.strategy_status.setText("状态: 已停止")
        self.strategy_status.setStyleSheet("color: red; font-weight: bold;")
    
    def run_strategy(self, strategy, mode, symbol):
        """Run the selected strategy"""
        try:
            if strategy == "原子核互反动力学策略":
                # 运行原子核互反动力学策略
                self.strategy_log.append(f"[{time.strftime('%H:%M:%S')}] 启动原子核互反动力学策略...")
                
                # 根据模式选择运行方式
                if mode == "回测":
                    # 回测模式
                    self.strategy_log.append(f"[{time.strftime('%H:%M:%S')}] 回测模式不支持，切换到实盘模式")
                    mode = "实盘"
                
                # 实盘模式
                import asyncio
                async def run_dynamics_strategy():
                    while self.strategy_status.text() == "状态: 运行中":
                        try:
                            await self.dynamics_strategy.run_live_trading(inst_id=symbol, interval=60)
                            await asyncio.sleep(1)
                        except Exception as e:
                            self.log(f"动力学策略错误: {e}")
                            self.strategy_log.append(f"[{time.strftime('%H:%M:%S')}] 策略错误: {e}")
                            break
                
                asyncio.run(run_dynamics_strategy())
            else:
                # 其他策略（passivbot）
                while self.strategy_status.text() == "状态: 运行中":
                    try:
                        self.strategy_log.append(f"[{time.strftime('%H:%M:%S')}] 策略运行中...")
                        time.sleep(5)  # Simulate strategy execution
                    except Exception as e:
                        self.log(f"策略错误: {e}")
                        break
        except Exception as e:
            self.log(f"策略运行错误: {e}")
            self.strategy_log.append(f"[{time.strftime('%H:%M:%S')}] 策略运行错误: {e}")
    
    def log(self, message):
        """Log a message"""
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        self.update_log.emit(f"[{timestamp}] {message}")
    
    def append_log(self, message):
        """Append log message to log widget"""
        self.log_text.append(message)
        # Auto-scroll to bottom
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
        
        # Also append to strategy log if it's a strategy-related message
        if "策略" in message:
            self.strategy_log.append(message)
            self.strategy_log.verticalScrollBar().setValue(self.strategy_log.verticalScrollBar().maximum())
    
    def api_login(self):
        """Login to API with current configuration, with network fault tolerance"""
        self.log("开始API登录...")
        self.login_status.setText("登录状态: 登录中...")
        self.login_status.setStyleSheet("font-weight: bold; color: orange;")
        
        # Get current configuration from UI
        login_config = {
            'api_key': self.api_key_edit.text(),
            'api_secret': self.api_secret_edit.text(),
            'passphrase': self.passphrase_edit.text(),
            'api_url': self.api_url_edit.text(),
            'api_ip': self.api_ip_list.toPlainText().split('\n')[0].strip() if self.api_ip_list.toPlainText() else None,
            'timeout': self.timeout_spin.value()
        }
        
        def login_thread():
            retry_count = 0
            max_retry = 3
            success = False
            error_msg = ""
            
            while retry_count < max_retry and not success:
                retry_count += 1
                try:
                    # Update login status to show retry count
                    self.login_status.setText(f"登录状态: 登录中（网络重试 {retry_count}/{max_retry}）")
                    self.login_status.setStyleSheet("font-weight: bold; color: orange;")
                    
                    # Create API client and test connection
                    from okx_api_client import OKXAPIClient
                    test_client = OKXAPIClient(
                        api_key=login_config['api_key'],
                        api_secret=login_config['api_secret'],
                        passphrase=login_config['passphrase'],
                        api_url=login_config['api_url'],
                        api_ip=login_config['api_ip'],
                        timeout=login_config['timeout']
                    )
                    
                    # Test connection with a simple API call
                    ticker = test_client.get_ticker('BTC-USDT-SWAP')
                    if ticker:
                        # Login successful
                        success = True
                    else:
                        error_msg = "无法获取行情数据"
                        time.sleep(1)
                except ConnectionResetError as e:
                    error_msg = f"网络连接重置: {str(e)}"
                    time.sleep(1)
                except Exception as e:
                    error_msg = f"API调用错误: {str(e)}"
                    break  # Don't retry for non-network errors
            
            if success:
                # Login successful
                self.login_status.setText("登录状态: 已登录")
                self.login_status.setStyleSheet("font-weight: bold; color: green;")
                self.api_login_btn.setEnabled(False)
                self.api_logout_btn.setEnabled(True)
                
                # Update login state in configuration
                self.config['api']['is_logged_in'] = True
                
                # Save the login configuration
                self.save_config()
                
                self.log("API登录成功")
            else:
                # Login failed
                self.login_status.setText(f"登录状态: 登录失败")
                self.login_status.setStyleSheet("font-weight: bold; color: red;")
                self.log(f"API登录失败: {error_msg}")
                self.log("可能是测试环境网络限制，建议：")
                self.log("1. 检查代理配置")
                self.log("2. 切换OKX主网")
                self.log("3. 验证API密钥")
        
        # Run login in background thread
        threading.Thread(target=login_thread).start()
    
    def api_logout(self):
        """Logout from API"""
        self.log("开始API登出...")
        
        # Clear login status
        self.login_status.setText("登录状态: 未登录")
        self.login_status.setStyleSheet("font-weight: bold; color: red;")
        
        # Update button states
        self.api_login_btn.setEnabled(True)
        self.api_logout_btn.setEnabled(False)
        
        # Update login state in configuration
        if 'is_logged_in' in self.config['api']:
            self.config['api']['is_logged_in'] = False
            
        # Save updated configuration
        self.save_config()
        
        self.log("API登出完成")
    
    def test_api_connection(self):
        """Test API connection with current configuration"""
        self.connection_status.setText("连接状态: 测试中...")
        self.connection_status.setStyleSheet("font-weight: bold; color: orange;")
        
        # Get current configuration from UI
        test_config = {
            'api_key': self.api_key_edit.text(),
            'api_secret': self.api_secret_edit.text(),
            'passphrase': self.passphrase_edit.text(),
            'api_url': self.api_url_edit.text(),
            'api_ip': self.api_ip_list.toPlainText().split('\n')[0].strip(),
            'timeout': self.timeout_spin.value()
        }
        
        # Create a test client with the current configuration
        def test_connection():
            try:
                from okx_api_client import OKXAPIClient
                test_client = OKXAPIClient(
                    api_key=test_config['api_key'],
                    api_secret=test_config['api_secret'],
                    passphrase=test_config['passphrase'],
                    api_url=test_config['api_url'],
                    api_ip=test_config['api_ip'],
                    timeout=test_config['timeout']
                )
                
                # Test with a simple API call
                ticker = test_client.get_ticker('BTC-USDT-SWAP')
                if ticker:
                    self.connection_status.setText("连接状态: 成功")
                    self.connection_status.setStyleSheet("font-weight: bold; color: green;")
                    self.log("API连接测试成功")
                else:
                    self.connection_status.setText("连接状态: 失败")
                    self.connection_status.setStyleSheet("font-weight: bold; color: red;")
                    self.log("API连接测试失败: 无法获取行情数据")
                    self.log("可能的原因:")
                    self.log("1. 网络环境问题，如防火墙或代理服务器阻止了连接")
                    self.log("2. SSL握手失败，远程主机强迫关闭了连接")
                    self.log("3. OKX API的反爬虫机制")
                    self.log("4. API密钥配置错误")
                    self.log("建议: 检查网络连接或使用代理服务器")
            except Exception as e:
                error_msg = str(e)
                self.connection_status.setText(f"连接状态: 失败 - {error_msg[:50]}...")
                self.connection_status.setStyleSheet("font-weight: bold; color: red;")
                self.log(f"API连接测试失败: {error_msg}")
                if "远程主机强迫关闭了一个现有的连接" in error_msg:
                    self.log("错误类型: SSL握手失败")
                    self.log("可能的原因:")
                    self.log("1. 防火墙或代理服务器阻止了SSL连接")
                    self.log("2. 网络环境问题")
                    self.log("3. OKX API的反爬虫机制")
                    self.log("建议: 检查网络连接或使用代理服务器")
                elif "getaddrinfo failed" in error_msg:
                    self.log("错误类型: DNS解析失败")
                    self.log("可能的原因:")
                    self.log("1. DNS服务器配置错误")
                    self.log("2. 网络连接问题")
                    self.log("建议: 检查DNS配置或网络连接")
                else:
                    self.log("建议: 检查网络连接或API配置")
        
        # Run test in a background thread to avoid freezing UI
        threading.Thread(target=test_connection).start()
    
    def test_proxy_connection(self):
        """Test proxy connection"""
        def test_proxy():
            try:
                proxy_enabled = self.proxy_enabled.isChecked()
                proxy_address = self.proxy_address.text()
                proxy_type = self.proxy_type.currentText()
                
                if not proxy_enabled:
                    self.log("代理未启用")
                    return
                
                if not proxy_address:
                    self.log("代理地址为空")
                    return
                
                # Create a simple test to check proxy connectivity
                import requests
                
                # Test HTTP proxy with requests
                self.log(f"开始测试{proxy_type}代理连接: {proxy_address}")
                
                # Test with requests
                try:
                    response = requests.get(
                        "https://www.okx.com/api/v5/public/ticker?instId=BTC-USDT-SWAP",
                        proxies={
                            "http": proxy_address,
                            "https": proxy_address
                        },
                        timeout=10
                    )
                    if response.status_code == 200:
                        self.log(f"代理HTTP请求成功，状态码: {response.status_code}")
                        self.log(f"代理测试通过！")
                    else:
                        self.log(f"代理HTTP请求失败，状态码: {response.status_code}")
                except Exception as e:
                    self.log(f"代理HTTP请求失败: {e}")
                
                # 简化WebSocket测试，只验证代理配置格式
                try:
                    # 检查代理地址格式
                    from urllib.parse import urlparse
                    parsed = urlparse(proxy_address)
                    if parsed.scheme in ['socks5', 'http', 'https']:
                        self.log(f"代理地址格式正确，支持WebSocket连接")
                    else:
                        self.log(f"代理地址格式可能不支持WebSocket连接")
                except Exception as e:
                    self.log(f"代理地址格式检查失败: {e}")
                
            except Exception as e:
                self.log(f"代理测试失败: {e}")
        
        # Run test in a background thread to avoid freezing UI
        threading.Thread(target=test_proxy).start()
    
    def detect_dpi_interception(self):
        """Detect DPI interception type and display results"""
        def detect():
            try:
                import subprocess
                import sys
                import os
                
                # 获取DPI检测脚本的完整路径
                script_path = os.path.join(os.path.dirname(__file__), 'detect_dpi_interception.py')
                
                self.log("开始DPI拦截类型检测...")
                
                # 在GUI中更新状态
                def update_gui_status(result_text, details):
                    self.dpi_detection_result.setText(result_text)
                    self.dpi_detection_details.setText(details)
                
                # 执行DPI检测脚本
                result = subprocess.run(
                    [sys.executable, script_path],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                # 解析检测结果
                output = result.stdout
                error = result.stderr
                
                # 提取关键信息
                if "DPI拦截类型: SSL握手阶段拦截" in output:
                    result_text = "SSL握手阶段拦截"
                    self.dpi_detection_result.setStyleSheet("font-weight: bold; color: red;")
                elif "DPI拦截类型: 应用层流量拦截" in output:
                    result_text = "应用层流量拦截"
                    self.dpi_detection_result.setStyleSheet("font-weight: bold; color: red;")
                elif "DPI拦截类型: 无DPI拦截" in output:
                    result_text = "无DPI拦截"
                    self.dpi_detection_result.setStyleSheet("font-weight: bold; color: green;")
                else:
                    result_text = "检测失败"
                    self.dpi_detection_result.setStyleSheet("font-weight: bold; color: orange;")
                
                # 组合详细信息
                details = output
                if error:
                    details += f"\n\n错误信息:\n{error}"
                
                # 更新GUI
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(0, lambda: update_gui_status(result_text, details))
                
                # 记录日志
                self.log(f"DPI拦截检测完成，结果: {result_text}")
                
            except subprocess.TimeoutExpired:
                self.log("DPI拦截检测超时")
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(0, lambda: self.dpi_detection_result.setText("检测超时"))
                QTimer.singleShot(0, lambda: self.dpi_detection_details.setText("检测过程超过60秒，可能网络环境复杂或代理响应缓慢"))
            except Exception as e:
                self.log(f"DPI拦截检测失败: {e}")
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(0, lambda: self.dpi_detection_result.setText("检测失败"))
                QTimer.singleShot(0, lambda: self.dpi_detection_details.setText(f"检测过程中发生错误: {str(e)}"))
        
        import threading
        threading.Thread(target=detect).start()
    
    def save_config(self, login_state=False):
        """Save current configuration to file with optional login state"""
        try:
            # Update configuration with UI values
            self.config['api']['api_key'] = self.api_key_edit.text()
            self.config['api']['api_secret'] = self.api_secret_edit.text()
            self.config['api']['passphrase'] = self.passphrase_edit.text()
            self.config['api']['api_url'] = self.api_url_edit.text()
            
            # Get API IPs from text edit
            api_ips = [ip.strip() for ip in self.api_ip_list.toPlainText().split('\n') if ip.strip()]
            self.config['api']['api_ips'] = api_ips
            # Set first IP as primary
            if api_ips:
                self.config['api']['api_ip'] = api_ips[0]
            
            self.config['api']['timeout'] = self.timeout_spin.value()
            
            # Save proxy configuration
            proxy_address = self.proxy_address.text()
            proxy_type = self.proxy_type.currentText().lower()
            
            # Initialize proxy config with empty values for all types
            proxy_config = {
                'enabled': self.proxy_enabled.isChecked(),
                'socks5': '',
                'http': '',
                'https': ''
            }
            
            # Set the proxy address for the selected type
            if proxy_config['enabled'] and proxy_address:
                proxy_config[proxy_type] = proxy_address
            
            self.config['api']['proxy'] = proxy_config
            
            # Save login state if specified
            if login_state:
                self.config['api']['is_logged_in'] = True
            
            # Save to file
            config_path = "d:\\Projects\\okx_trading_bot\\config\\okx_config.json"
            with open(config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            self.log("配置保存成功")
            
            # Restart API client with new configuration
            self.restart_api_client()
            
        except Exception as e:
            self.log(f"保存配置失败: {e}")
    
    def restart_api_client(self):
        """Restart API client with new configuration in a background thread"""
        def restart_thread():
            try:
                # Reinitialize API client with new configuration
                new_api_client = OKXAPIClient(
                    api_key=self.config['api']['api_key'],
                    api_secret=self.config['api']['api_secret'],
                    passphrase=self.config['api']['passphrase'],
                    is_test=self.config['api']['is_test'],
                    api_url=self.config['api']['api_url'],
                    api_ip=self.config['api'].get('api_ip'),
                    api_ips=self.config['api'].get('api_ips', []),
                    timeout=self.config['api']['timeout'],
                    proxy=self.config['api'].get('proxy', {})
                )
                
                # Update other services with new API client
                new_market_data_service = MarketDataService(new_api_client)
                new_order_manager = OrderManager(new_api_client)
                new_risk_manager = RiskManager(new_api_client)
                new_dynamics_strategy = DynamicsStrategy(new_api_client)
                
                # Switch to new clients on the main thread to ensure thread safety
                def update_gui():
                    self.api_client = new_api_client
                    self.market_data_service = new_market_data_service
                    self.order_manager = new_order_manager
                    self.risk_manager = new_risk_manager
                    self.dynamics_strategy = new_dynamics_strategy
                    
                    # Update DNS configuration display
                    if hasattr(self, 'current_dns_servers'):
                        current_region = self.api_client.get_dns_config().get('region', 'global')
                        self.dns_region_combo.setCurrentText(current_region)
                        self.current_dns_servers.setText(", ".join(self.api_client.get_dns_config()['servers']))
                    
                    self.log("API客户端已重新初始化")
                
                # Use QTimer to update GUI on main thread
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(0, update_gui)
            except Exception as e:
                self.log(f"重新初始化API客户端失败: {e}")
        
        # Run restart in a background thread
        import threading
        thread = threading.Thread(target=restart_thread)
        thread.daemon = True
        thread.start()
    
    def show_dns_stats(self):
        """
        Show DNS resolution statistics in a dialog
        """
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextEdit
        
        stats_dialog = QDialog(self)
        stats_dialog.setWindowTitle("DNS解析统计信息")
        stats_dialog.setGeometry(200, 200, 600, 400)
        
        layout = QVBoxLayout(stats_dialog)
        
        stats_text = QTextEdit()
        stats_text.setReadOnly(True)
        stats_text.setStyleSheet("font-family: Consolas, monospace;")
        
        # Get DNS statistics
        dns_stats = self.api_client.get_dns_stats()
        
        # Format statistics
        stats_str = f"""DNS解析统计信息

总查询次数: {dns_stats['total_queries']}
成功查询次数: {dns_stats['successful_queries']}
失败查询次数: {dns_stats['failed_queries']}
缓存命中次数: {dns_stats['cached_queries']}
成功率: {dns_stats['success_rate']:.2%}
缓存命中率: {dns_stats['cache_hit_rate']:.2%}
平均解析时间: {dns_stats['average_resolve_time']:.3f}s

DNS服务器性能:
"""
        
        for server, perf in dns_stats['server_performance'].items():
            total = perf['success'] + perf['failure']
            if total > 0:
                success_rate = perf['success'] / total
                avg_time = sum(perf['time']) / len(perf['time']) if perf['time'] else 0
                stats_str += f"{server}: 成功 {perf['success']}, 失败 {perf['failure']}, 成功率 {success_rate:.2%}, 平均时间 {avg_time:.3f}s\n"
        
        # Add DNS alerts information
        stats_str += f"\nDNS告警信息:\n"
        stats_str += f"告警次数: {dns_stats['alerts']['count']}\n"
        stats_str += f"失败率阈值: {dns_stats['alerts']['failure_rate_threshold']:.2%}\n"
        
        # Add current DNS configuration
        stats_str += f"\n当前DNS配置:\n"
        stats_str += f"DNS区域: {dns_stats['current_config']['region']}\n"
        stats_str += f"DNS服务器: {', '.join(dns_stats['current_config']['servers'])}\n"
        stats_str += f"超时时间: {dns_stats['current_config']['timeout']}秒\n"
        stats_str += f"重试次数: {dns_stats['current_config']['retry_count']}\n"
        
        stats_text.setText(stats_str)
        layout.addWidget(stats_text)
        
        stats_dialog.exec_()
    
    def update_dns_config_display(self):
        """
        Update DNS configuration display in GUI
        """
        try:
            if hasattr(self, 'api_client') and self.api_client:
                dns_config = self.api_client.get_dns_config()
                if dns_config:
                    region = dns_config.get('region', 'global')
                    servers = dns_config.get('servers', [])
                    if hasattr(self, 'dns_region_combo'):
                        self.dns_region_combo.setCurrentText(region)
                    if hasattr(self, 'current_dns_servers'):
                        self.current_dns_servers.setText(", ".join(servers))
        except Exception as e:
            self.log(f"更新DNS配置显示失败: {e}")
    
    def update_dns_configuration(self):
        """
        Update DNS configuration based on UI settings
        """
        try:
            region = self.dns_region_combo.currentText()
            
            # Update DNS configuration
            result = self.api_client.switch_dns_region(region)
            
            if result:
                # Update display
                self.update_dns_config_display()
                self.log(f"DNS配置已更新，区域切换到 {region}")
                self.dns_status_label.setText("DNS状态: 已更新")
                self.dns_status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.log(f"更新DNS配置失败，无效区域: {region}")
                self.dns_status_label.setText("DNS状态: 配置失败")
                self.dns_status_label.setStyleSheet("color: red; font-weight: bold;")
        except Exception as e:
            self.log(f"更新DNS配置失败: {e}")
            self.dns_status_label.setText("DNS状态: 配置错误")
            self.dns_status_label.setStyleSheet("color: red; font-weight: bold;")
    
    def init_health_check(self):
        """Initialize health check timer and monitoring"""
        # Health check timer
        self.health_check_timer = QTimer()
        self.health_check_timer.timeout.connect(self.perform_health_check)
        
        # Start with default interval from config or 5 minutes
        interval = self.config.get('market_data', {}).get('update_interval', 10) * 60
        self.health_check_timer.start(interval * 1000)  # Convert to milliseconds
        
        # DNS Health check timer
        self.dns_health_check_timer = QTimer()
        self.dns_health_check_timer.timeout.connect(self.perform_dns_health_check)
        self.dns_health_check_timer.start(30000)  # Check DNS every 30 seconds
        
        # Health status variables
        self.last_health_check = time.time()
        self.api_health_status = "healthy"
        self.last_api_error = None
        
        # DNS health status variables
        self.dns_health_status = "unhealthy"
        self.last_dns_check = time.time()
        
        self.log(f"健康检查已启动，检查间隔: {interval}秒")
        self.log("DNS健康检查已启动，检查间隔: 30秒")
    
    def perform_health_check(self):
        """Perform API health check"""
        if not self.enable_health_check.isChecked():
            return
        
        self.log("执行API健康检查...")
        
        def check_api_health():
            try:
                # Test with a simple API call
                ticker = self.api_client.get_ticker('BTC-USDT-SWAP')
                
                if ticker:
                    self.api_health_status = "healthy"
                    self.last_api_error = None
                    self.log("API健康检查通过")
                    
                    # Update current active IP display if available
                    if hasattr(self, 'current_active_ip'):
                        current_ip = self.api_client.get_current_ip()
                        self.current_active_ip.setText(f"当前活跃IP: {current_ip}")
                else:
                    self.api_health_status = "unhealthy"
                    self.last_api_error = "无法获取行情数据"
                    self.log(f"API健康检查失败: {self.last_api_error}")
                    self.show_alert("API连接警告", f"API健康检查失败: {self.last_api_error}")
                    
                    # Try to switch to next IP
                    self.api_client.switch_to_next_ip()
            except Exception as e:
                self.api_health_status = "unhealthy"
                self.last_api_error = str(e)
                self.log(f"API健康检查失败: {self.last_api_error}")
                self.show_alert("API连接错误", f"API健康检查失败: {self.last_api_error}")
                
                # Try to switch to next IP
                self.api_client.switch_to_next_ip()
            
            # Update status indicator
            self.update_status_indicator()
        
        # Run health check in a background thread
        threading.Thread(target=check_api_health).start()
    
    def perform_dns_health_check(self):
        """
        Perform DNS health check
        """
        try:
            # Get DNS statistics
            dns_stats = self.api_client.get_dns_stats()
            self.last_dns_check = time.time()
            
            # Update DNS status indicator
            if dns_stats['total_queries'] > 0:
                success_rate = dns_stats['success_rate']
                if success_rate > 0.9:
                    self.dns_health_status = "healthy"
                    self.dns_status_label.setText("DNS状态: 良好")
                    self.dns_status_label.setStyleSheet("color: green; font-weight: bold;")
                elif success_rate > 0.7:
                    self.dns_health_status = "warning"
                    self.dns_status_label.setText(f"DNS状态: 警告 ({success_rate:.1%})")
                    self.dns_status_label.setStyleSheet("color: orange; font-weight: bold;")
                else:
                    self.dns_health_status = "unhealthy"
                    self.dns_status_label.setText(f"DNS状态: 异常 ({success_rate:.1%})")
                    self.dns_status_label.setStyleSheet("color: red; font-weight: bold;")
                    
                    # Try to switch DNS region if success rate is too low
                    self.log(f"DNS解析成功率过低: {success_rate:.2%}，尝试切换DNS区域")
                    
                    # Get available regions and current region
                    regions = ["global", "asia", "europe", "north_america"]
                    current_region = self.api_client.get_dns_config().get('region', 'global')
                    
                    # Find next region to switch to
                    current_index = regions.index(current_region)
                    next_index = (current_index + 1) % len(regions)
                    next_region = regions[next_index]
                    
                    # Switch to next region
                    result = self.api_client.switch_dns_region(next_region)
                    if result:
                        self.dns_region_combo.setCurrentText(next_region)
                        self.current_dns_servers.setText(", ".join(self.api_client.get_dns_config()['servers']))
                        self.log(f"已切换DNS区域到 {next_region}")
                        self.dns_status_label.setText(f"DNS状态: 已切换到 {next_region}")
                    else:
                        self.log(f"切换DNS区域到 {next_region} 失败")
            else:
                # Not enough queries to determine health
                self.dns_status_label.setText("DNS状态: 未检测")
                self.dns_status_label.setStyleSheet("color: blue; font-weight: bold;")
        except Exception as e:
            self.log(f"DNS健康检查失败: {e}")
            self.dns_status_label.setText("DNS状态: 检查失败")
            self.dns_status_label.setStyleSheet("color: red; font-weight: bold;")
    
    def update_status_indicator(self):
        """Update the status indicator based on API health"""
        if self.api_health_status == "healthy":
            self.status_label.setText("状态: 正常")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.status_label.setText(f"状态: 异常 - {self.last_api_error}")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
    
    def show_alert(self, title, message):
        """Show an alert message to the user in main thread"""
        if self.is_closed:
            return
        
        from PyQt5.QtWidgets import QMessageBox
        from PyQt5.QtCore import QTimer
        from PyQt5.QtCore import QThread
        
        def display_alert():
            """Display the alert in main thread"""
            if self.is_closed:
                return
            try:
                QMessageBox.warning(self, title, message)
            except Exception as e:
                self.log(f"显示弹窗失败: {e}")
        
        # 确保在主线程中显示模态对话框
        if QThread.currentThread() == QThread.mainThread():
            display_alert()
        else:
            # 使用QTimer确保在主线程中执行
            QTimer.singleShot(0, display_alert)
            self.log("在非主线程中调用show_alert，将在主线程中显示弹窗")
    
    def init_data_updates(self):
        """Initialize periodic data updates"""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_all_data)
        self.timer.start(5000)  # Update every 5 seconds

def main():
    """Main function"""
    # Create application
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Create and show GUI
    gui = TradingGUI()
    gui.show()
    
    # Run application
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
