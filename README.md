# OKX 交易机器人

## 项目介绍

OKX 交易机器人是一个基于 PyQt5 开发的 GUI 交易机器人，支持 OKX 交易所的 REST API 和 WebSocket 连接，并提供 Socks5 代理支持。

### 主要功能

- 基于 PyQt5 的图形用户界面
- OKX REST API 和 WebSocket 客户端支持
- Socks5、HTTPS、HTTP 代理配置
- WebSocket 连接管理和自动重连
- 集中式配置管理
- 增强的日志记录
- 健康检查机制
- 指数退避重试机制
- DNS 解析和 SSL/TLS 指纹识别

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

配置文件位于 `config.ini`，包含以下主要部分：

#### API 配置

```ini
[api]
api_key = your_api_key
secret_key = your_secret_key
passphrase = your_passphrase
proxy_type = socks5
proxy_host = 127.0.0.1
proxy_port = 1080
proxy_username = 
proxy_password = 
```

#### WebSocket 配置

```ini
[websocket]
enable = True
ping_interval = 30
ping_timeout = 10
max_reconnect_attempts = 5
reconnect_delay = 2
```

#### GUI 配置

```ini
[gui]
enable_sound = True
auto_start = False
```

### 服务器配置

如果您需要在服务器上运行机器人，建议：

1. 使用 Linux 服务器（推荐 Ubuntu 20.04+）
2. 安装 Python 3.8+ 和必要的依赖
3. 配置防火墙，允许机器人访问 OKX API 端口
4. 使用 `screen` 或 `tmux` 保持机器人在后台运行

## 使用说明

### 启动机器人

1. 启动程序后，进入配置页面
2. 输入您的 OKX API 密钥、密钥密码和密码短语
3. 配置代理信息（如果需要）
4. 点击 "保存配置" 按钮
5. 切换到交易页面
6. 点击 "开始交易" 按钮

### 监控机器人

- 交易页面显示实时行情和交易状态
- 日志页面显示详细的运行日志
- 健康检查页面显示系统和网络状态

### 停止机器人

- 在交易页面点击 "停止交易" 按钮
- 或直接关闭程序窗口

## 帮助与支持

### 常见问题

1. **连接失败**
   - 检查 API 密钥是否正确
   - 检查网络连接和代理配置
   - 检查防火墙设置

2. **GUI 冻结**
   - 等待一段时间，机器人会自动恢复
   - 或尝试重启程序

3. **WebSocket 断开**
   - 机器人会自动重连
   - 检查网络稳定性

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
├── commons/
│   ├── config_manager.py    # 配置管理器
│   ├── logger_config.py     # 日志配置
│   └── health_checker.py    # 健康检查器
├── config.ini               # 配置文件
├── requirements.txt         # 依赖列表
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

## 贡献

欢迎提交 Issue 和 Pull Request！

## 免责声明

本交易机器人仅供学习和研究使用，不构成投资建议。使用本机器人进行交易，风险自负。
