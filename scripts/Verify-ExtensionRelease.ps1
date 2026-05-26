param(
    [string]$ApiBase = "https://word-addin-sooty.vercel.app",
    [string]$ExpectedVersion = "",
    [switch]$RunAuthenticatedSmoke
)

$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param(
        [string]$Label,
        [scriptblock]$Command
    )
    Write-Host ""
    Write-Host "== $Label =="
    & $Command
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$manifest = Get-Content ".\chrome_extension\manifest.json" -Raw -Encoding UTF8 | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace($ExpectedVersion)) {
    $ExpectedVersion = $manifest.version
}

Invoke-Checked "Local extension checks" {
    python -m json.tool ".\chrome_extension\manifest.json" | Out-Null
    node --check ".\chrome_extension\popup.js"
    node ".\tests\test_chrome_extension.js"
}

Invoke-Checked "Python API tests" {
    python -m unittest discover -s tests -v
}

Invoke-Checked "Python compile checks" {
    python -m py_compile `
        api\_bunken_vercel.py `
        bunkenn\word-app\api\shared\data_access.py `
        bunkenn\word-app\api\shared\bunken_service.py `
        bunkenn\word-app\api\shared\bunken_models.py
}

Invoke-Checked "GitHub raw manifest version" {
    $rawUrl = "https://raw.githubusercontent.com/luka8267/word_addin/main/chrome_extension/manifest.json?verify=$([guid]::NewGuid().ToString('N'))"
    $rawManifest = Invoke-RestMethod -Uri $rawUrl -Method Get
    Write-Host "raw version: $($rawManifest.version)"
    if ($rawManifest.version -ne $ExpectedVersion) {
        throw "Expected raw manifest version $ExpectedVersion but got $($rawManifest.version). GitHub CDN may still be stale."
    }
}

Invoke-Checked "Release ZIP version" {
    $zipPath = Join-Path $env:TEMP "bunken-web-importer-verify.zip"
    if (Test-Path $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    $files = @("manifest.json", "popup.html", "popup.css", "popup.js", "README.md")
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($file in $files) {
            $url = "https://raw.githubusercontent.com/luka8267/word_addin/main/chrome_extension/${file}?v=$([guid]::NewGuid().ToString('N'))"
            $bytes = (New-Object System.Net.WebClient).DownloadData($url)
            $entry = $zip.CreateEntry("bunken-web-importer/$file")
            $stream = $entry.Open()
            try {
                $stream.Write($bytes, 0, $bytes.Length)
            } finally {
                $stream.Dispose()
            }
        }
    } finally {
        $zip.Dispose()
    }
    $extractDir = Join-Path $env:TEMP "bunken-web-importer-verify"
    if (Test-Path $extractDir) {
        Remove-Item -LiteralPath $extractDir -Recurse -Force
    }
    Expand-Archive -LiteralPath $zipPath -DestinationPath $extractDir -Force
    $zipManifest = Get-Content (Join-Path $extractDir "bunken-web-importer\manifest.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host "zip version: $($zipManifest.version)"
    if ($zipManifest.version -ne $ExpectedVersion) {
        throw "Expected ZIP manifest version $ExpectedVersion but got $($zipManifest.version)."
    }
}

Invoke-Checked "Production extension API CORS/auth gate" {
    $api = $ApiBase.TrimEnd("/")
    $response = curl.exe -sS -i -X POST "$api/api/addin/extension/save" -H "Content-Type: application/json" -H "Origin: chrome-extension://test" -d "{}"
    $responseText = $response -join "`n"
    $responseText
    if ($responseText -notmatch "401 Unauthorized") {
        throw "Expected unauthenticated extension save request to return 401."
    }
    if ($responseText -notmatch "Access-Control-Allow-Origin") {
        throw "Expected CORS headers on extension save response."
    }
}

if ($RunAuthenticatedSmoke) {
    Invoke-Checked "Authenticated extension save smoke" {
        powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\Smoke-ExtensionSave.ps1" -ApiBase $ApiBase
    }
} else {
    Write-Host ""
    Write-Host "Skipping authenticated smoke. Rerun with -RunAuthenticatedSmoke after setting BUNKEN_EXTENSION_ACCESS_TOKEN."
}

Write-Host ""
Write-Host "Extension release verification passed for version $ExpectedVersion."
