# 文件名: AutoNetworkAdapter.ps1
# 功能: 自动检测OKX API和WebSocket端口连通性，并更新配置文件

param (
    [string]$ConfigPath = "config/okx_config.json",
    [string]$LogPath = "logs/network_adapter.log",
    [string]$AutoUpdate = "true",
    [int]$Timeout = 5
)

# 转换AutoUpdate参数为布尔值
$isAutoUpdate = $true
if ($AutoUpdate -eq "false" -or $AutoUpdate -eq "0" -or $AutoUpdate -eq "no") {
    $isAutoUpdate = $false
}

# 创建日志目录
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
}

# 写入日志函数
function Write-Log {
    param (
        [string]$Message,
        [string]$Level = "INFO"
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] [$Level] $Message"
    Write-Host $logMessage
    Add-Content -Path $LogPath -Value $logMessage
}

# 测试端口连通性函数
function Test-PortConnectivity {
    param (
        [string]$IP,
        [int]$Port,
        [int]$Timeout = 5
    )
    try {
        $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $connectResult = $tcpClient.BeginConnect($IP, $Port, $null, $null)
        $waitResult = $connectResult.AsyncWaitHandle.WaitOne([timespan]::FromSeconds($Timeout))
        
        if ($waitResult) {
            $tcpClient.EndConnect($connectResult)
            $tcpClient.Close()
            $stopwatch.Stop()
            return @{
                IP = $IP
                Port = $Port
                Reachable = $true
                ResponseTime = $stopwatch.ElapsedMilliseconds
            }
        } else {
            $tcpClient.Close()
            return @{
                IP = $IP
                Port = $Port
                Reachable = $false
                ResponseTime = $null
            }
        }
    } catch {
        return @{
            IP = $IP
            Port = $Port
            Reachable = $false
            ResponseTime = $null
            Error = $_.Exception.Message
        }
    }
}

# 主脚本
Write-Log "开始网络自动适配检测"

# 读取配置文件
if (-not (Test-Path $ConfigPath)) {
    Write-Log "配置文件不存在: $ConfigPath" "ERROR"
    exit 1
}

$config = Get-Content $ConfigPath | ConvertFrom-Json
$apiIps = $config.api.api_ips
$wsIps = $config.api.ws_ips

Write-Log "从配置文件读取到 $($apiIps.Count) 个API IP和 $($wsIps.Count) 个WebSocket IP"

# 合并所有IP，去重
$allIps = $apiIps + $wsIps | Select-Object -Unique
Write-Log "总共需要检测 $($allIps.Count) 个IP"

# 测试每个IP的端口
$testResults = @()
foreach ($ip in $allIps) {
    Write-Log "正在检测 IP: $ip"
    
    # 测试HTTPS端口
    $httpsResult = Test-PortConnectivity -IP $ip -Port 443 -Timeout $Timeout
    $testResults += $httpsResult
    
    # 测试WebSocket端口
    $wsResult = Test-PortConnectivity -IP $ip -Port 8443 -Timeout $Timeout
    $testResults += $wsResult
}

# 生成报告
Write-Log "=== 连通性检测报告 ==="
$reachableIps = @{}

foreach ($ip in $allIps) {
    $httpsResult = $testResults | Where-Object { $_.IP -eq $ip -and $_.Port -eq 443 }
    $wsResult = $testResults | Where-Object { $_.IP -eq $ip -and $_.Port -eq 8443 }
    
    $status = "❌ 不可达"
    if ($httpsResult.Reachable -and $wsResult.Reachable) {
        $status = "✅ 可达"
        $avgResponse = [math]::Round(($httpsResult.ResponseTime + $wsResult.ResponseTime) / 2, 2)
        $reachableIps[$ip] = $avgResponse
    }
    
    Write-Log "IP: $ip | HTTPS: $($httpsResult.Reachable) | WS: $($wsResult.Reachable) | 状态: $status"
}

# 按响应时间排序
$sortedReachableIps = $reachableIps.GetEnumerator() | Sort-Object Value
Write-Log ""
Write-Log "=== 可达IP响应时间排序 ==="
foreach ($ipEntry in $sortedReachableIps) {
    Write-Log "IP: $($ipEntry.Key) | 平均响应时间: $($ipEntry.Value)ms"
}

# 更新配置文件
if ($isAutoUpdate -and $sortedReachableIps.Count -gt 0) {
    Write-Log "正在更新配置文件"
    
    # 备份原始配置
    $backupPath = "$ConfigPath.bak.$(Get-Date -Format 'yyyyMMddHHmmss')"
    Copy-Item -Path $ConfigPath -Destination $backupPath
    Write-Log "已备份原始配置到: $backupPath"
    
    # 更新配置
    $sortedIps = $sortedReachableIps | ForEach-Object { $_.Key }
    $config.api.api_ips = $sortedIps
    $config.api.ws_ips = $sortedIps
    
    # 保存配置
    $config | ConvertTo-Json -Depth 10 | Set-Content $ConfigPath
    Write-Log "配置已更新，保留 $($sortedIps.Count) 个可达IP"
} elseif ($sortedReachableIps.Count -eq 0) {
    Write-Log "没有可达的IP，跳过配置更新" "WARNING"
}

Write-Log "网络自动适配检测完成"
