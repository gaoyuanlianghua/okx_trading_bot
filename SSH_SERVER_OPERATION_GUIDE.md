# SSH服务器操作OKX交易机器人指南

## 服务器信息

- **服务器IP**: 47.79.20.181
- **用户名**: root
- **密码**: w528329818.123
- **工作目录**: /root/okx\_trading\_bot

***

## 1. 连接到SSH服务器

### 使用密码连接

```bash
ssh root@47.79.20.181
# 密码: Gy528329818.123
```

### 使用sshpass自动输入密码（Linux/Mac）

```bash
# 安装sshpass
sudo apt-get install sshpass  # Ubuntu/Debian
brew install sshpass          # Mac

# 连接
sshpass -p "Gy528329818.123" ssh root@47.79.20.181
```

***

## 2. 基本操作命令

### 2.1 进入工作目录

```bash
cd /root/okx_trading_bot
```

### 2.2 查看当前状态

```bash
# 查看Git状态
git status

# 查看最近提交记录
git log --oneline -5

# 查看当前分支
git branch
```

### 2.3 同步最新代码

```bash
# 拉取最新代码
git pull origin master

# 如果有本地修改，先保存
 git stash
git pull origin master
git stash pop
```

***

## 3. 启动交易机器人

### 3.1 启动主程序

```bash
cd /root/okx_trading_bot
python3 main_new.py
```

### 3.2 后台运行（推荐）

```bash
# 使用nohup后台运行
nohup python3 main_new.py > trading_bot.log 2>&1 &

# 查看日志
tail -f trading_bot.log
```

### 3.3 使用screen后台运行

```bash
# 创建screen会话
screen -S trading_bot

# 在screen中启动程序
cd /root/okx_trading_bot
python3 main_new.py

# 分离screen会话（按Ctrl+A，然后按D）

# 重新连接screen会话
screen -r trading_bot

# 查看所有screen会话
screen -ls

# 终止screen会话
screen -X -S trading_bot quit
```

***

## 4. 停止交易机器人

### 4.1 查找并停止进程

```bash
# 查找Python进程
ps aux | grep python3

# 停止特定进程
kill <PID>

# 强制停止
kill -9 <PID>
```

### 4.2 停止所有相关进程

```bash
# 停止所有Python进程
pkill -f python3

# 或者停止特定程序
pkill -f main_new.py
```

***

## 5. 监控和日志

### 5.1 查看实时日志

```bash
# 查看主程序日志
tail -f /root/okx_trading_bot/logs/trading_bot.log

# 查看错误日志
tail -f /root/okx_trading_bot/logs/error.log
```

### 5.2 查看系统状态

```bash
# 查看系统资源使用
top
htop

# 查看磁盘空间
df -h

# 查看内存使用
free -h
```

### 5.3 查看网络连接

```bash
# 查看网络连接
netstat -tuln

# 查看WebSocket连接
netstat -an | grep 8443
```

***

## 6. 策略管理

### 6.1 查看已加载的策略

```bash
# 查看策略配置文件
cat /root/okx_trading_bot/config/config.yaml

# 查看策略执行记录
ls -la /root/okx_trading_bot/data/
```

### 6.2 修改策略参数

```bash
# 编辑配置文件
vim /root/okx_trading_bot/config/config.yaml

# 或者使用nano
nano /root/okx_trading_bot/config/config.yaml
```

### 6.3 策略参数说明

```yaml
strategy:
  default_strategy: NuclearDynamicsStrategy
  strategies:
    NuclearDynamicsStrategy:
      G_eff: 0.0015        # 市场耦合系数
      max_position: 0.5    # 最大仓位比例
      position_size: 0.1   # 仓位大小
      stop_loss: 0.02      # 止损比例
      take_profit: 0.05    # 止盈比例
      ε: 0.85              # 市场动量方向算符
```

***

## 7. 风险管理

### 7.1 查看风险参数

```bash
# 查看风险配置
cat /root/okx_trading_bot/config/config.yaml | grep -A 10 "risk:"
```

### 7.2 修改风险参数

