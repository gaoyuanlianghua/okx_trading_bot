# 部署方案

## 1. 环境准备

### 1.1 系统要求

- **操作系统**：Windows 10/11、macOS、Linux
- **Python 版本**：3.7 或更高版本
- **内存**：至少 2GB RAM
- **磁盘空间**：至少 100MB 可用空间
- **网络**：稳定的网络连接，支持 WebSocket 连接

### 1.2 依赖项

| 依赖项 | 版本 | 用途 |
|-------|------|------|
| PyQt5 | >=5.15.0 | GUI 界面 |
| cryptography | >=3.4.0 | API 密钥加密 |
| matplotlib | >=3.5.0 | 图表绘制 |
| pandas | >=1.3.0 | 数据处理 |
| psutil | >=5.8.0 | 系统资源监控 |
| openpyxl | >=3.0.0 | Excel 导出 |
| aiohttp | >=3.8.0 | 异步 HTTP 请求 |
| websockets | >=10.0.0 | WebSocket 通信 |
| asyncio | 内置 | 异步编程支持 |

## 2. 部署步骤

### 2.1 克隆代码库

```bash
# 克隆代码库
git clone <repository-url>
cd okx_trading_bot
```

### 2.2 安装依赖

#### 使用 pip 安装

```bash
# 安装依赖
pip install -r requirements.txt
```

#### 手动安装

```bash
# 手动安装依赖
pip install PyQt5 cryptography matplotlib pandas psutil openpyxl
```

### 2.3 配置 API 密钥

1. 在 OKX 官网申请 API 密钥
2. 启动应用程序
3. 在连接管理部分输入 API Key、Secret 和 Passphrase
4. 选择交易环境（模拟盘或实盘）
5. 点击"连接"按钮连接 WebSocket

### 2.4 运行应用程序

#### 直接运行

```bash
# 直接运行应用程序
python websocket_gui.py
```

#### 运行定时任务

```bash
# 运行定时任务脚本
python scripts/schedule_api_logs.py
```

#### 创建快捷方式

**Windows**：
1. 右键点击 `websocket_gui.py` 文件
2. 选择"创建快捷方式"
3. 将快捷方式拖到桌面或开始菜单

**macOS**：
1. 创建一个启动脚本 `start_app.sh`
2. 内容如下：
   ```bash
   #!/bin/bash
   cd /path/to/okx_trading_bot
   python websocket_gui.py
   ```
3. 赋予执行权限：`chmod +x start_app.sh`
4. 创建快捷方式到桌面

## 3. 配置文件

### 3.1 加密密钥

首次启动时，应用程序会自动生成加密密钥并保存在 `encryption_key.key` 文件中。请妥善保管此文件，不要分享给他人。

### 3.2 API 密钥存储

API 密钥会被加密存储在 `api_keys.json` 文件中。此文件包含加密后的 API 密钥信息，只有使用正确的加密密钥才能解密。

### 3.3 数据缓存

应用程序会缓存市场数据和订单历史，存储在本地文件中，以提高启动速度和响应速度。

## 4. 服务管理

### 4.1 启动服务

```bash
# 启动应用程序
python websocket_gui.py

# 启动定时任务脚本
python scripts/schedule_api_logs.py
```

### 4.2 停止服务

- 点击应用程序窗口右上角的关闭按钮
- 或使用 Ctrl+C 终止命令行进程

### 4.3 自动启动

#### Windows 自启动

1. 按下 Win+R 键打开运行对话框
2. 输入 `shell:startup` 并按回车
3. 将应用程序快捷方式复制到启动文件夹

#### macOS 自启动

1. 打开 "系统偏好设置"
2. 点击 "用户与群组"
3. 选择 "登录项"
4. 点击 "+" 按钮添加应用程序启动脚本

## 5. 监控与维护

### 5.1 日志监控

应用程序会生成日志文件，记录运行状态和错误信息。可以通过查看日志文件了解应用程序的运行情况。

### 5.2 性能监控

使用 `performance_test.py` 脚本可以定期测试应用程序的性能：

```bash
# 运行性能测试
python performance_test.py
```

### 5.3 常见问题排查

| 问题 | 可能原因 | 解决方案 |
|------|---------|----------|
| 启动失败 | 依赖项缺失 | 重新安装依赖 |
| 连接失败 | API 密钥错误 | 检查 API 密钥是否正确 |
| 内存占用高 | 运行策略过多 | 减少运行策略数量 |
| 响应缓慢 | 系统资源不足 | 关闭其他占用资源的应用 |

