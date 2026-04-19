# OKX 期权交易模式

## 概述

期权交易是一种衍生品交易，赋予持有者在未来特定时间以特定价格买入或卖出标的资产的权利。

### 特点
- **权利而非义务**：买方有权但无义务执行合约
- **杠杆效应**：小额资金控制大额资产
- **策略多样**：支持多种复杂策略组合
- **风险有限**：买方最大损失为权利金

## 期权基础

### 期权类型

#### 看涨期权 (Call Option)
- 赋予持有者以执行价**买入**标的资产的权利
- 预期价格上涨时购买
- 收益理论上无限

#### 看跌期权 (Put Option)
- 赋予持有者以执行价**卖出**标的资产的权利
- 预期价格下跌时购买
- 收益最高为执行价减去权利金

### 期权要素

| 要素 | 说明 | 示例 |
|------|------|------|
| 标的资产 | 期权对应的资产 | BTC、ETH |
| 执行价 | 约定的买卖价格 | 80000 USD |
| 到期日 | 期权失效日期 | 2025-06-28 |
| 权利金 | 购买期权的费用 | 500 USD |
| 合约乘数 | 每张合约代表的资产数量 | 0.01 BTC |

## 账户模式

### 组合保证金模式 (Portfolio Margin)
- 专业级账户模式
- 基于风险组合的保证金计算
- 支持复杂的期权策略

### 期权交易权限
- 需要开通期权交易权限
- 通过风险测评
- 满足资金要求

## API 接口

### 账户相关

#### 获取期权账户信息
```http
GET /api/v5/account/balance
```

**响应字段（期权模式特有）：**
- `greeks`: 希腊字母风险指标
  - `delta`: 价格敏感度
  - `gamma`: Delta变化率
  - `theta`: 时间衰减
  - `vega`: 波动率敏感度

#### 获取 Greeks 信息
```http
GET /api/v5/account/greeks
```

**请求参数：**
- `ccy`: 币种，如 "BTC"

### 交易相关

#### 期权下单
```http
POST /api/v5/trade/order
```

**请求参数：**
- `instId`: 产品ID，如 "BTC-USDT-250628-80000-C"
  - 格式：`标的-结算币-到期日-执行价-期权类型`
  - C: 看涨期权 (Call)
  - P: 看跌期权 (Put)
- `tdMode`: 交易模式
- `side`: 订单方向
- `ordType`: 订单类型
- `sz`: 委托数量（张数）

**示例（买入看涨期权）：**
```json
{
  "instId": "BTC-USDT-250628-80000-C",
  "tdMode": "cross",
  "side": "buy",
  "ordType": "limit",
  "sz": "1",
  "px": "500"
}
```

### 期权查询

#### 获取期权行情
```http
GET /api/v5/market/ticker
```

**请求参数：**
- `instId`: 期权产品ID

#### 获取期权链
```http
GET /api/v5/market/option-instrument-family
```

**请求参数：**
- `instFamily`: 期权品种，如 "BTC-USDT"

## 交易规则

### 合约规格
- **标的资产**：BTC、ETH 等
- **合约乘数**：0.01 BTC/张 或 0.1 ETH/张
- **最小交易单位**：1 张
- **到期日**：每周、每月、每季度

### 行权方式
- **欧式期权**：仅能在到期日行权
- **自动行权**：价内期权自动行权
- **现金结算**：按差价结算，不涉及实物交割

### 保证金要求

#### 买方
- 支付权利金
- 无需额外保证金
- 最大损失 = 权利金

#### 卖方
- 收取权利金
- 需要缴纳保证金
- 风险可能无限（看涨）或很大（看跌）

## 期权策略

### 基础策略

#### 1. 买入看涨 (Long Call)
- **适用场景**：强烈看涨
- **最大收益**：无限
- **最大损失**：权利金
- **盈亏平衡点**：执行价 + 权利金

#### 2. 买入看跌 (Long Put)
- **适用场景**：强烈看跌
- **最大收益**：执行价 - 权利金
- **最大损失**：权利金
- **盈亏平衡点**：执行价 - 权利金

