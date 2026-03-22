from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QTabWidget, QLabel

class TradingGUI(QMainWindow):
    def __init__(self, config, trading_bot):
        super().__init__()
        self.setWindowTitle("OKX交易机器人")
        self.setGeometry(100, 100, 1200, 800)
        
        # 先初始化UI，确保界面能够快速显示
        self.init_ui()
    
    def init_ui(self):
        """Initialize the main UI"""
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # Tab widget for main content
        self.tab_widget = QTabWidget()
        
        # Trading tab
        trading_tab = QWidget()
        trading_layout = QVBoxLayout(trading_tab)
        trading_layout.addWidget(QLabel("交易标签页"))
        self.tab_widget.addTab(trading_tab, "交易")
        
        main_layout.addWidget(self.tab_widget)
        self.setCentralWidget(main_widget)
