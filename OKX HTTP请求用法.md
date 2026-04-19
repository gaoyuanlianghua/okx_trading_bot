# OKX HTTP 请求用法

## REST 请求验证

### 发起请求
所有 REST 私有请求头都必须包含以下内容：

- **OK-ACCESS-KEY**：字符串类型的 API Key。
- **OK-ACCESS-SIGN**：使用 HMAC SHA256 哈希函数获得哈希值，再使用 Base-64 编码。
- **OK-ACCESS-TIMESTAMP**：发起请求的时间（UTC），如：2020-12-08T09:08:57.715Z
- **OK-ACCESS-PASSPHRASE**：您在创建 API 密钥时指定的 Passphrase。

所有请求都应该含有 `application/json` 类型内容，并且是有效的 JSON。

### 签名
生成签名：

OK-ACCESS-SIGN 的请求头是对 `timestamp + method + requestPath + body` 字符串（+ 表示字符串连接），以及 SecretKey，使用 HMAC SHA256 方法加密，通过 Base-64 编码输出而得到的。

例如：
```
sign=CryptoJS.enc.Base64.stringify(CryptoJS.HmacSHA256(timestamp + 'GET' + '/api/v5/account/balance?ccy=BTC', SecretKey))
```

其中：
- `timestamp` 的值与 OK-ACCESS-TIMESTAMP 请求头相同，为 ISO 格式，如 2020-12-08T09:08:57.715Z。
- `method` 是请求方法，字母全部大写：GET/POST。
- `requestPath` 是请求接口路径。如：/api/v5/account/balance
- `body` 是指请求主体的字符串，如果请求没有主体（通常为 GET 请求）则 body 可省略。如：`{"instId":"BTC-USDT","lever":"5","mgnMode":"isolated"}`
- GET 请求参数是算作 requestPath，不算 body
- SecretKey 为用户申请 API Key 时所生成。

## 请求头示例

```
Content-Type: application/json

OK-ACCESS-KEY: 37c541a1-****-****-****-10fe7a038418

OK-ACCESS-SIGN: leaVRETrtaoEQ3yI9qEtI1CZ82ikZ4xSG5Kj8gnl3uw=

OK-ACCESS-PASSPHRASE: 1****6

OK-ACCESS-TIMESTAMP: 2020-03-28T12:21:41.274Z

x-simulated-trading: 1  // 仅模拟盘需要
```

## 实盘与模拟盘 API 地址

### 实盘交易
- REST：https://www.okx.com
- WebSocket 公共频道：wss://ws.okx.com:8443/ws/v5/public
- WebSocket 私有频道：wss://ws.okx.com:8443/ws/v5/private
- WebSocket 业务频道：wss://ws.okx.com:8443/ws/v5/business

### 模拟盘交易
- REST：https://www.okx.com
- WebSocket 公共频道：wss://wspap.okx.com:8443/ws/v5/public
- WebSocket 私有频道：wss://wspap.okx.com:8443/ws/v5/private
- WebSocket 业务频道：wss://wspap.okx.com:8443/ws/v5/business

**注意：模拟盘的请求的 header 里面需要添加 "x-simulated-trading: 1"。**

## 交易时效性

由于网络延时或者 OKX 服务器繁忙会导致订单无法及时处理。如果您对交易时效性有较高的要求，可以灵活设置请求有效截止时间 `expTime` 以达到你的要求。

（批量）下单，（批量）改单接口请求中如果包含 `expTime`，如果服务器当前系统时间超过 `expTime`，则该请求不会被服务器处理。

### REST API
请求头中设置如下参数：

| 参数名 | 类型 | 是否必须 | 描述 |
|--------|------|----------|------|
| expTime | String | 否 | 请求有效截止时间。Unix 时间戳的毫秒数格式，如 1597026383085 |

目前支持如下接口：
- 下单
- 批量下单
- 修改订单
- 批量修改订单
- 信号交易的 POST / 下单

### 请求示例

