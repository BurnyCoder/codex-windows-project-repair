"""Local: coordinate validation, backup, application, and verification. Global: preserve history.

Sources: https://docs.python.org/3.14/library/sqlite3.html and https://docs.python.org/3.14/library/os.html
"""
import hashlib  # Local: verify backup integrity before using its evidence.
import json  # Local: emit complete, inspectable status documents.
import logging  # Global: retain audit events without dumping chat contents.
import os  # Local: atomically update only the helper's own reports.
import sqlite3  # Local: compare record identities through read-only connections.
import uuid  # Local: avoid collisions between temporary report filenames.
from contextlib import closing  # Global: release every database handle.
from datetime import datetime, timezone  # Local: make timestamps unambiguous.
from pathlib import Path  # Local: resolve manifests and snapshots precisely.
from .config import parse_json, read_json  # Global: one strict JSON parser.
from .planning import projects, validate_plan  # Local: require known profile and plan layouts.
from .storage import backup_state, build_repair, commit_state, validate_database  # Global: reuse the shared storage operations covered by fixture tests.
from .windows import assert_closed, discover_app, probe_root, reopen_app, single_worker, wait_for_exit  # Local: isolate Windows behavior.


def write_report(path, report):  # Global: helper reports never replace application files.
    """Local: write a unique temporary report; global: expose only complete JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)  # Local: create private runtime directories as needed.
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")  # Local: isolate concurrent report writes.
    try:  # Global: clean up only this invocation's temporary file.
        temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")  # Local: retain full report values.
        os.replace(temporary, path)  # Global: readers never see partial JSON.
    finally:  # Local: also clean up after a failed replacement.
        temporary.unlink(missing_ok=True)  # Global: never remove another worker's report.


def status(settings, stage, **details):  # Global: keep applied state distinct from UI success.
    """Local: report the current phase; global: leave useful recovery information after exit."""
    report = {"stage": stage, "pid": os.getpid(), "time_utc": datetime.now(timezone.utc).isoformat(), "home": str(settings.home), **details}  # Local: bind status to this profile and process.
    write_report(settings.output / "status.json", report)  # Local: use a predictable private report location.
    logging.info("Status: %s", json.dumps(report))  # Global: stream the full status to terminal and log.
    return report  # Local: CLI also prints structured results.


def preflight(settings, plan):  # Global: validate all requested changes before backup or commit.
    """Local: recheck schema, current roots, and WSL; global: reject stale assumptions."""
    validate_plan(plan, settings.home)  # Local: enforce schema and profile binding.
    state = read_json(settings.state)  # Global: reject duplicate keys and malformed JSON.
    projects(state)  # Local: require the observed legacy layout.
    build_repair(state, plan["changes"])  # Global: refuse changed project IDs or roots.
    if not (settings.home / "state_5.sqlite").is_file():  # Local: v1 requires the observed backup layout.
        raise ValueError("Unsupported profile: state_5.sqlite is missing")  # Global: never repair without its history backup.
    validate_database(settings.home / "state_5.sqlite")  # Local: fail before any repair if history cannot be verified.
    for change in plan["changes"]:  # Local: verify only the reviewed folders.
        actual = probe_root(plan["distro"], change["old_root"])  # Global: inaccessible folders fail rather than detach.
        if actual != change["new_roots"]:  # Local: compare the full proposed root array.
            raise ValueError(f"Folder availability or translation changed: {change['id']}")  # Global: require a new reviewed plan.
    return {"home": str(settings.home), "output": str(settings.output), "selected_projects": len(plan["changes"])}  # Local: expose launch configuration without chat contents.


def apply_plan(settings, plan, wait=False, reopen=False):  # Global: the sole high-level mutation entry point.
    """Local: execute guarded phases; global: preserve latest state and verified recovery data."""
    with single_worker(settings.home):  # Global: also exclude workers using a different output directory.
        backup = None  # Local: retain recovery details if a later phase fails.
        try:  # Global: attempt failure reporting after lock acquisition; early CLI/lock errors occur outside this block.
            preflight(settings, plan)  # Local: fail early before asking the user to quit.
            app = discover_app()  # Global: never guess which process owns app state.
            if wait:  # Local: the scheduler can run while the user finishes work.
                status(settings, "waiting_for_codex_to_close")  # Global: expose observable readiness.
                wait_for_exit(app["executable"])  # Local: require sustained observed process absence without forcing exit.
            assert_closed(app["executable"])  # Global: direct apply refuses an active desktop.
            preflight(settings, plan)  # Local: refresh filesystem assumptions after the wait.
            original = settings.state.read_bytes()  # Global: capture current bytes after the process observation.
            state = parse_json(original)  # Local: validate exactly the captured bytes used for backup and commit.
            if settings.state.read_bytes() != original:  # Global: reject an intervening writer before constructing the candidate.
                raise RuntimeError("State changed during validation")  # Local: require another attempt.
            candidate = build_repair(state, plan["changes"])  # Local: change only selected root arrays.
            if candidate == state:  # Global: repeated plans do not rewrite an already repaired profile.
                return status(settings, "already_applied", needs_ui_verification=True)  # Local: report idempotence accurately.
            assert_closed(app["executable"])  # Global: guard backup after filesystem checks.
            backup = backup_state(settings.state, settings.output / "backups", original)  # Local: exact JSON and consistent read-only database snapshot.
            commit_state(settings.state, original, candidate, lambda: assert_closed(app["executable"]))  # Global: compare current bytes and preserve Windows metadata at commit.
            report = status(settings, "applied", backup=backup, needs_ui_verification=True)  # Local: applying JSON does not establish UI success.
        except Exception as error:  # Global: never reopen after a failed or uncertain commit.
            status(settings, "failed", error=str(error), backup=backup)  # Local: retain any completed recovery snapshot.
            raise  # Global: return a nonzero result and full traceback.
        if reopen:  # Local: launch only after successful verified application.
            try:  # Global: a launch failure must not mislabel a successful state repair.
                reopen_app(app["app_id"])  # Local: use the discovered registration.
                report = status(settings, "applied", backup=backup, reopen_requested=True, needs_ui_verification=True)  # Global: distinguish a launch request from observed app readiness.
            except OSError as error:  # Local: the user can reopen manually if Windows rejects activation.
                report = status(settings, "applied", backup=backup, reopen_error=str(error), needs_ui_verification=True)  # Global: keep recovery information intact.
        return report  # Local: callers get the final saved phase.


def verify_backup(settings, directory):  # Global: compare identities without editing live data or history.
    """Local: validate a backup and inspect preservation; global: leave UI checks explicit."""
    directory = Path(directory).resolve()  # Local: treat the manifest as belonging to this selected backup.
    manifest = read_json(directory / "manifest.json")  # Global: reject malformed or ambiguous reports.
    if Path(manifest["source_home"]).resolve() != settings.home:  # Local: avoid comparing unrelated profiles.
        raise ValueError("Backup belongs to another Codex profile")  # Global: never infer preservation from mismatched data.
    snapshots = {}  # Local: validate both backup files before comparing anything.
    for label, name in (("state", ".codex-global-state.json"), ("database", "state_5.sqlite")):  # Global: use fixed local names, not arbitrary manifest file paths.
        snapshots[label] = directory / name  # Local: stay inside the chosen backup directory.
        if hashlib.sha256(snapshots[label].read_bytes()).hexdigest() != manifest[label + "_sha256"]:  # Global: detect corrupt or edited backups.
            raise ValueError(f"{label} backup checksum mismatch")  # Local: refuse unreliable evidence.
    before, after = read_json(snapshots["state"]), read_json(settings.state)  # Local: read snapshots without modifying either.
    old_projects, new_projects = projects(before), projects(after)  # Global: compare only recognized state layouts.
    assignments = after["thread-project-assignments"]  # Local: distinguish a missing prior key from a retained null value.
    report = {"legacy_project_ids_preserved": set(old_projects).issubset(new_projects), "legacy_assignments_unchanged": all(k in assignments and assignments[k] == v for k, v in before["thread-project-assignments"].items()), "tables": {}, "needs_ui_verification": True}  # Local: summarize relationships without exposing chat bodies.
    with closing(sqlite3.connect(snapshots["database"].as_uri() + "?mode=ro", uri=True)) as old, closing(sqlite3.connect((settings.home / "state_5.sqlite").as_uri() + "?mode=ro", uri=True)) as new:  # Global: never mutate the source database.
        for table in ("threads", "projects"):  # Local: identifiers are fixed constants, not SQL input.
            old_ids = {row[0] for row in old.execute(f'SELECT id FROM "{table}"')}  # Local: include archived records too.
            new_ids = {row[0] for row in new.execute(f'SELECT id FROM "{table}"')}  # Local: compare stable identities rather than counts alone.
            report["tables"][table] = {"before": len(old_ids), "current": len(new_ids), "missing": len(old_ids - new_ids)}  # Global: additions cannot conceal a missing old record.
    report["records_preserved"] = report["legacy_project_ids_preserved"] and report["legacy_assignments_unchanged"] and all(item["missing"] == 0 for item in report["tables"].values())  # Global: report mismatches for review; never claim chat visibility from record existence alone.
    return report  # Local: the CLI emits this read-only result.
