# OKX 交易模式文档

本文档将 OKX API 指南按交易模式进行拆分，便于理解和使用。

## 文档结构

### 交易模式文档 (`trading_modes/`)

| 文档 | 说明 | 适用场景 |
|------|------|----------|
| [现货交易](./trading_modes/spot_trading.md) | 基础币币交易，无杠杆 | 长期持有、简单交换 |
| [现货杠杆交易](./trading_modes/spot_margin_trading.md) | 币币杠杆，支持借贷 | 放大收益、做空 |
| [合约交易](./trading_modes/contract_trading.md) | 交割/永续合约 | 高杠杆、双向交易 |
| [期权交易](./trading_modes/options_trading.md) | 期权合约 | 复杂策略、对冲 |

### 账户管理文档 (`account_management/`)

| 文档 | 说明 |
|------|------|
| [账户风险管理](./account_management/risk_management.md) | 保证金率、强制平仓、风险监控 |
| [保证金管理](./account_management/margin_management.md) | 保证金计算、切换方式 |
| [持仓管理](./account_management/position_management.md) | 持仓查询、盈亏计算 |

## 交易模式对比

### 现货 vs 杠杆 vs 合约

| 特性 | 现货 | 现货杠杆 | 合约 |
|------|------|----------|------|
| 杠杆倍数 | 1x | 最高 5x | 最高 125x |
| 做空 | ❌ | ✅ | ✅ |
| 持有资产 | ✅ | ✅ | ❌ |
| 资金费率 | ❌ | ❌ | ✅ |
| 利息费用 | ❌ | ✅ | ❌ |
| 强制平仓 | ❌ | ✅ | ✅ |

### 全仓 vs 逐仓

| 特性 | 全仓 | 逐仓 |
|------|------|------|
| 保证金共享 | ✅ | ❌ |
| 风险分散 | ✅ | ❌ |
| 爆仓影响 | 全部仓位 | 单个仓位 |
| 资金利用率 | 高 | 低 |

## 快速开始

### 1. 选择交易模式

根据您的需求选择合适的交易模式：

- **新手**：从 [现货交易](./trading_modes/spot_trading.md) 开始
- **进阶**：尝试 [现货杠杆交易](./trading_modes/spot_margin_trading.md)
- **专业**：使用 [合约交易](./trading_modes/contract_trading.md)

### 2. 设置账户模式

在 OKX 网页或 App 上设置账户模式：

1. 现货模式：仅支持现货交易
2. 合约模式：仅支持合约交易
3. 跨币种保证金模式：支持现货和合约
4. 组合保证金模式：专业级账户

### 3. API 调用流程

```python
# 1. 初始化客户端
from core.api.okx_rest_client import OKXRESTClient
from core.config import OKXConfig

config = OKXConfig()
client = OKXRESTClient(config)

# 2. 获取账户余额
balance = await client.get_account_balance()

# 3. 执行交易（以现货买入为例）
order = {
    "instId": "BTC-USDT",
    "tdMode": "cash",  # 现货模式
    "side": "buy",
    "ordType": "market",
    "sz": "10",
    "tgtCcy": "quote_ccy"
}
result = await client.post("/api/v5/trade/order", order)
```

## 核心概念

### 交易模式 (`tdMode`)

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `cash` | 现货模式 | 币币交易 |
| `cross` | 全仓模式 | 杠杆/合约全仓 |
| `isolated` | 逐仓模式 | 杠杆/合约逐仓 |

### 产品类型 (`instType`)

| 类型 | 说明 | 示例 |
|------|------|------|
| `SPOT` | 现货 | BTC-USDT |
| `MARGIN` | 币币杠杆 | BTC-USDT |
| `SWAP` | 永续合约 | BTC-USDT-SWAP |
| `FUTURES` | 交割合约 | BTC-USDT-250628 |
| `OPTION` | 期权 | BTC-USDT-250628-80000-C |

### 订单方向 (`side` 和 `posSide`)

**现货/杠杆：**
- `side`: `buy` 或 `sell`

**合约：**
- `side`: `buy` 或 `sell`（开仓/平仓方向）
- `posSide`: `long` 或 `short`（持仓方向）

## 风险管理

### 关键指标

1. **保证金率** (`mgnRatio`)
   - 衡量账户风险的核心指标
   - 低于维持保证金率会触发强制平仓

2. **未实现盈亏** (`upl`)
   - 当前持仓的浮动盈亏
   - 平仓后转为已实现盈亏

3. **资金费率** (`fundingRate`)
   - 永续合约特有
   - 每 8 小时结算一次

### 风险控制建议

1. **合理使用杠杆**
   - 新手建议不超过 3 倍
   - 根据风险承受能力调整

2. **设置止损**
   - 单笔交易亏损不超过本金的 2%
   - 使用止损订单自动执行

3. **分散投资**
   - 不要将所有资金投入单一交易
   - 使用多个交易对分散风险

## 常见问题

### Q: 如何选择交易模式？

A: 根据您的交易经验和风险偏好：
- 新手：现货交易
- 有经验的交易者：现货杠杆
- 专业交易者：合约交易

### Q: 全仓和逐仓哪个更好？

A: 取决于您的策略：
- 全仓：资金利用率高，风险分散
- 逐仓：风险隔离，适合高风险策略

### Q: 如何避免强制平仓？

A: 
1. 保持足够的保证金
2. 合理使用杠杆
3. 及时追加保证金或减仓
4. 设置止损

## 相关资源

- [OKX API 官方文档](https://www.okx.com/docs-v5/)
- [OKX 交易指南](https://www.okx.com/help/trading-guide)
- [风险管理最佳实践](./account_management/risk_management.md)

## 更新日志

### 2026-04-10
- 创建交易模式文档结构
- 添加现货、现货杠杆、合约交易文档
- 创建 README 导航文档

---

**注意**：交易有风险，入市需谨慎。本文档仅供参考，不构成投资建议。
