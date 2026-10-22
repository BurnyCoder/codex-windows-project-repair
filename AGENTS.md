# Maintainer guidance

Use native Windows, Python 3.14, uv, and the local environment. Keep the public CLI as a wrapper over named phases; isolate Windows calls from pure state transformations. Preserve the existing seven regression cases and add a failing safety-contract test before a behavioral fix.

Never test application on a developer's real Codex profile. Use disposable synthetic JSON and SQLite fixtures. Do not weaken backup verification, process guards, plan/profile binding, or explicit project selection to make a test pass. No source-database writes belong in the repair.

Keep all runtime data under ignored directories. Before publishing, inspect the staged diff and Git history for private paths, identifiers, databases, logs, credentials, and accidental author emails. Use synthetic labels in examples. Never upload real diagnostic or backup files.

Update the relevant documentation when behavior changes. Keep usage in README, implementation rationale in docs/design.md, recovery in docs/recovery.md, and observed evidence in docs/case-study.md or docs/validation.md. Do not turn one successful case into a compatibility claim. Link implementation choices to primary references and explain safety-relevant code locally.

Run the documented validation commands for relevant changes. Scheduler integration requires an interactive Windows session and temporary tasks; inspect completion and cleanup. Review correctness, preservation, security, and failure paths once, fix substantive findings, then publish through a feature PR with passing Windows CI.
