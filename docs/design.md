# Design and source references

The command wrapper delegates to independent configuration, planning, Windows, storage, and workflow modules. The live transformation is a deep copy with only explicitly selected `rootPaths` replaced. Unknown fields, legacy project records, and associations survive that transformation by construction; the preservation tests reverse the permitted edit and require equality with the original fixture.

## Boundaries

1. **Diagnosis and proposal:** strict JSON decoding rejects duplicate keys and nonstandard numeric constants. Only a dictionary-shaped legacy layout and single-root selected projects are understood. No path rewrite is inferred from a project name.
2. **Filesystem evidence:** `wsl.exe -d <selected> --exec` receives separate arguments. The chosen distribution tests parent traversal and directory existence. Its `wslpath` output must be absolute and accessible from Windows. An error cannot become a “missing” result.
3. **Worker lifecycle:** a named Windows mutex excludes other workers in the same Windows session for the resolved profile. A deterministic, profile-derived task name and Task Scheduler's `IgnoreNew` setting also prevent duplicate registrations/instances. The task has no recurring or login trigger and runs with an interactive, limited principal. The Python shutdown wait expires after 30 minutes; Task Scheduler has a separate 35-minute hard execution cap to accommodate startup and cleanup.
4. **Backup:** the original JSON bytes are copied and verified. Python's SQLite backup API creates a consistent snapshot, including committed WAL data, through a read-only source connection. `quick_check` validates the destination; both files receive SHA-256 digests in a manifest. No SQL updates are sent to the source.
5. **Commit:** after another closure check and byte-for-byte concurrent-change check, a flushed temporary JSON file replaces the original through `ReplaceFileW`. Normal Windows metadata merge checks stay enabled. Other JSON values retain their meaning, although whitespace/formatting changes.
6. **Verification:** backup hashes and original record-ID subsets are checked. Earlier legacy associations must still have their original values. UI and desktop migration completion remain separate observations.

The scheduler pins plan bytes with a digest and pins resolved paths after preflight. Keep the checkout, `.env`, Python environment, and plan trusted and unchanged while it waits. This is a local administrative workflow, not a security boundary against another process running as the same user.

The tool does not take an exclusive lock on all Codex state. A process can restart between observations; byte comparisons and a final process check reduce that race but cannot mathematically eliminate it. Keep Codex closed through application. Database and JSON snapshots are not one cross-file transaction; app closure is required for the intended quiescent state. The process-name guard is conservative and can also wait on another application using the same executable name. Windows session isolation, abrupt power loss, forced task termination, and future internal-schema changes are outside the proven lifecycle guarantees.

## Primary references

| Mechanism or context | Source |
| --- | --- |
| Windows execution modes and troubleshooting | [Codex Windows app documentation](https://learn.chatgpt.com/docs/windows/windows-app) |
| Existing Native-mode workaround and its limits | [openai/codex#41290 comment](https://github.com/openai/codex/issues/41290#issuecomment-6066451501) |
| Platform-sensitive absolute-path deserialization | [Codex `AbsolutePathBuf` source](https://github.com/openai/codex/blob/a3d93e1e692f1144cf8685175a5d1f6bf7294f57/codex-rs/utils/absolute-path/src/lib.rs) |
| Standard-library JSON decoding | [Python 3.14 JSON documentation](https://docs.python.org/3.14/library/json.html) |
| SQLite snapshots | [Python `Connection.backup`](https://docs.python.org/3.14/library/sqlite3.html#sqlite3.Connection.backup), [SQLite backup API](https://www.sqlite.org/backup.html) |
| File metadata during replacement | [Microsoft `ReplaceFileW`](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew) |
| Worker lifetime guard | [Microsoft `CreateMutexW`](https://learn.microsoft.com/windows/win32/api/synchapi/nf-synchapi-createmutexw) |
| Package discovery | [Microsoft `Get-AppxPackageManifest`](https://learn.microsoft.com/powershell/module/appx/get-appxpackagemanifest) |
| Explicit WSL selection and command execution | [Microsoft WSL basic commands](https://learn.microsoft.com/windows/wsl/basic-commands) |
| Path translation | [Microsoft WSL interop documentation](https://learn.microsoft.com/en-us/windows/dev-environment/wsl-interop) |
| Task registration and privileges | [Register-ScheduledTask](https://learn.microsoft.com/powershell/module/scheduledtasks/register-scheduledtask), [New-ScheduledTaskPrincipal](https://learn.microsoft.com/powershell/module/scheduledtasks/new-scheduledtaskprincipal) |
| Hidden external launcher | [Start-Process](https://learn.microsoft.com/powershell/module/microsoft.powershell.management/start-process) |
| Project environment and configuration | [uv projects](https://docs.astral.sh/uv/guides/projects/), [uv environment files](https://docs.astral.sh/uv/concepts/configuration-files/#environment-variable-files) |
| Upstream contribution route | [Codex contribution policy](https://github.com/openai/codex/blob/main/docs/contributing.md) |

These APIs support the implementation choices. None constitutes a supported public API for editing Codex's internal desktop state.
