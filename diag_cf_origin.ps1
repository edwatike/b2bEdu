# Simulate what cloudflared does: connect to 127.0.0.1:3000 and send HTTP request
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect('127.0.0.1', 3000)
    $stream = $tcp.GetStream()
    $writer = New-Object System.IO.StreamWriter($stream)
    $reader = New-Object System.IO.StreamReader($stream)
    
    $writer.Write("GET / HTTP/1.1`r`nHost: b2bedu.ru`r`nConnection: close`r`n`r`n")
    $writer.Flush()
    
    $response = ""
    while (-not $reader.EndOfStream) {
        $line = $reader.ReadLine()
        $response += $line + "`n"
        if ($response.Length -gt 500) { break }
    }
    
    Write-Host "Response (first 500 chars):"
    Write-Host $response.Substring(0, [Math]::Min(500, $response.Length))
    
    $reader.Close()
    $writer.Close()
    $tcp.Close()
} catch {
    Write-Host "FAILED: $($_.Exception.Message)"
}
