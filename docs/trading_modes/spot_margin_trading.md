# OKX 现货杠杆交易模式

## 概述

现货杠杆交易允许用户借入资金进行交易，放大收益的同时也放大风险。

### 特点
- **杠杆交易**：可借入资金放大交易规模
- **双向交易**：支持做多和做空
- **利息费用**：借入资金需要支付利息
- **强制平仓**：风险过高时会被强制平仓

## 账户模式

### 币币杠杆 (Margin Trading)
- 在现货模式基础上开通借币功能
- 支持全仓和逐仓两种模式
- 可以借入交易对中的任意一种币种

### 全仓模式 (Cross Margin)
- 所有仓位共享保证金
- 风险分散，不易被单一仓位爆仓
- 资金利用率高

### 逐仓模式 (Isolated Margin)
- 每个仓位独立保证金
- 风险隔离，单一仓位爆仓不影响其他仓位
- 适合高风险策略

## API 接口

### 账户相关

#### 获取杠杆账户信息
```http
GET /api/v5/account/balance
```

**响应字段（杠杆模式特有）：**
- `liab`: 币种负债额
- `interest`: 计息，应扣未扣利息
- `maxLoan`: 币种最大可借
- `crossLiab`: 币种全仓负债额
- `isoLiab`: 币种逐仓负债额
- `twap`: 当前负债币种触发自动换币的风险

#### 获取最大可借
```http
GET /api/v5/account/max-loan
```

**请求参数：**
- `instId`: 产品ID
- `mgnMode`: 保证金模式，"cross" 或 "isolated"
- `ccy`: 币种

### 交易相关

#### 杠杆下单
```http
POST /api/v5/trade/order
```

**请求参数：**
- `instId`: 产品ID，如 "BTC-USDT"
- `tdMode`: 交易模式，"cross"（全仓）或 "isolated"（逐仓）
- `side`: 订单方向
- `ordType`: 订单类型
- `sz`: 委托数量
- `px`: 委托价格（限价单）

**示例（全仓买入）：**
```json
{
  "instId": "BTC-USDT",
  "tdMode": "cross",
  "side": "buy",
  "ordType": "market",
  "sz": "100",
  "tgtCcy": "quote_ccy"
}
```

### 借币还币

#### 借币
```http
POST /api/v5/account/borrow-repay
```

**请求参数：**
- `ccy`: 借币币种
- `amt`: 借币金额
- `side`: "borrow"（借入）

#### 还币
```http
POST /api/v5/account/borrow-repay
```

**请求参数：**
- `ccy`: 还币币种
- `amt`: 还币金额
- `side`: "repay"（归还）

### 杠杆管理

#### 设置杠杆倍数
```http
POST /api/v5/account/set-leverage
```

**请求参数：**
- `instId`: 产品ID
- `lever`: 杠杆倍数，如 "5"、"10"
- `mgnMode`: 保证金模式

**不同模式设置：**

1. **逐仓币币杠杆**（币对层面）
```json
{
  "instId": "BTC-USDT",
  "lever": "5",
  "mgnMode": "isolated"
}
```

2. **全仓币币杠杆**（币种层面）
```json
{
  "ccy": "BTC",
  "lever": "5",
  "mgnMode": "cross"
}
```

## 交易规则

### 杠杆倍数
- 币币杠杆：最高 5 倍
- 不同币种可能有不同限制

### 利息计算
```
利息 = 借币金额 × 日利率 × 借币天数
```

### 维持保证金率
- 根据杠杆倍数不同而变化
- 杠杆越高，维持保证金率越高

### 强制平仓
当保证金率低于维持保证金率时，会触发强制平仓。

## 风险管理

### 保证金率计算
```
保证金率 = (权益 / 仓位价值) × 100%
```

### 风险等级
- **安全**：保证金率 > 维持保证金率 + 10%
- **警告**：维持保证金率 < 保证金率 < 维持保证金率 + 10%
- **危险**：保证金率 < 维持保证金率

### 自动换币风险
- `twap` 字段表示自动换币风险等级
- 0-5，数字越大风险越高
- 当 twap >= 1 时，可能触发自动换币

## 代码示例

### Python 杠杆买入（全仓）
```python
async def margin_buy_cross(inst_id: str, usdt_amount: str, leverage: str = "5"):
    """全仓杠杆买入"""
    # 1. 设置杠杆倍数
    await client.post("/api/v5/account/set-leverage", {
        "instId": inst_id,
        "lever": leverage,
        "mgnMode": "cross"
    })
    
    # 2. 下单
    order = {
        "instId": inst_id,
        "tdMode": "cross",  # 全仓模式
        "side": "buy",
        "ordType": "market",
        "sz": usdt_amount,
        "tgtCcy": "quote_ccy"
    }
    return await client.post("/api/v5/trade/order", order)
```

### Python 借币
```python
async def borrow_currency(ccy: str, amt: str):
    """借入币种"""
    borrow_request = {
        "ccy": ccy,
        "amt": amt,
        "side": "borrow"
    }
    return await client.post("/api/v5/account/borrow-repay", borrow_request)
```

### Python 还币
```python
async def repay_currency(ccy: str, amt: str):
    """归还币种"""
    repay_request = {
        "ccy": ccy,
        "amt": amt,
        "side": "repay"
    }
    return await client.post("/api/v5/account/borrow-repay", repay_request)
```

## 注意事项

1. **利息费用**：借币需要按日支付利息
2. **强制平仓**：风险过高时会自动平仓
3. **自动换币**：负债过高时可能触发自动换币
4. **杠杆风险**：杠杆越高，风险越大

## 相关文档

- [现货交易](./spot_trading.md)
- [合约全仓交易](./contract_cross_trading.md)
- [账户风险管理](../account_management/risk_management.md)
- [保证金管理](../account_management/margin_management.md)
