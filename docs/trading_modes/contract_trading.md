# OKX 合约交易模式

## 概述

合约交易允许用户交易加密货币的衍生品，包括交割合约和永续合约。

### 特点
- **杠杆交易**：支持高杠杆（最高125倍）
- **双向交易**：支持做多和做空
- **无需持有标的资产**：交易的是合约而非实际资产
- **资金费率**：永续合约需要支付或收取资金费

## 账户模式

### 合约模式 (Futures Mode)
- 仅支持合约交易
- 不支持现货交易
- 支持交割合约和永续合约

### 跨币种保证金模式 (Multi-currency Margin)
- 支持现货和合约交易
- 多种币种可作为保证金
- 自动换币功能

### 组合保证金模式 (Portfolio Margin)
- 专业级账户模式
- 基于风险组合的保证金计算
- 支持更复杂的策略

## 合约类型

### 交割合约 (Futures)
- **定期交割**：每周、每月、每季度交割
- **到期结算**：到期时按结算价平仓
- **无资金费率**

### 永续合约 (Perpetual Swap)
- **无到期日**：可长期持有
- **资金费率**：每8小时结算一次
- **锚定现货价格**：通过资金费率机制

## API 接口

### 账户相关

#### 获取合约账户信息
```http
GET /api/v5/account/balance
```

**响应字段（合约模式特有）：**
- `upl`: 未实现盈亏
- `isoUpl`: 逐仓未实现盈亏
- `imr`: 初始保证金要求
- `mmr`: 维持保证金要求
- `availEq`: 可用保证金
- `mgnRatio`: 保证金率
- `notionalLever`: 币种杠杆倍数

### 交易相关

#### 合约下单
```http
POST /api/v5/trade/order
```

**请求参数：**
- `instId`: 产品ID，如 "BTC-USDT-SWAP"（永续）或 "BTC-USDT-250628"（交割）
- `tdMode`: 交易模式，"cross"（全仓）或 "isolated"（逐仓）
- `side`: 订单方向
- `posSide`: 持仓方向，"long"（做多）或 "short"（做空）
- `ordType`: 订单类型
- `sz`: 委托数量（张数）
- `px`: 委托价格（限价单）

**示例（永续合约全仓做多）：**
```json
{
  "instId": "BTC-USDT-SWAP",
  "tdMode": "cross",
  "side": "buy",
  "posSide": "long",
  "ordType": "market",
  "sz": "1"
}
```

**示例（永续合约逐仓做空）：**
```json
{
  "instId": "BTC-USDT-SWAP",
  "tdMode": "isolated",
  "side": "sell",
  "posSide": "short",
  "ordType": "market",
  "sz": "1"
}
```

### 持仓管理

#### 获取持仓信息
```http
GET /api/v5/account/positions
```

**请求参数：**
- `instType`: 产品类型，"SWAP"（永续）或 "FUTURES"（交割）
- `instId`: 产品ID（可选）

#### 设置杠杆倍数
```http
POST /api/v5/account/set-leverage
```

**全仓模式（合约层面）：**
```json
{
  "instId": "BTC-USDT-SWAP",
  "lever": "10",
  "mgnMode": "cross"
}
```

**逐仓模式（买卖持仓模式）：**
```json
{
  "instId": "BTC-USDT-SWAP",
  "posSide": "long",
  "lever": "10",
  "mgnMode": "isolated"
}
```

**逐仓模式（开平仓持仓模式）：**
```json
{
  "instId": "BTC-USDT-SWAP",
  "posSide": "long",
  "lever": "10",
  "mgnMode": "isolated"
}
```

### 资金费率

#### 获取资金费率
```http
GET /api/v5/public/funding-rate
```

**请求参数：**
- `instId`: 产品ID，如 "BTC-USDT-SWAP"

#### 获取资金费率历史
```http
GET /api/v5/public/funding-rate-history
```

## 交易规则

### 合约面值
- BTC：100 USD/张
- ETH：10 USD/张
- 其他币种根据具体规则

