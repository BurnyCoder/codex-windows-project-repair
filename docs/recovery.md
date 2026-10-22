# Recovery and scheduler troubleshooting

Read `status.json` and match its timestamp to the current launch. In the [application workflow](../src/codex_windows_project_repair/workflow.py), `waiting_for_codex_to_close` means the worker has reached its process-absence wait; quit normally when ready. `applied` means the JSON replacement was verified; `already_applied` means no further state write was needed. A written `failed` report includes an error and any completed backup manifest. Earlier CLI or mutex failures may leave no new report, and writing a report can itself fail. A successful launch request is not evidence that a worker started or the desktop reopened.

## Failure before a verified commit

Inspect `repair-*.log`, `launcher-*.log`, terminal errors, and Task Scheduler status as available. [Logging has gaps](design.md#logging-and-status), particularly before setup and on timeouts. Detected access failures, changed roots, WSL errors, unsupported layouts, failed backups, or an observed running desktop block the commit. A partial backup directory without a completed, verified manifest is not a recovery checkpoint. Diagnose the reported cause and create a fresh plan when assumptions changed.

If a final write/verification error occurred, inspect both current state and the completed backup. A `failed` report after commit began does not guarantee an unchanged target. Microsoft documents [ReplaceFileW failure states](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew) that can change names/content or leave the original target missing. Preserve what remains and use the separate verified backup when recovery is needed. [The helper](../src/codex_windows_project_repair/storage.py) does not automatically roll back, because that could overwrite a concurrent edit.

## Restore the JSON only when needed

1. Fully quit Codex and confirm the repair worker has finished. Do not restore while a worker is waiting to apply.
2. Preserve a separate copy of the **current** JSON, if present, and any new diagnostics before changing anything again. Choose a new, private filename; do not overwrite an earlier backup.
3. Select the intended backup directory from its manifest. Confirm its `source_home` is your profile. Compute `Get-FileHash -Algorithm SHA256 -LiteralPath 'BACKUP/.codex-global-state.json'` and compare it with `state_sha256` in that manifest.
4. After checking the exact source and destination paths, restore the verified `.codex-global-state.json` bytes to that profile. Restoring an older JSON file also restores its old sidebar/preferences/assignment state, so it can undo later changes. Retain the pre-restore copy.
5. Reopen Codex and inspect project creation, history visibility, and logs. The original bad roots may reintroduce the original symptom; restoration is recovery, not an alternative repair.

The tool never writes to the source SQLite database, so **do not replace it merely to undo this JSON repair**. A database rollback can discard newly created chats and must account for SQLite WAL/SHM state. Keep the consistent SQLite snapshot as recovery evidence for a separately assessed history problem. Do not delete the profile, sessions directory, or project records to address this symptom.

## Task cleanup

The launcher prints the exact task name. Inspect that task in Windows Task Scheduler or with `Get-ScheduledTask -TaskName 'EXACT-TASK-NAME'`. The wrapper attempts unregistration in `finally` after success, timeout, or failure; the cleanup command can itself fail. Forced termination, the 35-minute execution cap, sign-out, or power loss can prevent cleanup. A duplicate launch refuses an existing registration.

If the worker is still waiting, close Codex when ready or let its 30-minute wait expire. Do not force-stop a worker during backup or commit. Once you have established that the worker is finished and its state is understood, a leftover **exact** registration can be removed with:

```powershell
Unregister-ScheduledTask -TaskName 'EXACT-TASK-NAME' -Confirm:$false
```

There is no automatic boot/login retry. This launcher requires the current user to remain signed in and Task Scheduler access permitted by local policy. Do not elevate the repair to bypass a local policy. If scheduling is unavailable, run the documented direct `apply` command from a separate native PowerShell window after fully quitting Codex.

Microsoft documents [task inspection](https://learn.microsoft.com/powershell/module/scheduledtasks/get-scheduledtask) and [removing a registration](https://learn.microsoft.com/powershell/module/scheduledtasks/unregister-scheduledtask). The tool's cleanup attempt is implemented in [schedule-repair.ps1](../scripts/schedule-repair.ps1).
