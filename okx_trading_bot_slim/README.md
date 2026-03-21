# OKX 交易机器人

## 项目介绍

OKX 交易机器人是一个基于 PyQt5 开发的 GUI 交易机器人，支持 OKX 交易所的 REST API 和 WebSocket 连接。该项目采用多智能体架构设计，包含市场数据、订单管理、风险管理和策略执行等核心模块。

### 主要功能

- 基于 PyQt5 的图形用户界面
- OKX REST API 和 WebSocket 客户端支持
- WebSocket 连接管理和自动重连
- 集中式配置管理
- 增强的日志记录
- 健康检查机制
- 指数退避重试机制
- 多智能体架构设计
- 策略集成（包括原子核互反动力学策略）
- 策略添加功能
- 系统自动加载功能
- 优化的线程管理

## 安装与运行

### 系统要求

- Windows 10/11
- Python 3.8+
- 至少 2GB RAM
- 至少 100MB 可用磁盘空间

### 依赖安装

```bash
pip install -r requirements.txt
```

### 直接运行

```bash
python main.py
```

### 打包运行

#### 打包命令

```bash
pyinstaller --onefile --windowed --name okx_trading_bot main.py
```

#### 运行打包后的程序

直接双击生成的 `okx_trading_bot.exe` 文件即可运行。

## 配置说明

### 配置文件

配置文件位于 `config/okx_config.json`，包含 API 配置、WebSocket 配置等。

## 使用说明

### 启动机器人

1. 启动程序后，系统会自动加载功能
2. 进入配置管理页面
3. 输入您的 OKX API 密钥、密钥密码和密码短语
4. 点击 "保存配置" 按钮
5. 切换到交易页面
6. 点击 "更新数据" 按钮获取实时行情

### 策略管理

1. 进入策略管理页面
2. 选择策略类型
3. 配置策略参数
4. 点击 "激活策略" 按钮启动策略
5. 点击 "添加策略" 按钮添加自定义策略

### 监控机器人

- 交易页面显示实时行情和交易状态
- 日志页面显示详细的运行日志
- 网络状态页面显示系统和网络状态

### 停止机器人

- 直接关闭程序窗口

## 帮助与支持

### 常见问题

1. **连接失败**
   - 检查 API 密钥是否正确
   - 检查网络连接
   - 检查防火墙设置

2. **GUI 冻结**
   - 等待一段时间，机器人会自动恢复
   - 或尝试重启程序

3. **WebSocket 断开**
   - 机器人会自动重连
   - 检查网络稳定性

4. **如何添加自定义策略**
   - 点击 "添加策略" 按钮
   - 在弹出的对话框中输入策略名称、策略类名和模块路径
   - 点击 "添加" 按钮

### 日志查看

日志文件位于 `logs/` 目录下，按日期和大小轮换。

### 联系方式

如有问题或建议，请通过 GitHub Issues 提交。

## 代码结构

```
okx_trading_bot/
├── main.py                  # 主入口文件
├── trading_gui.py           # GUI 界面
├── okx_api_client.py        # OKX API 客户端
├── okx_websocket_client.py  # OKX WebSocket 客户端
├── agents/                  # 智能体模块
│   ├── base_agent.py
│   ├── decision_coordination_agent.py
│   ├── market_data_agent.py
│   ├── order_agent.py
│   ├── risk_management_agent.py
│   └── strategy_execution_agent.py
├── commons/                 # 公共模块
│   ├── agent_registry.py
│   ├── config_manager.py
│   ├── event_bus.py
│   ├── health_checker.py
│   └── logger_config.py
├── services/                # 服务模块
│   ├── market_data/         # 市场数据服务
│   ├── order_management/    # 订单管理服务
│   └── risk_management/     # 风险管理服务
├── strategies/              # 策略模块
│   ├── base_strategy.py
│   ├── dynamics_strategy.py
│   └── passivbot_integrator.py
├── config/                  # 配置目录
│   └── okx_config.json     # OKX 配置文件
├── requirements.txt         # 依赖列表
├── 使用说明.md              # 使用说明
├── 维护手册.md              # 维护手册
├── okx_trading_bot_slim/    # 精简版本
├── okx_trading_bot_slim.zip # 精简版本压缩包
└── README.md                # 项目说明
```

## 许可证

MIT License

## 更新日志

### v1.0.0

- 初始版本
- 支持 OKX REST API 和 WebSocket
- Socks5 代理支持
- PyQt5 GUI 界面
- 集中式配置管理
- 增强的日志记录
- 健康检查机制

### v1.1.0

- 多智能体架构实现
- Passivbot 策略集成
- 服务层模块化设计
- 完善的错误处理和异常捕获
- 网络连接稳定性优化

### v1.2.0

- 移除代理功能，只保留基本 API 调用方式
- 添加策略添加功能
- 移除"加载功能"按钮，系统启动时自动加载功能
- 优化线程管理，当没有活跃策略时降低线程执行频率
- 清理无用文件，创建slim版本
- 更新使用说明和维护手册

## 贡献

欢迎提交 Issue 和 Pull Request！

## 免责声明

本交易机器人仅供学习和研究使用，不构成投资建议。使用本机器人进行交易，风险自负。