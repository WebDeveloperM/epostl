<#
  Kompyuterdagi saytni vaqtincha internetga chiqarish (Cloudflare "quick tunnel", hisob shart emas).

    powershell -ExecutionPolicy Bypass -File tools\tunnel.ps1 start    # yoqish va manzilni chiqarish
    powershell -ExecutionPolicy Bypass -File tools\tunnel.ps1 url      # joriy manzilni ko'rsatish
    powershell -ExecutionPolicy Bypass -File tools\tunnel.ps1 stop     # o'chirish (sayt yopiladi)

  Kerak: Docker stack ishlayotgan bo'lsin (http://localhost:8080) va cloudflared.exe.
  cloudflared.exe qidiriladi: $env:CLOUDFLARED, PATH, so'ng %USERPROFILE%\cloudflared\cloudflared.exe
  Manzil (https://....trycloudflare.com) har safar yoqilganda yangi bo'ladi.
#>
param([ValidateSet("start", "stop", "url")][string]$Action = "start")

$ErrorActionPreference = "Stop"
$root   = Split-Path -Parent $PSScriptRoot
$state  = Join-Path $root "logs\tunnel"
$pidFile = Join-Path $state "tunnel.pid"
$logFile = Join-Path $state "tunnel.log"
$outFile = Join-Path $state "tunnel.out.log"
$target = "http://localhost:8080"
$pattern = "https://[a-z0-9-]+\.trycloudflare\.com"

function Find-Cloudflared {
    if ($env:CLOUDFLARED -and (Test-Path $env:CLOUDFLARED)) { return $env:CLOUDFLARED }
    $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $home_exe = Join-Path $env:USERPROFILE "cloudflared\cloudflared.exe"
    if (Test-Path $home_exe) { return $home_exe }
    return $null
}

function Get-Running {
    if (-not (Test-Path $pidFile)) { return $null }
    $id = [int](Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if (-not $id) { return $null }
    return Get-Process -Id $id -ErrorAction SilentlyContinue
}

function Get-TunnelUrl {
    if (-not (Test-Path $logFile)) { return $null }
    $m = Select-String -Path $logFile -Pattern $pattern | Select-Object -Last 1
    if ($m) { return [regex]::Match($m.Line, $pattern).Value }
    return $null
}

switch ($Action) {
    "url" {
        $u = Get-TunnelUrl
        if ((Get-Running) -and $u) { Write-Host $u } else { Write-Host "Tunnel ishlamayapti. Yoqish: tools\tunnel.ps1 start"; exit 1 }
    }
    "stop" {
        $p = Get-Running
        if ($p) { Stop-Process -Id $p.Id -Force; Write-Host "Tunnel o'chirildi - sayt endi internetdan ochilmaydi." }
        else { Write-Host "Tunnel ishlamayotgan edi." }
        Remove-Item $pidFile -ErrorAction SilentlyContinue
    }
    "start" {
        if (Get-Running) { Write-Host "Tunnel allaqachon ishlayapti: $(Get-TunnelUrl)"; exit 0 }
        $exe = Find-Cloudflared
        if (-not $exe) {
            Write-Host "cloudflared.exe topilmadi. O'rnating: winget install Cloudflare.cloudflared"
            Write-Host "yoki https://github.com/cloudflare/cloudflared/releases dan yuklab %USERPROFILE%\cloudflared\ ga qo'ying."
            exit 1
        }
        try { Invoke-WebRequest -Uri $target -UseBasicParsing -TimeoutSec 8 | Out-Null }
        catch { Write-Host "$target javob bermayapti. Avval: docker compose up -d"; exit 1 }

        New-Item -ItemType Directory -Force -Path $state | Out-Null
        Remove-Item $logFile, $outFile -ErrorAction SilentlyContinue
        # http2: korporativ tarmoqlarda ko'pincha UDP (quic) yopiq, TCP ishlaydi
        $p = Start-Process -FilePath $exe -WindowStyle Hidden -PassThru `
            -ArgumentList @("tunnel", "--no-autoupdate", "--protocol", "http2", "--url", $target) `
            -RedirectStandardError $logFile -RedirectStandardOutput $outFile
        Set-Content -Path $pidFile -Value $p.Id

        $url = $null
        for ($i = 0; $i -lt 40 -and -not $url; $i++) {
            Start-Sleep -Seconds 1
            if ($p.HasExited) { break }
            $url = Get-TunnelUrl
        }
        if ($url) {
            Write-Host "Sayt internetda: $url"
            Write-Host "O'chirish: powershell -ExecutionPolicy Bypass -File tools\tunnel.ps1 stop"
        } else {
            Write-Host "Manzil olinmadi. Jurnal: $logFile"
            if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }
            Remove-Item $pidFile -ErrorAction SilentlyContinue
            exit 1
        }
    }
}
