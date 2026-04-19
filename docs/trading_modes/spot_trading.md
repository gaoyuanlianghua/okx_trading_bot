# OKX 现货交易模式

## 概述

现货交易是最基础的交易模式，用户直接使用一种资产交换另一种资产，不涉及杠杆和借贷。

### 特点
- **无杠杆**：1:1 资金交易
- **无负债**：不会产生借贷
- **即时交割**：交易立即完成
- **简单透明**：资产和资金一一对应

## 账户模式

### 现货模式 (Spot Mode)
- 仅支持币币交易
- 不能进行合约交易
- 可开通借币功能（转为现货杠杆）

### 适用场景
- 长期持有加密货币
- 简单的资产交换
- 低风险交易需求

## API 接口

### 账户相关

#### 获取账户余额
```http
GET /api/v5/account/balance
```

**适用参数：**
- `ccy`: 币种（可选，为空返回所有币种）

**响应字段（现货模式特有）：**
- `availBal`: 可用余额
- `cashBal`: 现金余额
- `eq`: 币种总权益
- `spotBal`: 现货余额
- `openAvgPx`: 现货开仓成本价
- `accAvgPx`: 现货累计成本价
- `spotUpl`: 现货未实现收益
- `totalPnl`: 现货累计收益

### 交易相关

#### 币币下单
```http
POST /api/v5/trade/order
```

**请求参数：**
- `instId`: 产品ID，如 "BTC-USDT"
- `tdMode`: 交易模式，现货为 "cash"
- `side`: 订单方向，"buy" 或 "sell"
- `ordType`: 订单类型，"market" 或 "limit"
- `sz`: 委托数量
- `px`: 委托价格（限价单必填）

**示例：**
```json
{
  "instId": "BTC-USDT",
  "tdMode": "cash",
  "side": "buy",
  "ordType": "market",
  "sz": "10",
  "tgtCcy": "quote_ccy"
}
```

#### 币币批量下单
```http
POST /api/v5/trade/batch-orders
```

### 订单管理

#### 查询订单
```http
GET /api/v5/trade/order
```

#### 查询订单历史
```http
GET /api/v5/trade/orders-history
```

#### 撤销订单
```http
POST /api/v5/trade/cancel-order
```

## 交易规则

### 最小交易单位
- BTC: 0.00001 BTC
- ETH: 0.0001 ETH
- 其他币种根据具体规则

### 最小订单金额
- 币币交易：1 USDT 等值

### 价格精度
- 根据交易对不同，通常为 0.01 或 0.001

## 费用

### 交易手续费
- Maker: 0.08%
- Taker: 0.1%

### 计算公式
```
手续费 = 成交数量 × 手续费率
```

## 代码示例

### Python 现货买入
```python
async def spot_buy(inst_id: str, usdt_amount: str):
    """现货买入"""
    order = {
        "instId": inst_id,
        "tdMode": "cash",  # 现货模式
        "side": "buy",
        "ordType": "market",
        "sz": usdt_amount,
        "tgtCcy": "quote_ccy"  # 按USDT金额下单
    }
    return await client.post("/api/v5/trade/order", order)
```

### Python 现货卖出
```python
async def spot_sell(inst_id: str, btc_amount: str):
    """现货卖出"""
    order = {
        "instId": inst_id,
        "tdMode": "cash",  # 现货模式
        "side": "sell",
        "ordType": "market",
        "sz": btc_amount,
        "tgtCcy": "base_ccy"  # 按BTC数量下单
    }
    return await client.post("/api/v5/trade/order", order)
```

## 注意事项

1. **资金划转**：交易前确保资金在交易账户
2. **最小金额**：订单金额不能小于 1 USDT
3. **价格限制**：市价单按当前市场价格成交
4. **手续费**：从成交资产中扣除

## 相关文档

- [现货杠杆交易](./spot_margin_trading.md)
- [合约全仓交易](./contract_cross_trading.md)
- [账户风险管理](../account_management/risk_management.md)
