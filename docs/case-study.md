# One Windows Native recovery

## Observation and hypothesis

On 2026-10-22, the user reported that selecting an existing Windows folder produced “failed to create this project” and confirmed Windows Native execution. A private pre-repair desktop log at **17:55:44.537 UTC** identified package **26.1016.8120.0** and the following error (paths, stack details, and identifiers omitted):

```text
[host-app-server-projects] Local app-server assignment sync failed
Invalid request: AbsolutePathBuf deserialized without a base path
```

The reviewed legacy project inventory contained five selected Linux-root entries. The working hypothesis was that these roots interfered with native project migration. In the [pinned public `AbsolutePathBuf` source](https://github.com/openai/codex/blob/a3d93e1e692f1144cf8685175a5d1f6bf7294f57/codex-rs/utils/absolute-path/src/lib.rs#L344-L350), deserialization produces this error when no base is available and the path is not absolute on the executing platform. That source explains a possible mechanism; it does not establish the exact code packaged in this desktop build or prove the cause of this case.

The observation is **consistent with** the [earlier Windows Native report](https://github.com/openai/codex/issues/41290#issuecomment-6066451501). That author described a stale Linux root, the same generic deserialization error, and chat visibility problems after broad root rewriting. Their eventual intervention removed an obsolete project entry. Our intervention below preserved project containers instead. Neither report proves identical causation. The [original issue](https://github.com/openai/codex/issues/41290) concerns a WSL-mode regression; this case was in Windows Native mode.

## Targeted intervention

The original helper observed desktop process absence, copied the exact JSON bytes, and created a SQLite snapshot before replacing the JSON. Four explicitly reviewed Linux roots became WSL UNC paths checked for accessibility; one root checked as missing became `[]`. Project containers and legacy chat associations were retained. The helper opened the source SQLite database read-only and sent no SQL updates to it.

Those four destination paths were reviewed inputs to the original helper. The later reusable tool's automatic `wslpath` resolution was **not** the implementation used for this live intervention. Its generalized planning and lifecycle code was subsequently exercised on synthetic fixtures; it was not reapplied to the repaired profile. See the [version-pinned reusable storage code](https://github.com/BurnyCoder/codex-windows-project-repair/blob/beb1ee53adb611377a92311da47fa7b98a942445/src/codex_windows_project_repair/storage.py) for the published transformation and backup implementation, not independent proof of the private run.

An initial detached-worker attempt did not complete according to the user's report and retained status evidence. The retained evidence does not establish how or why it terminated. A later one-time, current-user Task Scheduler run recorded backup and commit at approximately **18:39:42–18:39:43 UTC**, requested reopening, and completed cleanup. No claim about Codex killing a process tree is needed to explain these observations.

## Recorded outcome

The baseline backup was taken at **18:39:42.737293 UTC**. Its JSON checksum matched its manifest and its SQLite snapshot passed `quick_check`. A separate read-only comparison at **20:18:29.879098 UTC** recomputed the preservation results below. All times in this document refer to **2026-10-22 UTC**.

| Evidence | Result and scope |
| --- | --- |
| User's subsequent message | **“Works now!”** — the basis for reporting recovered project creation; no automated UI verification was performed |
| Private startup log, 18:39:49.156 | `Local app-server project migration completed projectCount=31`; this event does not establish full assignment migration |
| Legacy project ID comparison | All **31** baseline IDs remained |
| Legacy assignment comparison | All **130** baseline keys remained with unchanged decoded JSON values |
| SQLite `threads` ID comparison | **Zero missing original IDs among 436** baseline IDs |
| SQLite `projects` ID comparison | **Zero missing original IDs among 26** baseline IDs |
| Five desktop log files with entries in 18:39:45.934–20:18:29.863 | No project assignment-sync failure was found in this inspected post-repair window |
| Later entries in that same window | `fs/watch` requests logged `AbsolutePathBuf deserialized without a base path`, beginning at **19:08:03.782** |

The repair therefore does **not** establish that all path-related failures were resolved. Assignment-sync failures and later filesystem-watch errors are distinct observations, even when they share generic error text. Historical post-repair totals previously quoted here are omitted because their timestamped snapshots were not retained for independent reconstruction. The comparisons above check original identities rather than relying on increased totals.

The live-case sources are **private logs, the original plan/helper records, the baseline snapshots, the later read-only comparison, and the user's messages**. Only sanitized counts and excerpts are published. Public implementation, tests, and this narrative do not independently prove those private observations; readers cannot reconstruct the live comparison from this repository. The [claim-to-evidence table](validation.md#claim-to-evidence) distinguishes these evidence types.

## Limits of the evidence

This is one intervention on one installation, without controls or separate ablations of the five changes. Temporal recovery is consistent with the hypothesis but does not identify which entry was necessary or sufficient. Other desktop versions and multi-root layouts remain unverified or unsupported as described in the [README scope](../README.md#scope-and-implementation).

Record presence does not prove that every database field or external conversation file is unchanged, or that every historical chat appears under its expected project in the UI. Pending assignment-migration metadata was still present in the later read-only inspection. Complete assignment migration and UI/history grouping were not established. Filesystem accessibility can also change after inspection.

The upstream recommendation is to handle invalid legacy entries individually, provide actionable errors, and preserve history/associations while allowing unrelated project creation. This is a proposal, not an implemented upstream fix. The [contribution policy](https://github.com/openai/codex/blob/main/docs/contributing.md), checked on 2026-10-22, directs outside findings to issues/discussion rather than unsolicited code PRs. This repository audit leaves the existing upstream comment unchanged.
