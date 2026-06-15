param(
    [string]$AddonsRoot = "$HOME\Documents\My Games\ArmaReforgerWorkbench\addons",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$repository = "https://github.com/BohemiaInteractive/Arma-Reforger-Samples.git"
$destination = Join-Path $AddonsRoot "SampleMod_NewCar"
$temporary = Join-Path ([System.IO.Path]::GetTempPath()) ("Arma-Reforger-Samples-" + [guid]::NewGuid())

if ((Test-Path $destination) -and -not $Force) {
    Write-Host "SampleMod_NewCar already exists at $destination"
    Write-Host "Use -Force to replace it with the current official version."
    exit 0
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is required. Install Git for Windows, then run this script again."
}

New-Item -ItemType Directory -Force -Path $AddonsRoot | Out-Null
git clone --depth 1 --filter=blob:none --sparse $repository $temporary
git -C $temporary sparse-checkout set SampleMod_NewCar

if (Test-Path $destination) {
    Remove-Item -Recurse -Force $destination
}
Copy-Item -Recurse -Force (Join-Path $temporary "SampleMod_NewCar") $destination
Remove-Item -Recurse -Force $temporary

Write-Host "Installed official SampleMod_NewCar to $destination"
Write-Host "License: Arma Public License"