### 杠杆倍数
- 全仓：最高 125 倍（根据币种不同）
- 逐仓：最高 125 倍

### 保证金率
```
保证金率 = (维持保证金 / 仓位价值) × 100%
```

### 强制平仓
当保证金率低于维持保证金率时触发。

## 费用

### 交易手续费
- Maker: 0.02% - 0.05%
- Taker: 0.05% - 0.08%

### 资金费率
- 每 8 小时结算一次（0:00、8:00、16:00 UTC+8）
- 正资金费：多头支付空头
- 负资金费：空头支付多头

## 代码示例

### Python 永续合约做多（全仓）
```python
async def swap_long_cross(inst_id: str, sz: str, leverage: str = "10"):
    """永续合约全仓做多"""
    # 1. 设置杠杆倍数
    await client.post("/api/v5/account/set-leverage", {
        "instId": inst_id,
        "lever": leverage,
        "mgnMode": "cross"
    })
    
    # 2. 下单
    order = {
        "instId": inst_id,
        "tdMode": "cross",
        "side": "buy",
        "posSide": "long",
        "ordType": "market",
        "sz": sz
    }
    return await client.post("/api/v5/trade/order", order)
```

### Python 永续合约做空（逐仓）
```python
async def swap_short_isolated(inst_id: str, sz: str, leverage: str = "10"):
    """永续合约逐仓做空"""
    # 1. 设置杠杆倍数
    await client.post("/api/v5/account/set-leverage", {
        "instId": inst_id,
        "lever": leverage,
        "mgnMode": "isolated"
    })
    
    # 2. 下单
    order = {
        "instId": inst_id,
        "tdMode": "isolated",
        "side": "sell",
        "posSide": "short",
        "ordType": "market",
        "sz": sz
    }
    return await client.post("/api/v5/trade/order", order)
```

### Python 获取持仓
```python
async def get_positions(inst_type: str = "SWAP"):
    """获取持仓信息"""
    params = {"instType": inst_type}
    return await client.get("/api/v5/account/positions", params)
```

### Python 平仓
```python
async def close_position(inst_id: str, pos_side: str, mgn_mode: str):
    """平仓"""
    order = {
        "instId": inst_id,
        "tdMode": mgn_mode,
        "side": "sell" if pos_side == "long" else "buy",
        "posSide": pos_side,
        "ordType": "market",
        "sz": "0"  # 0 表示全部平仓
    }
    return await client.post("/api/v5/trade/order", order)
```

## 风险管理

### 保证金率监控
```python
async def monitor_margin_ratio():
    """监控保证金率"""
    balance = await client.get("/api/v5/account/balance")
    for item in balance.get('details', []):
        mgn_ratio = item.get('mgnRatio')
        if mgn_ratio:
            ratio = float(mgn_ratio)
            if ratio < 0.1:  # 10%
                logger.warning(f"保证金率过低: {ratio}")
```

### 止损设置
```python
async def set_stop_loss(inst_id: str, pos_side: str, sl_price: str):
    """设置止损"""
    order = {
        "instId": inst_id,
        "posSide": pos_side,
        "tpTriggerPx": "",  # 止盈触发价
        "tpOrdPx": "",      # 止盈委托价
        "slTriggerPx": sl_price,  # 止损触发价
        "slOrdPx": "-1"     # -1 表示市价止损
    }
    return await client.post("/api/v5/trade/order-algo", order)
```

## 注意事项

1. **高杠杆风险**：合约交易风险极高，请谨慎使用杠杆
2. **资金费率**：永续合约持仓需要关注资金费率
3. **强制平仓**：保证金不足时会自动平仓
4. **交割日期**：交割合约注意到期时间

## 相关文档

- [现货交易](./spot_trading.md)
- [现货杠杆交易](./spot_margin_trading.md)
- [期权交易](./options_trading.md)
- [账户风险管理](../account_management/risk_management.md)
