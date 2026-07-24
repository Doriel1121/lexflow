param(
    [string]$SampleDir = "backend/test_samples/dummy_pdfs",
    [int]$Concurrency = 5,
    [int]$TimeoutSeconds = 1800,
    [string]$SemanticQuery = "LF-DUMMY-2026",
    [switch]$Cleanup,
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$LocalSampleDir = Resolve-Path (Join-Path $RepoRoot $SampleDir)
$SupportedExtensions = @(".pdf", ".docx", ".doc", ".txt", ".jpg", ".jpeg", ".png")
$Files = Get-ChildItem -LiteralPath $LocalSampleDir -File | Where-Object { $SupportedExtensions -contains $_.Extension.ToLowerInvariant() }

if ($Files.Count -eq 0) {
    throw "No supported files found in $LocalSampleDir"
}

$RepoRootText = $RepoRoot.Path.TrimEnd('\')
$LocalSampleDirText = $LocalSampleDir.Path.TrimEnd('\')
if (-not $LocalSampleDirText.StartsWith($RepoRootText, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "SampleDir must be inside the repo root: $RepoRootText"
}
$RelativeSampleDir = $LocalSampleDirText.Substring($RepoRootText.Length).TrimStart('\').Replace("\", "/")
$ContainerSampleDir = "/app/$RelativeSampleDir"
$CleanupFlag = if ($Cleanup) { "--cleanup" } else { "--no-cleanup" }

Write-Host "LexFlow full processing drain test" -ForegroundColor Cyan
Write-Host "Sample folder: $LocalSampleDir"
Write-Host "Container folder: $ContainerSampleDir"
Write-Host "Files: $($Files.Count)"
Write-Host "Concurrency: $Concurrency"
Write-Host "Cleanup: $($Cleanup.IsPresent)"

if (-not $NoBuild) {
    Write-Host "Ensuring backend container is running..." -ForegroundColor DarkCyan
    docker compose up -d backend celery_worker
}

$command = @(
    "compose", "exec", "-T", "backend", "python", "scripts/measure_processing_drain.py",
    "--sample-dir", $ContainerSampleDir,
    "--uploads", "0",
    "--concurrency", $Concurrency.ToString(),
    "--timeout-seconds", $TimeoutSeconds.ToString(),
    "--semantic-query", $SemanticQuery,
    $CleanupFlag
)

Write-Host "Running: docker $($command -join ' ')" -ForegroundColor DarkGray
& docker @command
