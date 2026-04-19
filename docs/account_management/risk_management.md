# 账户风险管理

## 概述

有效的风险管理是交易成功的关键。本文档介绍 OKX 交易中的风险管理机制和最佳实践。

## 风险指标

### 1. 保证金率 (Margin Ratio)

#### 定义
保证金率是衡量账户风险的核心指标，表示账户权益与仓位价值的比例。

#### 计算公式
```
保证金率 = (维持保证金 / 仓位价值) × 100%
```

#### 风险等级
| 等级 | 保证金率 | 状态 | 建议 |
|------|----------|------|------|
| 安全 | > 30% | 🟢 | 正常交易 |
| 警告 | 15% - 30% | 🟡 | 注意风险，准备追加保证金 |
| 危险 | < 15% | 🔴 | 立即追加保证金或减仓 |

#### API 获取
```http
GET /api/v5/account/balance
```

**响应字段：**
- `mgnRatio`: 保证金率

### 2. 未实现盈亏 (Unrealized PnL)

#### 定义
当前持仓的浮动盈亏，平仓后转为已实现盈亏。

#### API 获取
```http
GET /api/v5/account/balance
```

**响应字段：**
- `upl`: 未实现盈亏
- `isoUpl`: 逐仓未实现盈亏

### 3. 维持保证金率 (Maintenance Margin Ratio)

#### 定义
维持当前仓位所需的最低保证金率。

#### 特点
- 杠杆越高，维持保证金率越高
- 不同币种可能有不同要求

### 4. 爆仓风险

#### 触发条件
当保证金率低于维持保证金率时，触发强制平仓。

#### 爆仓流程
1. 保证金率触及维持保证金率
2. 系统发出爆仓预警
3. 强制平仓部分或全部仓位
4. 扣除爆仓费用

## 风险监控

### 实时监控

#### Python 监控脚本
```python
async def monitor_account_risk():
    """监控账户风险"""
    while True:
        balance = await client.get_account_balance()
        
        for item in balance.get('details', []):
            mgn_ratio = item.get('mgnRatio')
            upl = item.get('upl')
            
            if mgn_ratio:
                ratio = float(mgn_ratio)
                
                if ratio < 0.15:  # 15%
                    logger.error(f"🚨 爆仓风险！保证金率: {ratio:.2%}")
                    # 发送警报或自动减仓
                elif ratio < 0.30:  # 30%
                    logger.warning(f"⚠️ 风险警告！保证金率: {ratio:.2%}")
                else:
                    logger.info(f"✅ 保证金率正常: {ratio:.2%}")
        
        await asyncio.sleep(10)  # 每10秒检查一次
```

### 风险预警

#### 预警设置
```python
class RiskAlert:
    def __init__(self):
        self.alert_levels = {
            'danger': 0.15,    # 15%
            'warning': 0.30,   # 30%
            'safe': 0.50       # 50%
        }
    
    async def check_and_alert(self, mgn_ratio: float):
        """检查并发送警报"""
        if mgn_ratio < self.alert_levels['danger']:
            await self.send_alert('danger', f"保证金率过低: {mgn_ratio:.2%}")
        elif mgn_ratio < self.alert_levels['warning']:
            await self.send_alert('warning', f"保证金率警告: {mgn_ratio:.2%}")
```

## 风险控制策略

### 1. 仓位管理

#### 固定比例法
- 单笔交易不超过总资金的 5%
- 总仓位不超过总资金的 50%

#### 凯利公式
```
f = (bp - q) / b

其中：
f = 最优仓位比例
b = 赔率（平均盈利/平均亏损）
p = 胜率
q = 败率 = 1 - p
```

### 2. 止损策略

#### 固定金额止损
```python
async def set_stop_loss_fixed_amount(order_id: str, loss_amount: float):
    """设置固定金额止损"""
    order = await client.get_order(order_id)
    entry_price = float(order['avgPx'])
    size = float(order['sz'])
    
    # 计算止损价格
    stop_price = entry_price - (loss_amount / size)
    
    await client.post("/api/v5/trade/order-algo", {
        "instId": order['instId'],
        "posSide": order['posSide'],
        "slTriggerPx": str(stop_price),
        "slOrdPx": "-1"
    })
```

#### 百分比止损
```python
async def set_stop_loss_percentage(order_id: str, loss_percentage: float):
    """设置百分比止损"""
    order = await client.get_order(order_id)
    entry_price = float(order['avgPx'])
    
    # 计算止损价格
    stop_price = entry_price * (1 - loss_percentage)
    
    await client.post("/api/v5/trade/order-algo", {
        "instId": order['instId'],
        "posSide": order['posSide'],
        "slTriggerPx": str(stop_price),
        "slOrdPx": "-1"
    })
```

