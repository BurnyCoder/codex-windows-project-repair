# Local: exercise the real scheduler with disposable fixture output. Global: never touch Codex state.
# Source: https://learn.microsoft.com/powershell/module/microsoft.powershell.management/start-process
param([switch]$SimulateFailure) # Local: repeat the same integration check with an intentional worker failure.
$ErrorActionPreference = 'Stop' # Global: any failed assertion fails the smoke check.
$smokeRepo = Split-Path -Parent $PSScriptRoot # Local: use this checkout only.
$smokeRoot = Join-Path $smokeRepo ('.local/scheduler smoke/' + [Guid]::NewGuid().ToString('N')) # Local: include a space to test Windows argument quoting.
New-Item -ItemType Directory -Path $smokeRoot -Force | Out-Null # Global: keep disposable output ignored by Git.
$smokeState = Join-Path $smokeRoot 'fixture-state.json' # Local: create an unrelated preservation sentinel.
'{"fixture":"unchanged"}' | Set-Content -LiteralPath $smokeState -Encoding UTF8 # Global: this is synthetic data only.
$smokeBefore = (Get-FileHash -LiteralPath $smokeState).Hash # Local: make preservation observable.
$smokeStdout, $smokeStderr = (Join-Path $smokeRoot 'launch.json'), (Join-Path $smokeRoot 'launch-error.log') # Local: retain complete launcher diagnostics.
$smokeScript = Join-Path $smokeRepo 'scripts/schedule-repair.ps1' # Global: test the production scheduling wrapper.
$smokeArguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}" -SmokeTest -ReportRoot "{1}"' -f $smokeScript, $smokeRoot # Local: pass exact fixture paths through the normal process boundary.
if ($SimulateFailure) { $smokeArguments += ' -SimulateFailure' } # Global: injection stays inside the fixture-only worker branch.
$smokeLauncher = Start-Process powershell.exe -ArgumentList $smokeArguments -WindowStyle Hidden -PassThru -Wait -RedirectStandardOutput $smokeStdout -RedirectStandardError $smokeStderr # Global: wait for the independent launcher and retain its exit status.
if ($smokeLauncher.ExitCode -ne 0) { throw (Get-Content -LiteralPath $smokeStderr -Raw) } # Global: registration errors cannot count as success.
$smokeLaunch = Get-Content -LiteralPath $smokeStdout -Raw | ConvertFrom-Json # Local: obtain the exact temporary task identity.
$smokeDuplicateRefused = $false # Local: the still-running fixture must reserve its registration.
try { & $smokeScript -SmokeTest -ReportRoot $smokeRoot } catch { $smokeDuplicateRefused = $_.Exception.Message -like 'A task already exists:*' } # Global: no duplicate task may replace an existing worker.
if (-not $smokeDuplicateRefused) { throw 'Duplicate scheduler registration was not refused' } # Local: fail clearly if ownership protection regresses.
$smokeDeadline = [DateTime]::UtcNow.AddSeconds(45) # Global: bound the external integration check.
do { # Local: wait for the fixture sentinel and self-cleanup, not arbitrary elapsed time.
    $smokeResultExists = Test-Path -LiteralPath (Join-Path $smokeRoot 'smoke-result.json') # Local: observe completion independently of the dead launcher.
    $smokeTaskExists = [bool](Get-ScheduledTask -TaskName $smokeLaunch.task -ErrorAction SilentlyContinue) # Global: require cleanup of the exact created task.
    if ($smokeResultExists -and -not $smokeTaskExists) { break } # Local: both operation and cleanup must complete.
    Start-Sleep -Milliseconds 500 # Local: avoid hammering Task Scheduler.
} while ([DateTime]::UtcNow -lt $smokeDeadline)
if (-not $smokeResultExists -or $smokeTaskExists) { throw "Scheduler smoke failed; inspect $smokeRoot and task $($smokeLaunch.task)" } # Global: do not hide leaked registrations.
$smokeResult = Get-Content -LiteralPath (Join-Path $smokeRoot 'smoke-result.json') -Raw | ConvertFrom-Json # Local: verify the requested path actually ran.
if ($smokeResult.stage -ne $(if ($SimulateFailure) { 'injected_failure' } else { 'scheduler_smoke_passed' })) { throw 'Unexpected worker result' } # Global: cleanup alone cannot count as operation success.
if ((Get-FileHash -LiteralPath $smokeState).Hash -ne $smokeBefore) { throw 'Fixture state changed unexpectedly' } # Global: scheduler smoke cannot mutate app-like input.
[pscustomobject]@{ passed = $true; failureInjected = [bool]$SimulateFailure; launcherExited = $smokeLauncher.HasExited; duplicateRefused = $smokeDuplicateRefused; taskRemoved = $true; fixturePreserved = $true; evidence = $smokeRoot } | ConvertTo-Json # Local: return auditable evidence without private data.
