<#
.SYNOPSIS
  Install dcai-unified-kernel into an Agent Skills directory (Windows).

.DESCRIPTION
  ASCII-only on purpose: Windows PowerShell 5.1 reads BOM-less UTF-8 scripts as ANSI,
  which breaks non-ASCII string literals. Keep this file plain ASCII.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File install/install.ps1

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File install/install.ps1 -Target "$env:USERPROFILE\.dsh\skills"

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File install/install.ps1 -Remove
#>
[CmdletBinding()]
param(
  [string]$Target,
  [switch]$Check,
  [switch]$Remove
)

$ErrorActionPreference = 'Stop'
$Name = 'dcai-unified-kernel'
$Src = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

$Candidates = @(
  (Join-Path $env:USERPROFILE '.claude\skills'),
  (Join-Path $env:USERPROFILE '.dsh\skills'),
  (Join-Path $env:USERPROFILE '.codex\skills'),
  (Join-Path $env:USERPROFILE '.cursor\skills'),
  (Join-Path $env:USERPROFILE '.config\opencode\skills')
)

if ($Target) {
  $Bases = @($Target)
} else {
  $Bases = @($Candidates | Where-Object { Test-Path -LiteralPath $_ })
  if ($Bases.Count -eq 0) {
    $Bases = @($Candidates[1])
    if (-not $Check) { New-Item -ItemType Directory -Force -Path $Bases[0] | Out-Null }
  }
}

foreach ($base in $Bases) {
  $dest = Join-Path $base $Name
  if ($Remove) {
    if (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Recurse -Force; "removed $dest" }
    else { "not installed: $dest" }
    continue
  }
  if ($Check) { "would install to $dest"; continue }
  New-Item -ItemType Directory -Force -Path $base | Out-Null
  if (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Recurse -Force }
  Copy-Item -LiteralPath $Src -Destination $dest -Recurse
  "installed $dest"
}

if (-not $Remove -and -not $Check) {
  ""
  "Open a new agent session for the skill to be picked up."
  "Verify with: 'Load the DCAI kernel and confirm the version only.'"
}
