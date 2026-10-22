# One Windows Native recovery

## Observation and hypothesis

On 2026-10-22, selecting an existing ordinary Windows folder produced “failed to create this project” in Codex Desktop package **26.1016.8120.0**, configured for **Windows Native** execution. Startup/assignment logs reported:

```text
[host-app-server-projects] Local app-server assignment sync failed
Invalid request: AbsolutePathBuf deserialized without a base path
```

The legacy project dictionary contained five selected Linux-root entries. The working hypothesis was that those paths blocked native project migration. The public [`AbsolutePathBuf` implementation](https://github.com/openai/codex/blob/a3d93e1e692f1144cf8685175a5d1f6bf7294f57/codex-rs/utils/absolute-path/src/lib.rs) explains the error when a path is not absolute for the current platform and no base path is available; it does not by itself prove every desktop migration detail.

An existing [Windows Native workaround report](https://github.com/openai/codex/issues/41290#issuecomment-6066451501) had identified the same legacy-path symptom. That report also described chat visibility problems after broad root rewriting. We therefore retained every project container and chat association and restricted edits to reviewed roots. This case differs from #41290's original WSL-mode regression; it does not establish that the earlier regression returned.

## Targeted intervention

The helper waited for the desktop to exit, backed up the exact JSON bytes and a consistent SQLite snapshot, then replaced four existing Linux roots with accessible Windows WSL UNC paths. One verified missing directory was detached by setting its project's `rootPaths` to `[]`. No project record was deleted. The source SQLite database was not updated by the helper.

A detached subprocess initially failed to survive the app shutdown. A one-time, current-user Windows Task Scheduler worker completed the repair, requested reopening, and removed its registration. The reusable tool generalizes that launcher and the tested storage operations; its generalized code was subsequently tested on synthetic fixtures, not reapplied to this repaired profile.

## Recorded outcome

| Evidence | Result |
| --- | --- |
| User's subsequent project-creation attempt | Reported working |
| Startup log at 18:39:49.156 UTC | `Local app-server project migration completed projectCount=31` |
| Legacy project ID set | All 31 prior IDs remained |
| Legacy chat-to-project assignments | All 130 prior entries unchanged |
| SQLite `threads` ID set | All 436 pre-repair IDs remained; post-repair count 442 |
| SQLite `projects` ID set | All 26 pre-repair IDs remained; post-repair count 33 |
| Four inspected post-repair desktop logs | No matching assignment-sync / `AbsolutePathBuf` failures |

ID-set comparisons, rather than increased counts alone, established the reported record preservation. These figures are sanitized summaries of private before/after snapshots, helper status, and desktop logs inspected during the repair. Those private artifacts and conversation identifiers are deliberately not published; outsiders cannot independently reconstruct this live case from the repository.

## Limits of the evidence

This was one intervention on one installation, without randomized controls or separate ablations of the five root changes. The temporal recovery and migration log support the proposed mechanism, but do not establish which individual entry was necessary or sufficient. Synthetic tests check preservation contracts; they do not establish compatibility with every desktop version or profile.

Record existence does not prove that every historical chat is visible under its expected project in the UI, nor that every field of every database record is unchanged. Pending legacy assignment migration metadata was still observed, so this case does **not** establish full assignment-migration completion. WSL folders can also become inaccessible later. The utility leaves these checks explicit rather than reporting complete UI recovery automatically.

The upstream recommendation is to isolate invalid legacy entries, provide actionable errors for each, and preserve history/associations while allowing unrelated project creation to proceed. This is a proposed product behavior, not a claim about an implemented upstream fix. Findings are contributed through discussion under the repository's [current contribution policy](https://github.com/openai/codex/blob/main/docs/contributing.md).