#### 移动止损
```python
async def set_trailing_stop(order_id: str, callback_rate: float):
    """设置移动止损"""
    await client.post("/api/v5/trade/order-algo", {
        "instId": order_id,
        "ordType": "move_order_stop",
        "callbackRate": str(callback_rate)
    })
```

### 3. 止盈策略

#### 固定止盈
```python
async def set_take_profit(order_id: str, profit_percentage: float):
    """设置固定止盈"""
    order = await client.get_order(order_id)
    entry_price = float(order['avgPx'])
    
    take_profit_price = entry_price * (1 + profit_percentage)
    
    await client.post("/api/v5/trade/order-algo", {
        "instId": order['instId'],
        "posSide": order['posSide'],
        "tpTriggerPx": str(take_profit_price),
        "tpOrdPx": "-1"
    })
```

#### 分批止盈
```python
async def set_partial_take_profits(order_id: str, levels: list):
    """设置分批止盈"""
    order = await client.get_order(order_id)
    
    for i, (percentage, size_ratio) in enumerate(levels):
        entry_price = float(order['avgPx'])
        tp_price = entry_price * (1 + percentage)
        
        await client.post("/api/v5/trade/order-algo", {
            "instId": order['instId'],
            "posSide": order['posSide'],
            "tpTriggerPx": str(tp_price),
            "tpOrdPx": "-1",
            "sz": str(float(order['sz']) * size_ratio)
        })
```

## 杠杆管理

### 杠杆选择

#### 建议杠杆倍数
| 经验水平 | 建议杠杆 | 说明 |
|----------|----------|------|
| 新手 | 1-3x | 低风险，学习为主 |
| 中级 | 3-5x | 适度风险，有一定经验 |
| 高级 | 5-10x | 较高风险，经验丰富 |
| 专业 | 10x+ | 极高风险，专业交易者 |

#### 动态杠杆调整
```python
async def adjust_leverage_based_on_volatility(inst_id: str):
    """根据波动率调整杠杆"""
    # 获取历史波动率
    volatility = await calculate_volatility(inst_id)
    
    if volatility > 0.05:  # 5% 日波动
        new_leverage = "3"
    elif volatility > 0.03:  # 3% 日波动
        new_leverage = "5"
    else:
        new_leverage = "10"
    
    await client.post("/api/v5/account/set-leverage", {
        "instId": inst_id,
        "lever": new_leverage,
        "mgnMode": "cross"
    })
```

## 应急处理

### 1. 自动减仓

#### 触发条件
- 保证金率低于危险线
- 手动触发

#### 减仓策略
```python
async def emergency_reduce_position(inst_id: str, target_ratio: float):
    """紧急减仓"""
    positions = await client.get_positions(instId=inst_id)
    
    for pos in positions:
        current_size = float(pos['pos'])
        reduce_size = current_size * target_ratio
        
        # 平仓部分仓位
        await client.post("/api/v5/trade/order", {
            "instId": inst_id,
            "tdMode": pos['mgnMode'],
            "side": "sell" if pos['posSide'] == "long" else "buy",
            "posSide": pos['posSide'],
            "ordType": "market",
            "sz": str(reduce_size)
        })
```

### 2. 追加保证金

```python
async def add_margin(ccy: str, amt: str):
    """追加保证金"""
    # 从资金账户转入交易账户
    await client.post("/api/v5/asset/transfer", {
        "ccy": ccy,
        "amt": amt,
        "from": "6",  # 资金账户
        "to": "18"    # 交易账户
    })
```

## 最佳实践

### 1. 交易前准备
- [ ] 确定风险承受能力
- [ ] 设置止损止盈
- [ ] 计算仓位大小
- [ ] 检查保证金率

### 2. 交易中监控
- [ ] 实时监控保证金率
- [ ] 关注市场波动
- [ ] 及时调整止损
- [ ] 记录交易日志

### 3. 交易后复盘
- [ ] 分析盈亏原因
- [ ] 评估风险控制效果
- [ ] 优化交易策略
- [ ] 更新风险参数

## 常见错误

### 1. 过度杠杆
- **问题**：使用过高杠杆导致爆仓
- **解决**：根据经验选择合适杠杆

### 2. 无止损交易
- **问题**：亏损不断扩大
- **解决**：每笔交易必须设置止损

### 3. 过度交易
- **问题**：频繁交易导致手续费过高
- **解决**：制定交易计划，避免冲动交易

### 4. 忽视风险指标
- **问题**：不监控保证金率
- **解决**：设置自动监控和预警

## 相关文档

- [保证金管理](./margin_management.md)
- [持仓管理](./position_management.md)
- [现货交易](../trading_modes/spot_trading.md)
- [合约交易](../trading_modes/contract_trading.md)

---

**警告**：交易有风险，入市需谨慎。请根据自身情况制定合适的风险管理策略。