## 6. 多环境部署

### 6.1 开发环境

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 运行开发版本
python websocket_gui.py
```

### 6.2 测试环境

```bash
# 运行测试
python -m pytest

# 运行性能测试
python performance_test.py
```

### 6.3 生产环境

```bash
# 安装生产依赖
pip install -r requirements.txt

# 运行生产版本
python websocket_gui.py
```

## 7. 容器化部署

### 7.1 Docker 部署

#### Dockerfile

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "websocket_gui.py"]
```

#### 构建和运行

```bash
# 构建镜像
docker build -t okx-trading-bot .

# 运行容器
docker run -it --name okx-bot okx-trading-bot
```

### 7.2 注意事项

- 容器化部署需要考虑 GUI 显示问题，可能需要使用 X11 转发或其他方案
- 加密密钥文件需要通过卷挂载或环境变量传递
- API 密钥需要在首次运行时配置

## 8. 升级与更新

### 8.1 代码更新

```bash
# 拉取最新代码
git pull

# 安装新依赖
pip install -r requirements.txt

# 重新启动应用程序
python websocket_gui.py
```

### 8.2 依赖更新

```bash
# 更新所有依赖
pip install --upgrade -r requirements.txt

# 或更新单个依赖
pip install --upgrade PyQt5 cryptography matplotlib pandas
```

### 8.3 配置迁移

- 加密密钥文件和 API 密钥文件会在升级后继续使用
- 数据缓存文件会在升级后继续使用
- 策略文件会在升级后继续使用

## 9. 安全考虑

### 9.1 密钥管理

- 加密密钥文件 `encryption_key.key` 应妥善保管
- API 密钥应定期更新
- 不要在代码中硬编码 API 密钥
- 不要将加密密钥文件提交到版本控制系统

### 9.2 网络安全

- 使用 HTTPS 连接
- 定期检查网络连接状态
- 避免在公共网络上使用应用程序
- 启用防火墙保护

### 9.3 系统安全

- 定期更新操作系统和依赖项
- 使用防病毒软件
- 限制应用程序的系统权限
- 定期备份重要数据

## 10. 故障恢复

### 10.1 数据备份

- 定期备份 `encryption_key.key` 文件
- 定期备份 `api_keys.json` 文件
- 定期备份策略文件

### 10.2 恢复流程

1. 安装应用程序
2. 恢复备份的 `encryption_key.key` 文件
3. 恢复备份的 `api_keys.json` 文件
4. 恢复备份的策略文件
5. 启动应用程序

### 10.3 应急方案

- 保存 API 密钥的安全备份
- 保存加密密钥的安全备份
- 定期导出策略和交易数据
- 建立紧急联系渠道

## 11. 部署检查清单

### 预部署检查
- [ ] 系统环境符合要求
- [ ] 依赖项已正确安装
- [ ] API 密钥已申请并配置
- [ ] 加密密钥已安全存储

### 部署后检查
- [ ] 应用程序能正常启动
- [ ] WebSocket 连接正常
- [ ] 市场数据能正常获取
- [ ] 策略能正常运行
- [ ] 数据导出功能正常
- [ ] 系统资源使用合理

### 定期检查
- [ ] 应用程序运行状态
- [ ] 系统资源使用情况
- [ ] API 密钥有效性
- [ ] 加密密钥安全性
- [ ] 数据备份状态

## 12. 常见部署问题

### 12.1 依赖安装失败

**解决方案**：
- 确保使用正确的 Python 版本
- 确保网络连接正常
- 尝试使用国内镜像源

### 12.2 启动失败

**解决方案**：
- 检查依赖项是否安装正确
- 检查 Python 版本是否兼容
- 查看日志文件了解详细错误信息

### 12.3 连接失败

**解决方案**：
- 检查 API 密钥是否正确
- 检查网络连接是否正常
- 确认 OKX API 服务是否正常

### 12.4 性能问题

**解决方案**：
- 关闭不需要的标签页和功能
- 减少同时运行的策略数量
- 增加系统内存
- 优化系统配置

## 13. 部署最佳实践

- 使用虚拟环境隔离依赖
- 定期更新应用程序和依赖项
- 建立自动化部署流程
- 实施监控和告警机制
- 制定详细的部署文档和操作手册
- 进行定期的安全审计

## 14. 总结

本部署方案提供了详细的部署步骤和最佳实践，确保 OKX 交易机器人能够在不同环境中稳定运行。通过遵循本方案，可以确保应用程序的安全性、可靠性和性能，为用户提供一个高效、安全的交易工具。
