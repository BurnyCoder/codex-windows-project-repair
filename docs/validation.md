# Validation record

Local validation on 2026-10-22 used native Windows, Python 3.14.2, the project-local uv environment, and PowerShell 5.1. All data fixtures were synthetic and confined to the checkout. The repaired real profile was not repaired again.

| Check | Observed result |
| --- | --- |
| Original storage regression cases | All seven retained and passing |
| Full Python suite | 23 tests passed |
| Installed console entry point | `codex-project-repair --help` succeeded |
| Packaging | Source distribution and wheel built successfully |
| Scheduler success integration | Independent launcher exited; fixture worker completed; duplicate registration refused; registration removed; input sentinel unchanged |
| Scheduler injected-failure integration | Failure branch executed; duplicate registration refused; registration removed; input sentinel unchanged |

The scheduler tests intentionally use a space in the disposable output path to exercise quoting. They schedule the production wrapper's explicitly isolated smoke branch; they do not invoke the real-profile repair. Their private transcript files remain ignored. Python workflow tests use actual JSON, SQLite snapshots, `ReplaceFileW`, and named mutexes, with synthetic app/WSL observations.

Test-driven changes included a failing unsupported-database-schema case followed by a preflight schema guard. The first scheduler smoke assertion treated an unavailable `Process.ExitCode` as failure despite a successful worker result; using `Start-Process -Wait -PassThru` made launcher completion/exit-status observation reliable in the tested PowerShell environment. The corrected integration checks then passed for success and intentional worker failure.

Windows CI runs the Python suite, entry-point check, and build. Its authoritative results are in [GitHub Actions](https://github.com/BurnyCoder/codex-windows-project-repair/actions/workflows/windows.yml). Interactive scheduler checks are separate from CI, because the launcher requires a signed-in interactive user.

The [case study](case-study.md) contains the separate live-repair observations. Passing fixture tests does not establish universal compatibility or prove historical chat visibility in the desktop UI.
