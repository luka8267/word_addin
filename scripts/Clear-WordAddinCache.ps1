param(
    [switch] $CloseWord
)

$ErrorActionPreference = "Stop"

$wordProcesses = Get-Process -Name WINWORD -ErrorAction SilentlyContinue
if ($wordProcesses -and -not $CloseWord) {
    Write-Warning "Word is running. Close Word first, or rerun with -CloseWord."
    $wordProcesses | Select-Object Id,ProcessName,MainWindowTitle
    exit 1
}

if ($wordProcesses -and $CloseWord) {
    $wordProcesses | Stop-Process -Force
    Start-Sleep -Seconds 1
}

$webViewProcesses = Get-Process -Name msedgewebview2 -ErrorAction SilentlyContinue
if ($webViewProcesses) {
    $webViewProcesses | Stop-Process -Force
    Start-Sleep -Seconds 1
}

$cachePaths = @(
    "$env:LOCALAPPDATA\Microsoft\Office\16.0\Wef",
    "$env:LOCALAPPDATA\Microsoft\Office\16.0\WebServiceCache",
    "$env:LOCALAPPDATA\Microsoft\Office\16.0\WebView2"
)

foreach ($path in $cachePaths) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
        Write-Host "Removed: $path"
    } else {
        Write-Host "Not found: $path"
    }
}

Write-Host ""
Write-Host "Word add-in cache cleared. Restart Word and add bunken Word from Shared Folder again."
