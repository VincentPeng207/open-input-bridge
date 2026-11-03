# Restart launcher: replace only a prior instance from this exact checkout.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$bridgeFile = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'windows\ly03_voice_bridge_ws_v1.py'))
if (-not (Test-Path -LiteralPath $bridgeFile -PathType Leaf)) {
    Write-Host "[ERROR] Bridge script not found: $bridgeFile"
    exit 1
}

# Forward arguments to Python; user-specified --hotkey overrides our default.
$bridgeArgs = @('--hotkey', 'ctrl+win', '--copy-url') + @($args)
$port = 8766
for ($i = 0; $i -lt $bridgeArgs.Count; $i++) {
    $item = [string]$bridgeArgs[$i]
    if ($item -eq '--port' -and $i + 1 -lt $bridgeArgs.Count) {
        $number = 0
        if ([int]::TryParse([string]$bridgeArgs[$i + 1], [ref]$number) -and $number -ge 1 -and $number -le 65535) {
            $port = $number
        }
    } elseif ($item -match '^--port=(\d+)$') {
        $number = [int]$Matches[1]
        if ($number -ge 1 -and $number -le 65535) { $port = $number }
    }
}

function Get-ListenerPids([int]$ListenPort) {
    $connections = @(Get-NetTCPConnection -LocalPort $ListenPort -State Listen -ErrorAction SilentlyContinue)
    return @($connections | Select-Object -ExpandProperty OwningProcess -Unique)
}

function Test-SameCheckoutBridge([int]$ProcessId, [string]$ExpectedScript) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    if ($null -eq $process) { return $false }
    $exe = [System.IO.Path]::GetFileName([string]$process.ExecutablePath)
    if ($exe -notin @('python.exe', 'pythonw.exe')) { return $false }
    $command = [string]$process.CommandLine
    # Exact Python script argument, not an arbitrary Python process or an unrelated checkout.
    $pattern = '(?i)(^|\s|")' + [regex]::Escape($ExpectedScript) + '($|\s|")'
    return [regex]::IsMatch($command, $pattern)
}

if ($bridgeArgs -contains '--help' -or $bridgeArgs -contains '-h') {
    & py -3 $bridgeFile @bridgeArgs
    exit $LASTEXITCODE
}

$owners = @(Get-ListenerPids $port)
foreach ($ownerPid in $owners) {
    if (-not (Test-SameCheckoutBridge -ProcessId ([int]$ownerPid) -ExpectedScript $bridgeFile)) {
        Write-Host "[ERROR] Port $port is occupied by PID $ownerPid; not this checkout's bridge."
        Write-Host '        Nothing was stopped. Check the process manually.'
        exit 2
    }
}

foreach ($ownerPid in $owners) {
    if ((@(Get-ListenerPids $port) -contains [int]$ownerPid) -and
        (Test-SameCheckoutBridge -ProcessId ([int]$ownerPid) -ExpectedScript $bridgeFile)) {
        Write-Host "[Open Input Bridge] Replacing previous bridge on port $port (PID $ownerPid)."
        try {
            Stop-Process -Id ([int]$ownerPid) -Force -ErrorAction Stop
        } catch {
            Write-Host "[ERROR] Could not stop bridge PID $ownerPid : $($_.Exception.Message)"
            exit 3
        }
    }
}
if ($owners.Count -gt 0) {
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if (@(Get-ListenerPids $port).Count -eq 0) { break }
        Start-Sleep -Milliseconds 200
    }
}
if (@(Get-ListenerPids $port).Count -ne 0) {
    Write-Host "[ERROR] Port $port remains occupied. New bridge was not started."
    exit 4
}

Write-Host '[Open Input Bridge] Starting receiver. Ctrl+C stops the service.'
Write-Host '        A fresh token is generated on each start; reopen the new URL on Android.'
& py -3 $bridgeFile @bridgeArgs
exit $LASTEXITCODE
