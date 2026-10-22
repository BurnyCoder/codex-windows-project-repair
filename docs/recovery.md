# Recovery and scheduler troubleshooting

Read the current `status.json` and its timestamp first. `waiting_for_codex_to_close` means the worker is ready for orderly exit; `applied` means the JSON replacement was verified; `already_applied` means no further state write was needed. `failed` includes an error and any completed backup manifest. A successful launch request is not evidence that a worker started or the desktop reopened.

## Failure before a verified commit

Inspect the full `repair-*.log` and `launcher-*.log` in the selected output directory. Missing permissions, changed roots, WSL failures, unsupported layouts, failed backups, or a still-running desktop block the write. A partially created backup directory without a completed, verified manifest is not a recovery checkpoint. Do not blindly rerun an old plan; diagnose the reported cause and create a fresh plan when assumptions changed.

If a final write/verification error occurred, inspect both current state and the completed backup. A `failed` report after the commit began does not guarantee the live file stayed unchanged. The helper deliberately avoids an automatic rollback that could overwrite a concurrent app edit.

## Restore the JSON only when needed

1. Fully quit Codex and confirm the repair worker has finished. Do not restore while a worker is waiting to apply.
2. Preserve a separate copy of the **current** JSON and any new diagnostics before changing it again. Choose a new, private filename; do not overwrite an earlier backup.
3. Select the intended backup directory from its manifest. Confirm its `source_home` is your profile. Compute `Get-FileHash -Algorithm SHA256 -LiteralPath 'BACKUP/.codex-global-state.json'` and compare it with `state_sha256` in that manifest.
4. After checking the exact source and destination paths, restore the verified `.codex-global-state.json` bytes to that profile. Restoring an older JSON file also restores its old sidebar/preferences/assignment state, so it can undo later changes. Retain the pre-restore copy.
5. Reopen Codex and inspect project creation, history visibility, and logs. The original bad roots may reintroduce the original symptom; restoration is recovery, not an alternative repair.

The tool never writes to the source SQLite database, so **do not replace it merely to undo this JSON repair**. A database rollback can discard newly created chats and must account for SQLite WAL/SHM state. Keep the consistent SQLite snapshot as recovery evidence for a separately assessed history problem. Do not delete the profile, sessions directory, or project records to address this symptom.

## Task cleanup

The launcher prints the exact task name. Inspect that task in Windows Task Scheduler or with `Get-ScheduledTask -TaskName 'EXACT-TASK-NAME'`. Normal success, timeout, and handled failures unregister it. A forced process termination, hard execution cap, sign-out, or power loss can bypass `finally`, leaving a registration. A duplicate launch refuses to overwrite it.

If the worker is still waiting, close Codex when ready or let its 30-minute wait expire. Do not force-stop a worker during backup or commit. Once you have established that the worker is finished and its state is understood, a leftover **exact** registration can be removed with:

```powershell
Unregister-ScheduledTask -TaskName 'EXACT-TASK-NAME' -Confirm:$false
```

There is no automatic boot/login retry. This launcher requires the current user to remain signed in and Task Scheduler access permitted by local policy. Do not elevate the repair to bypass a local policy. If scheduling is unavailable, run the documented direct `apply` command from a separate native PowerShell window after fully quitting Codex.

Microsoft documents [task inspection](https://learn.microsoft.com/powershell/module/scheduledtasks/get-scheduledtask) and [removing a registration](https://learn.microsoft.com/powershell/module/scheduledtasks/unregister-scheduledtask). The tool's normal cleanup is implemented in `scripts/schedule-repair.ps1`.
