# Check if frontend responds on localhost:3000
Write-Host "=== Testing http://localhost:3000 ==="
try {
    $r = Invoke-WebRequest -Uri http://localhost:3000 -UseBasicParsing -TimeoutSec 5
    Write-Host "Status: $($r.StatusCode)"
    Write-Host "Content-Length: $($r.Content.Length)"
    Write-Host "First 200 chars: $($r.Content.Substring(0, [Math]::Min(200, $r.Content.Length)))"
} catch {
    Write-Host "FAILED: $($_.Exception.Message)"
}

Write-Host "`n=== Testing http://127.0.0.1:3000 ==="
try {
    $r2 = Invoke-WebRequest -Uri http://127.0.0.1:3000 -UseBasicParsing -TimeoutSec 5
    Write-Host "Status: $($r2.StatusCode)"
    Write-Host "Content-Length: $($r2.Content.Length)"
} catch {
    Write-Host "FAILED: $($_.Exception.Message)"
}

Write-Host "`n=== Process on port 3000 ==="
$proc = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue
if ($proc) {
    $pid_val = $proc.OwningProcess | Select-Object -First 1
    $p = Get-Process -Id $pid_val -ErrorAction SilentlyContinue
    Write-Host "PID: $pid_val"
    Write-Host "Process: $($p.ProcessName)"
    Write-Host "Path: $($p.Path)"
    Write-Host "LocalAddress: $($proc.LocalAddress | Select-Object -First 1)"
} else {
    Write-Host "No process listening on port 3000!"
}
