# Local: launch through Task Scheduler. Global: Windows schedules the worker independently of the initiating CLI.
# Sources: https://learn.microsoft.com/powershell/module/scheduledtasks/register-scheduledtask
# and https://learn.microsoft.com/powershell/module/scheduledtasks/new-scheduledtaskprincipal
[CmdletBinding()]
param(
    [string]$Plan, # Local: reviewed plan file; never embedded in a shell command as code.
    [switch]$Worker, # Global: only Windows invokes the independent execution branch normally.
    [string]$TaskName, # Local: exact temporary registration owned by this invocation.
    [string]$UvPath, # Local: resolve uv before leaving the caller's environment.
    [string]$ProfileHome, # Global: pin the profile discovered during preflight.
    [string]$ReportRoot, # Local: pin the private report location too.
    [string]$PlanSha256, # Global: reject edits to the plan after scheduling.
    [switch]$SmokeTest, # Local: test scheduler lifetime and cleanup without reading Codex state.
    [switch]$SimulateFailure # Local: inject a fixture-only failure to verify worker cleanup.
)
$ErrorActionPreference = 'Stop' # Global: registration and cleanup failures must be visible.
$repairRepo = (Split-Path -Parent $PSScriptRoot).Replace('\', '/') # Local: uv environment paths use forward slashes.
$repairEnvArgs = @() # Local: .env is optional when defaults suffice.
if (Test-Path -LiteralPath "$repairRepo/.env") { $repairEnvArgs = @('--env-file', "$repairRepo/.env") } # Global: read only the clone's own optional configuration.
if ($Worker) { # Global: this process is owned by Windows Task Scheduler, not Codex.
    if ($TaskName -notmatch '^CodexProjectRepair-(Smoke-)?[a-f0-9]{16}$') { throw 'Unexpected worker task identity' } # Local: constrain cleanup to this tool's naming scheme.
    $repairExitCode = 1 # Global: missing launch success remains failure.
    $repairTranscript = Join-Path $ReportRoot ('launcher-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '.log') # Local: name the recording; errors outside its active interval may be absent.
    try { # Global: attempt task cleanup on handled completion; forced termination can bypass finally.
        New-Item -ItemType Directory -Path $ReportRoot -Force | Out-Null # Local: bootstrap failure still reaches scheduler cleanup.
        Start-Transcript -LiteralPath $repairTranscript | Out-Null # Local: record output during the transcript's active interval.
        if ($SmokeTest) { # Global: this branch cannot invoke apply or read any Codex profile.
            Start-Sleep -Seconds 5 # Local: keep the disposable worker alive after its launcher exits.
            [pscustomobject]@{ stage = $(if ($SimulateFailure) { 'injected_failure' } else { 'scheduler_smoke_passed' }); workerPid = $PID; task = $TaskName } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $ReportRoot 'smoke-result.json') -Encoding UTF8 # Local: write only the explicitly selected fixture output.
            if ($SimulateFailure) { throw 'Intentional fixture failure to test cleanup' } # Global: exercise the same finally block as a failed repair.
            $repairExitCode = 0 # Local: record the sentinel operation's success.
        } else { # Global: real repairs reuse every tested Python guard.
            & $UvPath run --frozen --project $repairRepo @repairEnvArgs codex-project-repair --home $ProfileHome --output $ReportRoot apply --plan $Plan --plan-sha256 $PlanSha256 --wait --reopen # Local: pass data as individual arguments.
            $repairExitCode = $LASTEXITCODE # Global: preserve the repair's true result.
        }
    } finally { # Global: cleanup must happen even when uv cannot start.
        try { Stop-Transcript | Out-Null } catch { Write-Warning $_ } # Local: avoid masking the original failure if transcript startup failed.
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false # Global: remove only this invocation's temporary registration.
    }
    exit $repairExitCode # Local: expose the outcome to the scheduler.
}
if ($SmokeTest) { # Global: integration checks never depend on real profile configuration.
    if (-not $ReportRoot) { throw 'Smoke tests require an explicit fixture ReportRoot' } # Local: prevent accidental output selection.
    $ReportRoot = [IO.Path]::GetFullPath($ReportRoot) # Local: bind the disposable output to an absolute path.
    $ProfileHome = $ReportRoot # Local: use the fixture path only as a unique task identity.
} else { # Global: validate the concrete repair before scheduling it.
    if (-not $Plan) { throw 'Supply -Plan with a reviewed plan file' } # Local: never repair without selection.
    $Plan = (Resolve-Path -LiteralPath $Plan).Path # Local: avoid dependence on the future worker's working directory.
    $UvPath = (Get-Command uv -CommandType Application).Source # Local: use the user's installed uv executable.
    $PlanSha256 = (Get-FileHash -LiteralPath $Plan -Algorithm SHA256).Hash # Global: bind the worker to these reviewed bytes.
    $repairPreflight = & $UvPath run --frozen --project $repairRepo @repairEnvArgs codex-project-repair apply --plan $Plan --plan-sha256 $PlanSha256 --check-only # Global: perform no app-state mutation while validating.
    if ($LASTEXITCODE -ne 0) { throw 'Preflight failed; nothing scheduled' } # Local: reject invalid plans before registering a task.
    $repairConfig = ($repairPreflight -join "`n") | ConvertFrom-Json # Local: parse only stdout JSON, not diagnostic stderr.
    $ProfileHome, $ReportRoot = $repairConfig.home, $repairConfig.output # Global: pin the preflight-resolved configuration across process environments.
}
$repairHasher = [Security.Cryptography.SHA256]::Create() # Local: derive a stable task name without exposing profile paths.
try { $repairDigest = $repairHasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($ProfileHome.ToLowerInvariant())) } finally { $repairHasher.Dispose() } # Global: release the hash provider.
$repairIdentity = ([BitConverter]::ToString($repairDigest)).Replace('-', '').ToLowerInvariant().Substring(0, 16) # Local: use a compact deterministic identity.
$TaskName = 'CodexProjectRepair-' + $(if ($SmokeTest) { 'Smoke-' }) + $repairIdentity # Global: one temporary registration per profile and mode.
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) { throw "A task already exists: $TaskName; inspect it before retrying" } # Global: never overwrite another active worker.
$repairArguments = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -Worker -TaskName "{1}" -ReportRoot "{2}"' -f $PSCommandPath, $TaskName, $ReportRoot # Local: Windows paths cannot contain quotation marks.
if ($SmokeTest) { $repairArguments += ' -SmokeTest'; if ($SimulateFailure) { $repairArguments += ' -SimulateFailure' } } else { $repairArguments += ' -Plan "{0}" -UvPath "{1}" -ProfileHome "{2}" -PlanSha256 "{3}"' -f $Plan, $UvPath, $ProfileHome, $PlanSha256 } # Global: no plan contents are injected as executable shell text.
$repairAction = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument $repairArguments -WorkingDirectory $repairRepo # Local: launch a hidden scheduler-owned worker.
$repairPrincipal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited # Global: no elevation or stored password.
$repairSettings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 35) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew # Local: bound work and avoid interruption merely from unplugging.
Register-ScheduledTask -TaskName $TaskName -Action $repairAction -Principal $repairPrincipal -Settings $repairSettings -Description 'One-time reviewed Codex project repair; no recurring or startup trigger; self-removes.' | Out-Null # Global: no recurring or login schedule is installed.
try { Start-ScheduledTask -TaskName $TaskName } catch { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false; throw } # Local: undo only this newly created registration if launch fails.
[pscustomobject]@{ task = $TaskName; reportRoot = $ReportRoot; state = 'launch_requested' } | ConvertTo-Json # Global: actual waiting readiness must be observed in status.json.
