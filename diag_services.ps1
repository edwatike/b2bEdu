# Check for antivirus / SSL inspection services
Write-Host "=== Running security services ==="
Get-Service -ErrorAction SilentlyContinue | Where-Object {
    $_.DisplayName -match 'kasper|eset|avast|avg|norton|bitdefender|drweb|defender|malware|sophos|trend|mcafee|symantec' -and $_.Status -eq 'Running'
} | Select-Object Name, DisplayName, Status | Format-Table -AutoSize

Write-Host "`n=== Outbound BLOCK firewall rules ==="
Get-NetFirewallRule -Direction Outbound -Action Block -Enabled True -ErrorAction SilentlyContinue |
    Select-Object DisplayName | Format-Table -AutoSize

Write-Host "`n=== Firewall rules mentioning cloudflared ==="
Get-NetFirewallRule -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -match 'cloudflared' } |
    Select-Object DisplayName, Direction, Action, Enabled | Format-Table -AutoSize

Write-Host "`n=== Happ-tun adapter (VPN/tunnel) ==="
Get-NetAdapter -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match 'happ|tun|tap|wg|vpn' } |
    Select-Object Name, Status, InterfaceDescription | Format-Table -AutoSize
