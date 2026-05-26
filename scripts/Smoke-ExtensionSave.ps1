param(
    [string]$ApiBase = "https://word-addin-sooty.vercel.app",
    [string]$AccessToken = $env:BUNKEN_EXTENSION_ACCESS_TOKEN,
    [string]$Email = $env:BUNKEN_EXTENSION_EMAIL,
    [string]$Password = $env:BUNKEN_EXTENSION_PASSWORD,
    [string]$Title = "",
    [string]$Doi = "",
    [string]$Url = "https://example.org/bunken-extension-smoke",
    [string]$PdfCandidate = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($AccessToken)) {
    if ([string]::IsNullOrWhiteSpace($Email) -or [string]::IsNullOrWhiteSpace($Password)) {
        Write-Host "BUNKEN_EXTENSION_ACCESS_TOKEN is not set."
        Write-Host "Either set a Supabase access token:"
        Write-Host '$env:BUNKEN_EXTENSION_ACCESS_TOKEN="<access token>"'
        Write-Host "or set bunken login credentials so this script can request one through the add-in API:"
        Write-Host '$env:BUNKEN_EXTENSION_EMAIL="<email>"'
        Write-Host '$env:BUNKEN_EXTENSION_PASSWORD="<password>"'
        exit 2
    }

    $loginBody = @{
        email = $Email
        password = $Password
    } | ConvertTo-Json -Depth 4
    $apiForLogin = $ApiBase.TrimEnd("/")
    Write-Host "Requesting access token through $apiForLogin/api/addin/auth/login ..."
    $login = Invoke-RestMethod `
        -Method Post `
        -Uri "$apiForLogin/api/addin/auth/login" `
        -Headers @{
            "Content-Type" = "application/json"
            "Origin" = "chrome-extension://bunken-smoke-test"
        } `
        -Body $loginBody
    $AccessToken = $login.accessToken
    if ([string]::IsNullOrWhiteSpace($AccessToken)) {
        throw "Login response did not include accessToken."
    }
}

$stamp = Get-Date -Format "yyyyMMddHHmmss"
if ([string]::IsNullOrWhiteSpace($Title)) {
    $Title = "bunken extension smoke test $stamp"
}
if ([string]::IsNullOrWhiteSpace($Doi)) {
    $Doi = "10.5555/bunken-smoke-$stamp"
}

$api = $ApiBase.TrimEnd("/")
$headers = @{
    "Authorization" = "Bearer $AccessToken"
    "Content-Type" = "application/json"
    "Origin" = "chrome-extension://bunken-smoke-test"
}
$payload = @{
    url = $Url
    title = $Title
    authors = @("Smoke Tester")
    journal = "bunken Smoke Tests"
    year = (Get-Date -Format "yyyy")
    doi = $Doi
    abstract = "Created by scripts/Smoke-ExtensionSave.ps1 to verify the Chrome extension save flow."
    pdfCandidates = @($PdfCandidate)
} | ConvertTo-Json -Depth 6

Write-Host "Saving smoke paper: $Title"
$first = Invoke-RestMethod `
    -Method Post `
    -Uri "$api/api/addin/extension/save" `
    -Headers $headers `
    -Body $payload

Write-Host "First save:"
$first | ConvertTo-Json -Depth 8

Write-Host "Saving same DOI again to verify duplicate handling..."
$second = Invoke-RestMethod `
    -Method Post `
    -Uri "$api/api/addin/extension/save" `
    -Headers $headers `
    -Body $payload

Write-Host "Second save:"
$second | ConvertTo-Json -Depth 8

Write-Host "Searching saved paper through add-in papers API..."
$encodedQuery = [System.Uri]::EscapeDataString($Doi)
$list = Invoke-RestMethod `
    -Method Get `
    -Uri "$api/api/addin/papers?q=$encodedQuery" `
    -Headers $headers

$items = @($list.items)
$matched = $items | Where-Object { $_.doi -eq $Doi -or $_.title -eq $Title }

if (-not $first.itemId) {
    throw "First save did not return itemId."
}
if (-not $second.duplicate) {
    throw "Second save was not reported as duplicate."
}
if (-not $matched) {
    throw "Saved paper was not found through /api/addin/papers."
}

Write-Host "Smoke test passed."
Write-Host "itemId=$($first.itemId)"
Write-Host "pdfSaved=$($first.pdf.saved)"
Write-Host "matchedItems=$($matched.Count)"
