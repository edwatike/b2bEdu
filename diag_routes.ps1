# Check routing to Cloudflare edge IPs
Write-Host "=== Route to 198.41.200.63 ==="
Find-NetRoute -RemoteIPAddress 198.41.200.63 -ErrorAction SilentlyContinue |
    Select-Object InterfaceAlias, InterfaceIndex, NextHop, DestinationPrefix | Format-Table -AutoSize

Write-Host "`n=== All network adapters ==="
Get-NetAdapter | Select-Object Name, Status, InterfaceIndex, InterfaceDescription | Format-Table -AutoSize

Write-Host "`n=== Default gateway per interface ==="
Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |
    Select-Object InterfaceAlias, InterfaceIndex, NextHop, RouteMetric | Format-Table -AutoSize

Write-Host "`n=== happ-tun interface details ==="
Get-NetIPAddress -InterfaceAlias 'happ-tun' -ErrorAction SilentlyContinue |
    Select-Object InterfaceAlias, IPAddress, PrefixLength | Format-Table -AutoSize

Write-Host "`n=== TLS test via binding to Wi-Fi adapter ==="
try {
    $wifi = Get-NetIPAddress -InterfaceAlias 'Беспроводная сеть' -AddressFamily IPv4 -ErrorAction Stop
    $localIP = $wifi.IPAddress
    Write-Host "Wi-Fi local IP: $localIP"
    
    $tcp = New-Object System.Net.Sockets.TcpClient
    $localEP = New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Parse($localIP), 0)
    $tcp.Client.Bind($localEP)
    $tcp.Connect('198.41.200.63', 443)
    Write-Host "TCP connected via Wi-Fi OK"
    
    $callback = [System.Net.Security.RemoteCertificateValidationCallback]{ param($sender,$cert,$chain,$errors) return $true }
    $ssl = New-Object System.Net.Security.SslStream($tcp.GetStream(), $false, $callback)
    $ssl.AuthenticateAsClient('argotunnel.com')
    Write-Host "TLS OK via Wi-Fi!"
    Write-Host "Protocol: $($ssl.SslProtocol)"
    Write-Host "RemoteCert Issuer: $($ssl.RemoteCertificate.Issuer)"
    $ssl.Close()
    $tcp.Close()
} catch {
    Write-Host "FAILED via Wi-Fi: $($_.Exception.Message)"
    if ($_.Exception.InnerException) { Write-Host "Inner: $($_.Exception.InnerException.Message)" }
}
