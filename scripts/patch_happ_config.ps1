# Patch Happ sing-box config to add cloudflared.exe bypass
# Run this AFTER Happ connects/reconnects VPN

$configPath = "C:\Users\admin\AppData\Local\Happ\config.json"

Write-Host "Reading Happ config..." -ForegroundColor Cyan
$json = Get-Content $configPath -Raw | ConvertFrom-Json

# 1) Add cloudflared.exe to process_name bypass
$processRule = $json.route.rules | Where-Object { $_.outbound -eq "direct" -and $_.process_name } | Select-Object -First 1
if ($processRule) {
    $names = [System.Collections.ArrayList]@($processRule.process_name)
    if ("cloudflared.exe" -notin $names) {
        $names.Add("cloudflared.exe") | Out-Null
        $names.Add("cloudflared") | Out-Null
        $processRule.process_name = $names.ToArray()
        Write-Host "  Added cloudflared.exe to process bypass" -ForegroundColor Green
    } else {
        Write-Host "  cloudflared.exe already in process bypass" -ForegroundColor Yellow
    }
}

# 2) Disable strict_route
$tunInbound = $json.inbounds | Where-Object { $_.type -eq "tun" } | Select-Object -First 1
if ($tunInbound -and $tunInbound.strict_route -eq $true) {
    $tunInbound.strict_route = $false
    Write-Host "  Disabled strict_route" -ForegroundColor Green
} else {
    Write-Host "  strict_route already false or not found" -ForegroundColor Yellow
}

# 3) Add IP CIDR rule for Cloudflare edge IPs (if not present)
$hasIpRule = $json.route.rules | Where-Object { $_.ip_cidr -and $_.outbound -eq "direct" }
if (-not $hasIpRule) {
    $ipRule = [PSCustomObject]@{
        ip_cidr = @("198.41.192.0/24", "198.41.200.0/24")
        outbound = "direct"
    }
    $rules = [System.Collections.ArrayList]@($json.route.rules)
    $rules.Insert(1, $ipRule) | Out-Null
    $json.route.rules = $rules.ToArray()
    Write-Host "  Added Cloudflare IP CIDR direct rule" -ForegroundColor Green
}

# Save
$json | ConvertTo-Json -Depth 10 | Set-Content $configPath -Encoding UTF8
Write-Host "Config patched successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Now restart sing-box:" -ForegroundColor Cyan
Write-Host "  1) In Happ app: disconnect and reconnect VPN" -ForegroundColor White
Write-Host "  OR" -ForegroundColor Yellow
Write-Host "  2) Run: taskkill /F /IM sing-box.exe (Happ will restart it)" -ForegroundColor White
