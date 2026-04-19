# 阿里云AccessKey创建指南

## 安全提醒
⚠️ **请勿将AccessKey ID和Secret直接发送给任何人，包括AI助手**

## 创建步骤

### 方法1：通过阿里云控制台创建（推荐）

1. **登录阿里云控制台**
   - 访问: https://www.aliyun.com
   - 使用账号: gaoyuan0001@1315775683699328.onaliyun.com
   - 密码: AP:8b365338-7d7a-46da-b8c4-82134386a37d

2. **进入AccessKey管理页面**
   - 点击右上角头像 → AccessKey管理
   - 或访问: https://ram.console.aliyun.com/manage/ak

3. **创建AccessKey**
   - 点击"创建AccessKey"
   - 选择"使用子用户AccessKey"（更安全）
   - 或使用"使用主账号AccessKey"

4. **保存AccessKey信息**
   - 创建后会显示 AccessKey ID 和 AccessKey Secret
   - **立即复制并保存，Secret只会显示一次**

### 方法2：使用阿里云CLI创建

```bash
# 安装阿里云CLI
pip install aliyun-cli

# 配置账号
aliyun configure
# 输入AccessKey ID和Secret

# 创建新的AccessKey
aliyun ram CreateAccessKey --UserName <子用户名>
```

## 配置到交易系统

创建AccessKey后，在服务器上执行：

```bash
# 编辑环境变量文件
nano ~/.bashrc

# 添加以下内容到文件末尾
export OSS_ACCESS_KEY_ID=你的AccessKeyID
export OSS_ACCESS_KEY_SECRET=你的AccessKeySecret
export OSS_ENDPOINT=oss-cn-hongkong-internal.aliyuncs.com
export OSS_BUCKET_NAME=gaoyuan-okx
export ENABLE_OSS_BACKUP=true

# 保存并生效
source ~/.bashrc
```

## 验证配置

```bash
# 检查环境变量
echo $OSS_ACCESS_KEY_ID
echo $OSS_ACCESS_KEY_SECRET

# 测试OSS连接
cd /root/okx_trading_bot
python3 sync_to_oss.py check
```

## 安全建议

1. **使用子账号**：不要直接使用主账号创建AccessKey
2. **最小权限原则**：只给OSS读写权限
3. **定期轮换**：定期更换AccessKey
4. **不要硬编码**：不要将AccessKey写入代码
5. **使用环境变量**：通过环境变量传递敏感信息

## 子账号权限策略（推荐）

创建子账号时，使用以下自定义权限策略：

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "oss:PutObject",
        "oss:GetObject",
        "oss:ListObjects",
        "oss:DeleteObject"
      ],
      "Resource": [
        "acs:oss:*:*:gaoyuan-okx/*"
      ]
    }
  ]
}
```

## 遇到问题？

1. **AccessKey创建失败**：检查账号是否有RAM权限
2. **OSS连接失败**：检查网络和内网域名是否正确
3. **权限不足**：检查Bucket Policy和RAM权限

## 快速配置命令

创建AccessKey后，在服务器上执行以下命令：

```bash
cat >> ~/.bashrc << 'EOF'
# 阿里云OSS配置
export OSS_ACCESS_KEY_ID=你的AccessKeyID
export OSS_ACCESS_KEY_SECRET=你的AccessKeySecret
export OSS_ENDPOINT=oss-cn-hongkong-internal.aliyuncs.com
export OSS_BUCKET_NAME=gaoyuan-okx
export ENABLE_OSS_BACKUP=true
EOF

source ~/.bashrc

# 测试连接
cd /root/okx_trading_bot && python3 test_oss_connection.py
```
