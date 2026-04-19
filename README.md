# OKX 交易机器人

## 项目概述

OKX 交易机器人是一个基于 OKX 交易所 API 的自动化交易系统，支持现货、杠杆、合约和期权交易。系统采用事件驱动架构，通过智能体（Agent）实现自动化交易策略的执行和管理。

## 项目结构

```
okx_trading_bot/
├── core/                  # 核心模块
│   ├── api/               # API 客户端
│   ├── agents/            # 智能体
│   ├── config/            # 配置管理
│   ├── events/            # 事件系统
│   ├── traders/           # 交易器
│   └── utils/             # 工具类
├── strategies/            # 交易策略
├── config/                # 配置文件
├── main_new.py            # 主程序
└── README.md              # 项目文档
```

## 核心模块

### API 客户端
- `okx_rest_client.py`：OKX REST API 客户端
- `okx_websocket_client.py`：OKX WebSocket API 客户端

### 智能体
- `coordinator_agent.py`：协调智能体，负责协调其他智能体的工作
- `order_agent.py`：订单智能体，负责订单的执行和管理
- `order_agent_adapter.py`：订单智能体适配器，将原有 OrderAgent 适配到新的交易器架构
- `strategy_agent.py`：策略智能体，负责策略的执行和管理
- `risk_agent.py`：风险智能体，负责风险控制
- `signal_agent.py`：信号智能体，负责信号的处理和管理
- `profit_growth_agent.py`：盈利增长智能体，负责盈利增长的管理
- `market_sentiment_agent.py`：市场情绪智能体，负责市场情绪的分析和管理

### 交易器
- `base_trader.py`：交易器基类，定义所有交易器的通用接口
- `spot_trader.py`：现货交易器
- `margin_trader.py`：杠杆交易器
- `contract_trader.py`：合约交易器
- `options_trader.py`：期权交易器
- `trader_manager.py`：交易器管理器，负责交易器的创建和管理

### 事件系统
- `event_bus.py`：事件总线，负责事件的发布和订阅
- `event.py`：事件类，定义事件的结构和类型

### 配置管理
- `env_manager.py`：环境管理器，负责加载和管理配置

## 配置文件

### 配置文件结构

- `config.yaml`：默认配置文件
- `config_live.yaml`：实盘配置文件
- `config_test.yaml`：测试配置文件
- `current_env.json`：当前环境配置文件

### 配置示例

```yaml
# API 配置
api:
  api_key: "your_api_key"
  api_secret: "your_api_secret"
  passphrase: "your_passphrase"
  is_test: true

# 交易配置
trading:
  mode: "spot"  # spot, margin, contract, options
  leverage: 2
  min_order_amount: 1

# 策略配置
strategy:
  name: "NuclearDynamicsStrategy"
  params:
    param1: value1
    param2: value2

# 市场配置
market:
  cryptocurrencies: ["BTC", "ETH"]
  refresh_interval: 1

# 通知配置
notification:
  email:
    enabled: false
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    sender_email: "your_email@gmail.com"
    sender_password: "your_email_password"
    receiver_email: "your_email@gmail.com"
  telegram:
    enabled: false
    bot_token: "your_bot_token"
    chat_id: "your_chat_id"
```

## 运行系统

### 准备工作

1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

2. 配置 API 密钥：
   - 复制 `config/config.yaml` 到 `config/config_live.yaml` 和 `config/config_test.yaml`
   - 在相应的配置文件中填写 API 密钥

3. 设置当前环境：
   - 修改 `config/current_env.json` 文件，将 `env` 字段设置为 `live` 或 `test`

### 运行系统

```bash
python3 main_new.py
```

## 交易策略

### 策略目录

- `strategies/` 目录包含各种交易策略

### 策略示例

- `nuclear_dynamics_strategy.py`：核动力策略，基于市场数据生成交易信号

## 系统功能

- **自动交易**：根据策略自动执行交易
- **多交易模式**：支持现货、杠杆、合约和期权交易
- **多策略支持**：支持多种交易策略
- **风险管理**：内置风险控制机制
- **市场情绪分析**：分析市场情绪，辅助交易决策
- **盈利增长管理**：管理盈利增长，实现复利效应
- **实时监控**：实时监控系统运行状态和交易情况
- **通知功能**：支持邮件和 Telegram 通知

## 系统优化

### 配置管理优化
- 配置验证：确保配置文件的格式和内容正确
- 配置热加载：无需重启系统即可应用配置更改
- 配置加密：对敏感配置（如 API 密钥）进行加密存储
- 配置版本管理：方便回滚配置更改

### 交易器优化
- 交易器池：支持动态创建和管理交易器
- 交易器监控：实时监控交易器的运行状态
- 交易器容错：当交易器失败时自动切换到备用交易器
- 交易器负载均衡：提高系统的并发处理能力

### 策略优化
- 策略参数优化：自动调整策略参数以获得最佳性能
- 策略组合：支持多个策略的协同工作
- 策略回测：评估策略的历史性能
- 策略自动切换：根据市场情况自动选择最佳策略

### 风险管理优化
- 风险评估：提供更全面的风险评估指标
- 风险控制：实现更精细的风险控制机制
- 风险预警：当风险超过阈值时及时通知用户
- 风险报告：生成风险报告，帮助用户了解系统的风险状况

### 系统架构优化
- 模块化设计：提高代码的可维护性和可扩展性
- 异步处理：提高系统的并发处理能力
- 缓存机制：减少重复计算和 API 调用
- 日志系统：提供更详细的系统运行日志

### API 调用优化
- API 速率限制：避免超过交易所的 API 调用限制
- API 重试机制：提高 API 调用的成功率
- API 响应缓存：减少重复的 API 调用
- API 错误处理：提高系统的稳定性

### 数据处理优化
- 数据缓存：减少重复的数据处理
- 数据预处理：提高数据处理的效率
- 数据压缩：减少数据存储和传输的开销
- 数据可视化：帮助用户直观地了解市场情况

### 用户界面优化
- 监控面板：显示系统的运行状态和交易情况
- 配置界面：方便用户调整系统配置
- 报表功能：生成交易报表和系统运行报表
- 告警系统：当系统出现异常时及时通知用户

### 安全性优化
- API 密钥管理：实现更安全的 API 密钥管理机制
- 数据加密：对敏感数据进行加密存储和传输
- 访问控制：限制对系统的访问
- 安全审计：记录系统的操作日志

### 文档优化
- API 文档：完善 API 文档，方便开发者使用系统的 API
- 配置文档：提供详细的配置文档，帮助用户理解和配置系统
- 开发文档：添加开发文档，帮助开发者理解系统的架构和代码
- 用户指南：提供用户指南，帮助用户使用系统的功能

## 注意事项

- 系统需要 OKX 交易所的 API 密钥才能运行
- 建议先在测试环境中运行系统，熟悉系统的功能和操作
- 系统的交易策略可能存在风险，使用时请谨慎
- 系统的性能和稳定性取决于网络连接和 API 响应速度

## 贡献

欢迎对系统进行改进和扩展，如有问题或建议，请提交 issue 或 pull request。

## 许可证

本项目采用 MIT 许可证。