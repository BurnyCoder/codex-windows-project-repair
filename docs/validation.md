# Validation record

## Revisions and environments

The independent repository audit on **2026-10-22** began at [`dcaf1c0ed23f20c65e61bf3f4811c12fc4c7ebaf`](https://github.com/BurnyCoder/codex-windows-project-repair/commit/dcaf1c0ed23f20c65e61bf3f4811c12fc4c7ebaf), the merge of [PR #1](https://github.com/BurnyCoder/codex-windows-project-repair/pull/1). Fresh baseline execution passed all **24** tests. The seven original storage test methods were compared with the retained original helper tests by Python AST and matched. Their test logic remains intact in [test_storage.py](../tests/test_storage.py).

The behavior correction is [`37d89f6846784f346041eeb3a71acef5d02691f5`](https://github.com/BurnyCoder/codex-windows-project-repair/commit/37d89f6846784f346041eeb3a71acef5d02691f5). Local checks used **Windows 11 build 26200**, **CPython 3.14.2**, **uv 0.13.0**, a checkout-local `.venv`, and **PowerShell 7.6.5** as the invoking shell. This is separate from the historical scheduler runs under Windows PowerShell 5.1. No repair/scheduler worker was launched, no live-profile application was repeated, and Codex was not stopped or restarted for this correction audit.

## Current fixture checks

| Check | Observed result |
| --- | --- |
| Baseline suite at `dcaf1c0` | 24 passed in 0.550 s in the local audit environment |
| New mocked path regressions against the old implementation | Eight test methods ran; three methods failed, accounting for ten failed assertions/subtests |
| Suite after the path correction at `37d89f6` | **32 passed in 0.650 s**, including the original seven storage tests |
| Windows CI at `37d89f6` | [32 passed in 0.498 s](https://github.com/BurnyCoder/codex-windows-project-repair/actions/runs/39851569261/job/120078844202); CLI help and source/wheel builds passed |
| Installed CLI help | Root help and all four command help screens exited successfully without accessing a profile |
| Invalid CLI option | `codex-project-repair --audit-invalid-option` exited `2` before profile access |
| Packaging | `uv build` produced a source distribution and wheel |

The new tests were written and executed before changing production behavior. They exposed trailing space/NBSP loss, acceptance of malformed multiline output, and an executable regular-file parent incorrectly allowing an empty-root proposal. [The correction](https://github.com/BurnyCoder/codex-windows-project-repair/blob/37d89f6846784f346041eeb3a71acef5d02691f5/src/codex_windows_project_repair/windows.py) removes at most one LF/CRLF suffix, rejects remaining line breaks/empty output, and requires parent directory type as well as search permission. [The eight regression methods](https://github.com/BurnyCoder/codex-windows-project-repair/blob/37d89f6846784f346041eeb3a71acef5d02691f5/tests/test_windows.py) also cover no terminator, inaccessible parents/destinations, unexpected command status, and a legitimate missing-directory result. The prior broken-symlink fixture now supplies the extra parent-type predicate.

Commands used from the checkout (after the existing environment had been synchronized):

```powershell
uv run --frozen --no-sync python -B -m unittest discover -s tests -p test_windows.py -v
uv run --frozen --no-sync python -B -m unittest discover -s tests -v
uv run --frozen --no-sync codex-project-repair --help
foreach ($command in @('inspect', 'plan', 'apply', 'verify')) {
    uv run --frozen --no-sync codex-project-repair $command --help
}
uv build
git diff --check
```

Timestamped local command logs are private and ignored. Times above describe these runs, not performance benchmarks. Python tests use disposable JSON/SQLite and actual Windows replacement/mutex APIs while mocking app/WSL observations. The mutex test acquires the same name twice within one process; it does not establish cross-session exclusion. The suite does not exercise live WSL translation, actual project creation, every metadata field, or full chat-content/UI preservation.

The correction CI job used **Windows Server 2025**, **CPython 3.14.8**, and **uv 0.13.5**, as reported in its public logs. The workflow's `--python 3.14` selects an available interpreter in that series; it does not pin a patch release. Documentation/comment edits after `37d89f6` were checked by AST comparison to leave Python behavior unchanged, including all seven original test-method ASTs. Final PR checks validate the combined branch before merging.

## Historical CI and scheduler evidence

The [24-test Windows CI job](https://github.com/BurnyCoder/codex-windows-project-repair/actions/runs/39841505062/job/120043433330) ran at [`beb1ee53adb611377a92311da47fa7b98a942445`](https://github.com/BurnyCoder/codex-windows-project-repair/commit/beb1ee53adb611377a92311da47fa7b98a942445), before the merge commit audited here. Its logs report **24 tests in 0.318 s, OK**, CPython **3.14.9**, uv **0.13.5**, successful CLI help, and successful source/wheel builds. Its [pinned workflow](https://github.com/BurnyCoder/codex-windows-project-repair/blob/beb1ee53adb611377a92311da47fa7b98a942445/.github/workflows/windows.yml) contains the commands and action revisions. This is public execution evidence, unlike private local logs.

Retained private scheduler smoke records from earlier on 2026-10-22 include successful and intentionally failing fixture branches, unchanged input sentinels, and Windows PowerShell **5.1.26100.9711** transcripts. The four recorded task registrations were absent when inspected during the audit. These artifacts support the recorded fixture outcomes and later absence of those registrations; they do not independently prove every assertion in the smoke script completed in every attempt.

The [historical smoke script](https://github.com/BurnyCoder/codex-windows-project-repair/blob/beb1ee53adb611377a92311da47fa7b98a942445/tests/scheduler-smoke.ps1) contains assertions for launcher exit, duplicate registration refusal, success/failure output, task cleanup, and sentinel preservation. It uses a space-containing disposable path and the wrapper's isolated smoke branch, not the Python repair pipeline. Reading that code establishes intended coverage, not proof of a new execution. The earlier detached live helper's termination mechanism remains unknown, as explained in the [case study](case-study.md).

Scheduler integration was **not rerun in this audit**, in accordance with the request not to launch workers or interrupt Codex. The [current CI workflow](../.github/workflows/windows.yml) runs fixture tests, help, and packaging only; it registers no scheduled tasks.

## Publication checks

The audit checked Markdown relative-file links and heading targets, and fetched external documentation/source URLs with their HTML anchors. No unresolved targets remained in those checks. Referenced GitHub revisions, source files, issue evidence, and CI results were inspected through repository data. The architecture SVG parsed as XML; its labels were corrected to describe observed absence and read-only SQL connections.

Tracked files, the staged changes, reachable Git blob history, commit author addresses, and rebuilt wheel/source-distribution contents were reviewed for runtime artifacts and private data. Filename checks and pattern scans found no private profile path, conversation UUID, common credential token, or database/log/backup artifact in the checked publication inputs. This is a scoped review, not proof that an arbitrary secret detector can recognize every possible secret. Runtime logs and retained private case evidence remain outside Git. The original helper/backups and upstream issue comment were not changed.

## Claim-to-evidence

| Material claim | Evidence type and source | What it establishes / limitation |
| --- | --- | --- |
| Targeted root transformation, backups, original-ID and assignment checks | Public [storage](../src/codex_windows_project_repair/storage.py), [workflow](../src/codex_windows_project_repair/workflow.py), [storage tests](../tests/test_storage.py), [workflow tests](../tests/test_workflow.py) | Implemented contracts and their stated fixture coverage; not all record contents or UI grouping |
| Exact translation spelling and parent-type check | Public [regressions](../tests/test_windows.py); primary [Python suffix semantics](https://docs.python.org/3.14/builtins/stdtypes.html#str.removesuffix) and [GNU predicates](https://www.gnu.org/software/coreutils/manual/coreutils.html#test-invocation) | Reproduced logic defects and fixture correction; no claim that every WSL/filesystem variant was tested |
| Historical 24 passing tests | Public [CI job](https://github.com/BurnyCoder/codex-windows-project-repair/actions/runs/39841505062/job/120043433330) at `beb1ee5` | Observed execution on that CI revision/environment, not the later correction |
| Corrected 32-test suite | Public [CI job](https://github.com/BurnyCoder/codex-windows-project-repair/actions/runs/39851569261/job/120078844202) at `37d89f6` | Regression execution, help, and build; no live-profile or scheduler run |
| API behavior: backups, metadata, session namespace, CLI exit codes, buffering | Primary documentation linked in [design](design.md#primary-references), together with the implementation | API contracts and how the tool uses them; not live-case proof |
| Desktop version, startup event, preservation counts, later watch errors | Private original logs/snapshots and read-only recomputation, sanitized in [case study](case-study.md#recorded-outcome) | One installation and explicit timestamps/window; not independently reproducible from public files |
| Recovered project creation | Private user message “Works now!” | User-reported result, not an automated UI assertion |
| Linux roots caused this failure | Hypothesis consistent with the [earlier Native report](https://github.com/openai/codex/issues/41290#issuecomment-6066451501) and [pinned path implementation](https://github.com/openai/codex/blob/a3d93e1e692f1144cf8685175a5d1f6bf7294f57/codex-rs/utils/absolute-path/src/lib.rs#L344-L350) | Plausible explanation; no controlled causal isolation or proof of identical desktop internals |
| MIT licensing | Public [LICENSE](../LICENSE) and [package metadata](../pyproject.toml) | Repository licensing, not OpenAI endorsement |

Every evidence category has a different scope. Passing fixture checks does not establish universal compatibility, complete migration, or historical chat visibility.
