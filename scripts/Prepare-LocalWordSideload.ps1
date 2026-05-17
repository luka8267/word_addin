param(
    [string] $CatalogPath = "$env:USERPROFILE\Documents\bunken-word-addin-catalog",
    [string] $BaseUrl = "https://localhost:4280",
    [string] $ShareName = "bunken-word-addin-catalog",
    [ValidateSet("taskpane", "full", "minimal", "commands", "icons")]
    [string] $ManifestVariant = "taskpane",
    [switch] $CreateShare,
    [switch] $CheckLocalServer
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$manifestGenerator = Join-Path $repoRoot "bunkenn\generate_manifest.py"
$manifestFileName = if ($ManifestVariant -eq "taskpane") {
    "manifest.local.xml"
} elseif ($ManifestVariant -eq "full") {
    "manifest.local.xml"
} else {
    "manifest.local.$ManifestVariant.xml"
}
$manifestSource = Join-Path $repoRoot "bunkenn\$manifestFileName"
$catalogDir = New-Item -ItemType Directory -Force -Path $CatalogPath
$catalogManifest = Join-Path $catalogDir.FullName "manifest.xml"

$env:BUNKEN_LOCAL_BASE_URL = $BaseUrl
python $manifestGenerator --local
Copy-Item -LiteralPath $manifestSource -Destination $catalogManifest -Force

Write-Host ""
Write-Host "Local Word manifest prepared:"
Write-Host "  $catalogManifest"
Write-Host "Variant:"
Write-Host "  $ManifestVariant"
Write-Host ""

if ($CheckLocalServer) {
    try {
        $taskpane = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/taskpane.html" -TimeoutSec 8
        $version = Invoke-RestMethod -Uri "$BaseUrl/api/addin/papers?_debug=version" -TimeoutSec 8
        Write-Host "Local server check:"
        Write-Host "  taskpane.html: HTTP $($taskpane.StatusCode)"
        Write-Host "  api version: $($version.version)"
        Write-Host ""
    } catch {
        Write-Warning "Local server check failed: $($_.Exception.Message)"
        Write-Warning "Start Functions and SWA CLI before opening the add-in in Word."
        Write-Host ""
    }
}

if ($CreateShare) {
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
    if (-not $isAdmin) {
        throw "Run PowerShell as Administrator to create an SMB share, or rerun without -CreateShare."
    }

    $existingShare = Get-SmbShare -Name $ShareName -ErrorAction SilentlyContinue
    if ($existingShare) {
        if ((Resolve-Path $existingShare.Path).Path -ne $catalogDir.FullName) {
            throw "SMB share '$ShareName' already exists and points to '$($existingShare.Path)'."
        }
    } else {
        New-SmbShare -Name $ShareName -Path $catalogDir.FullName -ReadAccess $env:USERNAME | Out-Null
    }

    Write-Host "SMB share ready:"
    Write-Host "  \\$env:COMPUTERNAME\$ShareName"
    Write-Host "  \\localhost\$ShareName"
    Write-Host ""
}

Write-Host "Next manual Word steps:"
Write-Host "  1. Word: File > Options > Trust Center > Trust Center Settings."
Write-Host "  2. Trusted Add-in Catalogs: add the network share URL."
Write-Host "  3. Check 'Show in Menu', then restart Word."
Write-Host "  4. Insert > My Add-ins > Shared Folder > bunken Word."
Write-Host ""
Write-Host "If you did not use -CreateShare, share this folder first:"
Write-Host "  $($catalogDir.FullName)"
