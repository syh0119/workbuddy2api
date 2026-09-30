# WorkBuddy2API 局域网访问放行脚本
# 用法：右键 -> 以管理员身份运行 PowerShell，然后执行：
#   powershell -ExecutionPolicy Bypass -File enable_lan.ps1
# 作用：为新版 Windows 防火墙放行入站 TCP 8000，并打印局域网访问地址。

$port = 8000
$ruleName = "WorkBuddy2API-$port"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[!] 需要管理员权限。请右键 PowerShell -> 以管理员身份运行，再执行本脚本。" -ForegroundColor Red
    exit 1
}

Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $port -Profile Any | Out-Null
Write-Host "[+] 已放行入站 TCP $port（所有网络类型）" -ForegroundColor Green

Write-Host ""
Write-Host "本机局域网访问地址（其他设备填这个作为 base_url）：" -ForegroundColor Cyan
Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
    ForEach-Object { Write-Host ("    http://{0}:{1}/v1" -f $_.IPAddress, $port) }
Write-Host ""
Write-Host "提示：其他设备必须与本机处于同一局域网（同一路由器/WiFi）。"
