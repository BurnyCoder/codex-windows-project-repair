# Windows Codex project repair

[![Windows validation](https://github.com/BurnyCoder/codex-windows-project-repair/actions/workflows/windows.yml/badge.svg)](https://github.com/BurnyCoder/codex-windows-project-repair/actions/workflows/windows.yml)

An unofficial, targeted repair for **Windows Native** Codex Desktop profiles whose legacy Linux project roots block project creation. It previews explicit project selections, resolves their folders through your chosen WSL distribution, waits for Codex to close, verifies fresh backups, and changes only the selected `rootPaths` arrays. It never updates the source chat database.

One installation recovered project creation after this repair; startup logged migration of 31 projects and every checked pre-repair project/chat ID remained present. This is evidence for one case, **not universal compatibility**. See the [sanitized case study](docs/case-study.md) for the observations and remaining uncertainty.

## Install and diagnose

Run these commands in **native Windows PowerShell**, using your regular Windows account. Install [Git](https://git-scm.com/downloads/win) and [uv](https://docs.astral.sh/uv/getting-started/installation/) first. `uv sync` installs Python 3.14 if needed and creates a local `.venv`.

```powershell
git clone https://github.com/BurnyCoder/codex-windows-project-repair.git
cd codex-windows-project-repair
uv sync --frozen --python 3.14
Copy-Item .env.example .env
uv run --frozen --env-file .env codex-project-repair inspect
```

`inspect` reads the legacy project inventory and discovers the installed desktop package and registered WSL distributions. It reports IDs, names, roots, and candidate status without writing profile data or report files. `linux_root` means a supported *shape*, not proof that the entry caused your error. Other records remain visible as `not_a_supported_repair_target`.

This workaround addresses the following observed log error when selecting an ordinary Windows project folder:

```text
[host-app-server-projects] Local app-server assignment sync failed
Invalid request: AbsolutePathBuf deserialized without a base path
```

Check [Codex's Windows troubleshooting documentation](https://learn.chatgpt.com/docs/windows/windows-app) and the [related Windows Native report](https://github.com/openai/codex/issues/41290#issuecomment-6066451501). A generic “failed to create this project” message alone does not establish this cause. The original issue also describes a separate WSL-mode regression.

## Preview, apply, verify

Replace the example values below with an ID and the exact distribution name reported by `inspect`. Repeat `--project` for each project you intentionally select.

```powershell
uv run --frozen --env-file .env codex-project-repair plan --project "PROJECT-ID" --distro "YOUR-DISTRIBUTION"
Get-Content .local/plan.json
uv run --frozen --env-file .env codex-project-repair apply --plan .local/plan.json --check-only
```

Review each old root and proposed Windows path. An existing directory is translated by that distribution's `wslpath -w` and checked from Windows. Inaccessible parents, WSL failures, files, and broken symlinks block the plan. A verified missing directory also blocks it unless you explicitly add **`--detach-missing`**. Detachment sets that selected project's roots to `[]`; the project container, ordering, and chat associations remain. It deletes no folder or project record. An absent parent is treated conservatively as unverifiable, even when it might itself have been deleted.

Plans are never overwritten. Use `--save .local/another-plan.json` for a new preview. Regenerate a plan if folder availability changes. The scheduled worker checks its SHA-256 to reject edits made after scheduling.

To apply through Task Scheduler, run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/schedule-repair.ps1 -Plan .local/plan.json
Get-Content .local/status.json
```

The launcher returns a task name and `launch_requested`. **Wait until the current worker's status says `waiting_for_codex_to_close`, then fully quit Codex.** Match the status timestamp to this launch; an old status file is not evidence that a new worker started. See `.local/launcher-*.log` if it never becomes ready. Keep this checkout and its `.venv` in place until the worker finishes.

The task runs once as the current user, without elevation or a saved password. It waits up to 30 minutes for a sustained exit, rechecks the plan, backs up JSON and SQLite, verifies the backups, and replaces the JSON file using Windows `ReplaceFileW`. It then requests reopening through the discovered app registration and removes its task registration. `applied` means the JSON change succeeded; `reopen_requested` does not prove the app opened. If it does not reopen, open Codex normally and inspect `status.json`.

Alternatively, fully quit Codex and run this from a **separate PowerShell window**:

```powershell
uv run --frozen --env-file .env codex-project-repair apply --plan .local/plan.json --reopen
```

Do not rely on a detached child launched by Codex to survive Codex's shutdown. That approach failed in the observed case; the scheduler-owned worker succeeded.

After reopening, use the exact backup directory reported in `status.json`:

```powershell
uv run --frozen --env-file .env codex-project-repair verify --backup ".local/backups/BACKUP-TIMESTAMP"
```

`verify` checks backup hashes, preservation of legacy project IDs and prior chat associations, and missing IDs in the database's `threads` and `projects` tables. New records are allowed; equal counts cannot hide a missing old ID. Exit codes are `0` for success, `1` for an execution/validation error, and `2` for a preservation mismatch. Verification always reports `needs_ui_verification`: try adding a Windows project, inspect startup logs, and check your historical chats in the UI yourself.

## Configuration and recovery

The optional `.env` contains `CODEX_REPAIR_HOME` and `CODEX_REPAIR_OUTPUT`. Blank values use `CODEX_HOME` or the current user's `.codex` directory, and `.local` under the current working directory, respectively. Use absolute paths with forward slashes for overrides. The global `--home` and `--output` options, placed before a command, override these defaults. The scheduler loads the checkout's `.env` and pins its resolved profile/output paths during preflight.

Plans, backups, status, and logs contain private metadata. They belong under the ignored `.local` directory, outside the Codex profile. Keep them private. The SQLite backup contains sensitive chat metadata; it is not a backup of every external rollout file or project working tree. The tool has no LLM calls or external telemetry. Operational commands log complete diagnostics to timestamped local files and stderr; `inspect` and `verify` print read-only results.

See [recovery and scheduler troubleshooting](docs/recovery.md) before manually restoring anything. No automatic database restore is performed.

## Scope and implementation

| Area | Supported / tested scope |
| --- | --- |
| Desktop | Observed successful case: Windows package `26.1016.8120.0`, Windows Native mode. Other desktop versions are unverified. |
| Installation | One discoverable `OpenAI.Codex` MSIX registration with a `ChatGPT.exe` or `Codex.exe` application. Package version and AppUserModelID are discovered. |
| State | `.codex-global-state.json` with dictionary-valued `local-projects` and `thread-project-assignments`; selected records have matching IDs and one normalized absolute Linux root. |
| History | `state_5.sqlite` with `threads.id` and `projects.id`; opened read-only by the tool. |
| Runtime | Native Windows, Python 3.14, uv, PowerShell 5.1 or later, Windows Task Scheduler, and a usable selected WSL distribution providing `/usr/bin/test` and `wslpath`. |
| Exclusions | Multi-root selections, unknown layouts, Linux-host execution, missing/ambiguous desktop installations, and inaccessible filesystem paths are refused. |

Features include explicit selection, strict JSON parsing, read-only diagnosis, consistent SQLite snapshots, backup checksums, repeat-application protection, concurrent-edit checks, duplicate-worker exclusion, and metadata-preserving JSON replacement. Python's standard library implements the repair; uv manages packaging/configuration, and PowerShell handles scheduling.

![Repair phases and data boundaries](docs/architecture.svg)

`cli.py` is the command wrapper; `planning.py` validates and builds proposals, `windows.py` handles OS observations, `storage.py` transforms and backs up data, and `workflow.py` coordinates application and verification. The scheduler reuses the same `apply` command. See [design, limitations, and sources](docs/design.md).

## Validate a checkout

```powershell
uv run --frozen python -m unittest discover -s tests -v
uv build
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/scheduler-smoke.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/scheduler-smoke.ps1 -SimulateFailure
```

The Python suite retains the original seven repair tests and adds planning, failed-backup, unsupported-schema, inaccessible-path, timeout, record-identity, and duplicate-worker cases. Windows CI runs the suite, CLI entry-point check, and package build. Scheduler checks run separately in an interactive Windows session using disposable fixtures; they test launcher exit, duplicate registration refusal, cleanup on success/failure, and sentinel preservation. Neither suite repairs your actual profile. See the [validation record](docs/validation.md).

MIT licensed. This community utility is not an OpenAI product or a supported desktop migration API.
