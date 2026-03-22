# OKX交易机器人智能体通信协议

## 智能体依赖关系

### 核心智能体依赖图

```
DecisionCoordinationAgent (决策协调智能体)
├── MarketDataAgent (市场数据智能体)
├── RiskManagementAgent (风险控制智能体)
├── StrategyExecutionAgent (策略执行智能体)
└── OrderAgent (订单管理智能体)
```

### 详细依赖关系

1. **决策协调智能体**
   - 依赖：所有其他智能体
   - 职责：协调各智能体工作，处理决策逻辑

2. **市场数据智能体**
   - 依赖：无（基础服务）
   - 职责：获取和处理市场数据

3. **风险控制智能体**
   - 依赖：市场数据智能体
   - 职责：监控风险，执行风险控制策略

4. **策略执行智能体**
   - 依赖：市场数据智能体、风险控制智能体
   - 职责：执行交易策略，生成交易信号

5. **订单管理智能体**
   - 依赖：市场数据智能体、风险控制智能体、策略执行智能体
   - 职责：管理订单的创建、更新和取消

## 事件通信协议

### 事件列表

#### 市场数据事件
- **market_data_updated**：市场数据更新事件
  - 数据结构：
    ```json
    {
      "symbol": "BTC-USDT-SWAP",
      "data": {
        "symbol": "BTC-USDT-SWAP",
        "price": 60000.0,
        "open": 59000.0,
        "high": 61000.0,
        "low": 58000.0,
        "volume": 10000.0,
        "change": 1000.0,
        "change_pct": 1.69
      },
      "timestamp": 1640995200.0
    }
    ```

#### 订单事件
- **order_placed**：订单已下单
- **order_updated**：订单已更新
- **order_canceled**：订单已取消

#### 策略事件
- **strategy_registered**：策略已注册
- **strategy_activated**：策略已激活
- **strategy_deactivated**：策略已停用
- **strategy_paused**：策略已暂停
- **strategy_resumed**：策略已恢复

#### 风险事件
- **risk_alert**：风险警报
- **risk_state_updated**：风险状态更新

#### 智能体状态事件
- **agent_status_changed**：智能体状态变化
  - 数据结构：
    ```json
    {
      "agent_id": "market_data_agent",
      "status": "运行中"
    }
    ```

## 消息通信协议

### 消息类型

#### 订阅交易对
```json
{
  "type": "subscribe_symbol",
  "symbol": "BTC-USDT-SWAP"
}
```

#### 取消订阅交易对
```json
{
  "type": "unsubscribe_symbol",
  "symbol": "BTC-USDT-SWAP"
}
```

#### 获取市场数据
```json
{
  "type": "get_market_data",
  "symbol": "BTC-USDT-SWAP",
  "sender": "strategy_execution_agent"
}
```

#### 市场数据响应
```json
{
  "type": "market_data_response",
  "symbol": "BTC-USDT-SWAP",
  "data": {
    "symbol": "BTC-USDT-SWAP",
    "price": 60000.0,
    "open": 59000.0,
    "high": 61000.0,
    "low": 58000.0,
    "volume": 10000.0,
    "change": 1000.0,
    "change_pct": 1.69
  }
}
```

## 通信流程

### 1. 市场数据获取流程

1. 决策协调智能体发送订阅消息给市场数据智能体
2. 市场数据智能体开始获取指定交易对的数据
3. 市场数据智能体定期发布market_data_updated事件
4. 其他智能体订阅该事件并处理市场数据

### 2. 策略执行流程

1. 策略执行智能体订阅market_data_updated事件
2. 收到市场数据后，执行策略逻辑
3. 生成交易信号并发布trading_signal事件
4. 订单管理智能体处理交易信号并执行订单

### 3. 风险控制流程

1. 风险控制智能体订阅market_data_updated和order_placed事件
2. 监控市场数据和订单状态
3. 当风险超过阈值时，发布risk_alert事件
4. 其他智能体根据风险警报调整行为

## 通信规范

### 事件命名规范
- 使用小写字母和下划线
- 采用动词+名词的结构
- 例如：market_data_updated, order_placed

### 消息格式规范
- 使用JSON格式
- 包含type字段标识消息类型
- 包含必要的业务数据字段
- 包含可选的元数据字段（如timestamp, sender等）

### 错误处理规范
- 所有异常必须记录日志
- 事件处理失败不应影响其他事件的处理
- 智能体之间的通信应有超时机制

## 扩展指南

### 添加新智能体
1. 继承BaseAgent类
2. 实现必要的方法（start, stop, process_message等）
3. 注册到智能体注册表
4. 订阅相关事件
5. 发布必要的事件

### 添加新事件
1. 在EventBus类中定义新的信号
2. 更新事件列表文档
3. 确保所有相关智能体正确处理新事件

### 添加新消息类型
1. 在相关智能体的process_message方法中添加处理逻辑
2. 更新消息类型文档
3. 确保消息格式符合规范

## 版本控制

- 通信协议版本：v1.0
- 变更记录：
  - v1.0：初始版本，定义了基础通信协议
