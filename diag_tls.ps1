try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect('198.41.200.63', 443)
    Write-Host "TCP connected OK"
    $stream = $tcp.GetStream()
    $callback = [System.Net.Security.RemoteCertificateValidationCallback]{ param($sender,$cert,$chain,$errors) return $true }
    $ssl = New-Object System.Net.Security.SslStream($stream, $false, $callback)
    $ssl.AuthenticateAsClient('argotunnel.com')
    Write-Host "TLS OK"
    Write-Host "Protocol: $($ssl.SslProtocol)"
    Write-Host "Cipher: $($ssl.CipherAlgorithm)"
    Write-Host "RemoteCert Subject: $($ssl.RemoteCertificate.Subject)"
    Write-Host "RemoteCert Issuer: $($ssl.RemoteCertificate.Issuer)"
    $ssl.Close()
    $tcp.Close()
} catch {
    Write-Host "TLS FAILED: $($_.Exception.Message)"
    if ($_.Exception.InnerException) {
        Write-Host "Inner: $($_.Exception.InnerException.Message)"
    }
}