#### 3. 卖出看涨 (Short Call)
- **适用场景**：看跌或横盘
- **最大收益**：权利金
- **最大损失**：无限
- **风险等级**：高风险

#### 4. 卖出看跌 (Short Put)
- **适用场景**：看涨或横盘
- **最大收益**：权利金
- **最大损失**：执行价 - 权利金
- **风险等级**：中等风险

### 组合策略

#### 1. 跨式组合 (Straddle)
- **构建**：同时买入相同执行价的看涨和看跌
- **适用场景**：预期大波动，方向不确定
- **特点**：双向获利，成本较高

#### 2. 宽跨式组合 (Strangle)
- **构建**：买入不同执行价的看涨和看跌
- **适用场景**：预期大波动，降低成本
- **特点**：需要更大波动才能盈利

#### 3. 价差组合 (Spread)
- **牛市价差**：买入低执行价看涨 + 卖出高执行价看涨
- **熊市价差**：买入高执行价看跌 + 卖出低执行价看跌
- **特点**：限制风险和收益，降低成本

#### 4. 蝶式组合 (Butterfly)
- **构建**：三个不同执行价的期权组合
- **适用场景**：预期价格稳定
- **特点**：风险有限，收益有限

## 代码示例

### Python 买入看涨期权
```python
async def buy_call_option(inst_id: str, price: str, size: str):
    """买入看涨期权"""
    order = {
        "instId": inst_id,  # 如 "BTC-USDT-250628-80000-C"
        "tdMode": "cross",
        "side": "buy",
        "ordType": "limit",
        "sz": size,
        "px": price
    }
    return await client.post("/api/v5/trade/order", order)
```

### Python 获取 Greeks
```python
async def get_greeks(ccy: str = "BTC"):
    """获取 Greeks 信息"""
    params = {"ccy": ccy}
    return await client.get("/api/v5/account/greeks", params)
```

### Python 监控 Greeks
```python
async def monitor_greeks():
    """监控 Greeks 风险"""
    greeks = await get_greeks("BTC")
    
    delta = float(greeks.get('delta', 0))
    gamma = float(greeks.get('gamma', 0))
    theta = float(greeks.get('theta', 0))
    vega = float(greeks.get('vega', 0))
    
    print(f"Delta: {delta} (价格敏感度)")
    print(f"Gamma: {gamma} (Delta变化率)")
    print(f"Theta: {theta} (时间衰减)")
    print(f"Vega: {vega} (波动率敏感度)")
    
    # 风险预警
    if abs(delta) > 1000:
        logger.warning(f"Delta风险过高: {delta}")
```

## 风险管理

### Greeks 风险管理

#### Delta 对冲
- **目标**：保持 Delta 中性
- **方法**：通过现货或期货对冲
- **频率**：根据 Gamma 调整频率

#### Gamma 风险
- **特点**：Delta 的变化率
- **风险**：价格大幅波动时风险增加
- **管理**：定期调整对冲仓位

#### Theta 损耗
- **特点**：时间价值衰减
- **影响**：买方每天损失时间价值
- **策略**：卖方赚取 Theta，买方需快速获利

#### Vega 风险
- **特点**：波动率敏感度
- **风险**：波动率变化影响期权价格
- **管理**：监控市场波动率变化

### 仓位管理

1. **权利金管理**
   - 单笔交易不超过总资金的 5%
   - 避免过度集中

2. **到期管理**
   - 关注到期日
   - 提前处理即将到期的期权

3. **行权管理**
   - 了解自动行权规则
   - 及时行使价内期权

## 注意事项

1. **复杂性**：期权比现货和合约更复杂
2. **时间衰减**：期权价值随时间减少
3. **波动率影响**：隐含波动率影响期权价格
4. **流动性**：部分期权流动性较差
5. **卖方风险**：卖方风险可能无限

## 相关文档

- [现货交易](./spot_trading.md)
- [合约交易](./contract_trading.md)
- [账户风险管理](../account_management/risk_management.md)
- [Greeks 风险管理](../account_management/greeks_management.md)

---

**警告**：期权交易风险极高，可能导致本金全部损失。建议充分学习后再进行交易。