```bash
curl -X 'POST' \
  'https://www.okx.com/api/v5/trade/order' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'OK-ACCESS-KEY: *****' \
  -H 'OK-ACCESS-SIGN: *****'' \
  -H 'OK-ACCESS-TIMESTAMP: *****'' \
  -H 'OK-ACCESS-PASSPHRASE: *****'' \
  -H 'expTime: 1597026383085' \
  -d '{
  "instId": "BTC-USDT",
  "tdMode": "cash",
  "side": "buy",
  "ordType": "limit",
  "px": "1000",
  "sz": "0.01"
}'
```

## 限速

OKX 的 REST 和 WebSocket API 使用限速来保护 API 免受恶意使用，因此交易平台可以可靠和公平地运行。

当请求因限速而被系统拒绝时，系统会返回错误代码 50011（用户请求频率过快，超过该接口允许的限额。请参考 API 文档并限制请求）。

### 限速规则

- WebSocket 登录和订阅限速基于连接。
- 公共未经身份验证的 REST 限速基于 IP 地址。
- 私有 REST 限速基于 User ID（子帐户具有单独的 User ID）。
- WebSocket 订单管理限速基于 User ID（子账户具有单独的 User ID）。

### 交易相关 API

对于与交易相关的 API（下订单、取消订单和修改订单），以下条件适用：

- 限速在 REST 和 WebSocket 通道之间共享。
- 下单、修改订单、取消订单的限速相互独立。
- 限速在 Instrument ID 级别定义（期权除外）
- 期权的限速是根据 Instrument Family 级别定义的。
- 批量订单接口和单订单接口的限速也是独立的，除了只有一个订单发送到批量订单接口时，该订单将被视为一个订单并采用单订单限速。

### 子账户限速

子账户维度，每 2 秒最多允许 1000 个订单相关请求。仅有新订单及修改订单请求会被计入此限制。此限制涵盖以下所列的所有接口。对于包含多个订单的批量请求，每个订单将被单独计数。如果请求频率超过限制，系统会返回 50061 错误码。

涵盖接口：
- POST / 下单
- POST / 批量下单
- POST / 修改订单
- POST / 批量修改订单
- WS / 下单
- WS / 批量下单
- WS / 改单
- WS / 批量改单

## 常用 API 接口

### 获取交易产品基础信息

- 限速：20 次/2s
- 限速规则：User ID + Instrument Type
- 权限：读取
- HTTP 请求：GET /api/v5/account/instruments

### 查看账户余额

- 限速：10 次/2s
- 限速规则：User ID
- 权限：读取
- HTTP 请求：GET /api/v5/account/balance

### 查看持仓信息

- 限速：10 次/2s
- 限速规则：User ID
- 权限：读取
- HTTP 请求：GET /api/v5/account/positions

### 查看账户持仓风险

- 限速：10 次/2s
- 限速规则：User ID
- 权限：读取
- HTTP 请求：GET /api/v5/account/account-position-risk

### 账单流水查询（近七天）

- 限速：5 次/s
- 限速规则：User ID
- 权限：读取
- HTTP 请求：GET /api/v5/account/bills

## 最佳实践

1. **限速控制**：如果需要的请求速率高于 OKX 的限速，可以设置不同的子账户来批量请求限速。建议使用此方法来限制或间隔请求，以最大化每个帐户的限速并避免断开连接或拒绝请求。

2. **签名生成**：确保正确生成签名，特别是对于包含请求体的 POST 请求。

3. **时间戳同步**：请求在时间戳之后 30 秒会失效，如果服务器时间和 API 服务器时间有偏差，推荐使用 REST API 查询 API 服务器的时间，然后设置时间戳。

4. **错误处理**：妥善处理 API 返回的错误码，特别是限速错误和认证错误。

5. **请求时效性**：对于对交易时效性有较高要求的场景，设置合理的 `expTime` 参数。

6. **网络连接**：确保网络连接稳定，避免因网络问题导致请求失败。

7. **API 密钥安全**：妥善保管 API 密钥，避免泄露。

8. **模拟盘测试**：在实盘交易前，使用模拟盘进行充分测试，确保交易逻辑正确。