```yaml
risk:
  max_drawdown: 0.1           # 最大回撤10%
  max_leverage: 10            # 最大杠杆10倍
  max_position_percent: 0.5   # 最大仓位50%
  stop_loss_enabled: true     # 启用止损
  take_profit_enabled: true   # 启用止盈
  alert_thresholds:
    drawdown: 0.05            # 回撤预警5%
    leverage: 8               # 杠杆预警8倍
    position_size: 0.4        # 仓位预警40%
```

***

## 8. 测试和调试

### 8.1 运行网络测试

```bash
cd /root/okx_trading_bot
python3 test_network.py
```

### 8.2 运行API测试

```bash
cd /root/okx_trading_bot
python3 test_full_api.py
```

### 8.3 运行策略测试

```bash
cd /root/okx_trading_bot
python3 test_all_strategies.py
```

***

## 9. 常见问题解决

### 9.1 WebSocket连接问题

```bash
# 检查网络连接
ping ws.okx.com

# 检查端口连通性
telnet ws.okx.com 8443

# 重启WebSocket连接
pkill -f main_new.py
python3 main_new.py
```

### 9.2 依赖包问题

```bash
# 安装缺失的依赖
pip3 install scipy scikit-learn hjson

# 安装所有依赖
pip3 install -r requirements.txt
```

### 9.3 权限问题

```bash
# 修复文件权限
chmod +x /root/okx_trading_bot/*.py

# 修复目录权限
chmod -R 755 /root/okx_trading_bot
```

***

## 10. 备份和恢复

### 10.1 备份配置文件

```bash
# 备份配置
cp /root/okx_trading_bot/config/config.yaml /root/okx_trading_bot/config/config.yaml.backup

# 备份数据
cp -r /root/okx_trading_bot/data /root/okx_trading_bot/data_backup
```

### 10.2 恢复配置

```bash
# 恢复配置
cp /root/okx_trading_bot/config/config.yaml.backup /root/okx_trading_bot/config/config.yaml

# 恢复数据
cp -r /root/okx_trading_bot/data_backup /root/okx_trading_bot/data
```

***

## 11. 性能优化

### 11.1 查看Python进程资源使用

```bash
# 查看Python进程CPU和内存使用
ps aux | grep python3

# 查看详细资源使用
pidstat -p <PID> 1
```

### 11.2 优化系统参数

```bash
# 增加文件描述符限制
ulimit -n 65535

# 查看当前限制
ulimit -a
```

***

## 12. 安全建议

### 12.1 修改SSH默认端口

```bash
# 编辑SSH配置
vim /etc/ssh/sshd_config

# 修改端口
Port 2222

# 重启SSH服务
systemctl restart sshd
```

### 12.2 使用密钥认证

```bash
# 生成密钥对
ssh-keygen -t rsa -b 4096

# 复制公钥到服务器
ssh-copy-id root@47.79.20.181

# 禁用密码登录
vim /etc/ssh/sshd_config
PasswordAuthentication no
```

***

## 13. 联系和支持

### 13.1 查看日志获取帮助

```bash
# 查看详细日志
cat /root/okx_trading_bot/logs/trading_bot.log | grep ERROR

# 查看最近错误
tail -n 100 /root/okx_trading_bot/logs/error.log
```

### 13.2 GitHub仓库

- 仓库地址: <https://github.com/gaoyuanlianghua/okx_trading_bot>
- 提交问题: <https://github.com/gaoyuanlianghua/okx_trading_bot/issues>

***

## 14. 快捷命令汇总

```bash
# 连接服务器
ssh root@47.79.20.181

# 进入目录
cd /root/okx_trading_bot

# 启动机器人
python3 main_new.py

# 后台启动
nohup python3 main_new.py > trading_bot.log 2>&1 &

# 查看日志
tail -f trading_bot.log

# 停止机器人
pkill -f main_new.py

# 同步代码
git pull origin master

# 查看状态
ps aux | grep python3
```

***

## 注意事项

1. **交易风险**: 自动交易存在风险，请确保了解策略的工作原理
2. **资金安全**: 使用虚拟盘API进行测试，确认稳定后再使用实盘
3. **监控日志**: 定期检查日志，及时发现和解决问题
4. **备份配置**: 定期备份配置文件和重要数据
5. **更新代码**: 定期同步最新代码，获取bug修复和功能更新

***

**最后更新**: 2026-04-01
**版本**: v1.0
