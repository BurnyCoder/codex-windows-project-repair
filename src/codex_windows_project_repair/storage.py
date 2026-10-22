"""Local: transform and back up state. Global: preserve projects, chats, and file ACLs.

Sources: https://docs.python.org/3.14/library/json.html,
https://docs.python.org/3.14/library/sqlite3.html#sqlite3.Connection.backup,
https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew.
"""
import copy  # Local: isolate edits; global: retain the original state for comparison.
import ctypes  # Local: call Windows replacement; global: preserve the original file's DACL.
import hashlib  # Local: hash backups; global: provide a verifiable recovery record.
import json  # Local: validate structure; global: preserve JSON value types.
import logging  # Local: record phases; global: make the repair auditable.
import os  # Local: flush writes; global: finish the temporary file before replacement.
import sqlite3  # Local: snapshot the database; global: never update the source database.
import time  # Local: bound busy-database backup retries; global: avoid a stuck worker.
import uuid  # Local: name an exclusive temporary file; global: avoid collisions.
from contextlib import closing  # Local: close database handles; global: prevent lingering locks.
from ctypes import wintypes  # Local: declare Windows ABI types; global: avoid pointer conversion errors.
from datetime import datetime, timezone  # Local: timestamp backups; global: use explicit UTC.


def validate_database(database):  # Global: require the history layout that verification understands.
    """Local: inspect fixed table schemas read-only; global: reject unsupported state before repair."""
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:  # Local: never create or update the source database.
        for table in ("threads", "projects"):  # Global: SQL identifiers are fixed internal constants.
            columns = {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}  # Local: inspect schema without reading conversations.
            if "id" not in columns:  # Global: record preservation must remain verifiable after repair.
                raise ValueError(f"Unsupported database layout: missing {table}.id")  # Local: require review of the changed app schema.


def build_repair(state, plan):  # Global: a pure transformation with no disk side effects.
    """Local: change reviewed root arrays. Global: retain all IDs and chat associations."""
    candidate = copy.deepcopy(state)  # Local: make independent nested objects.
    seen = set()  # Local: detect duplicate authorization entries before changing anything.
    for item in plan:  # Local: visit only the explicitly reviewed project IDs.
        project_id = item["id"]  # Local: use stable identity rather than a display name.
        if project_id in seen:  # Global: ambiguous duplicate plan entries must fail.
            raise ValueError(f"Duplicate project in repair plan: {project_id}")  # Local: explain the invalid plan.
        seen.add(project_id)  # Local: remember the checked identity.
        project = candidate["local-projects"].get(project_id)  # Local: locate the exact legacy record.
        if not project or project.get("id") != project_id:  # Global: never invent a missing project.
            raise ValueError(f"Project record changed or disappeared: {project_id}")  # Local: require a new diagnosis.
        if project["rootPaths"] not in ([item["old_root"]], item["new_roots"]):  # Global: protect newer user edits.
            raise ValueError(f"Unexpected rootPaths for {project_id}")  # Local: refuse the stale plan.
        project["rootPaths"] = list(item["new_roots"])  # Local: replace only the allowed folder links.
    return candidate  # Global: all other fields come unchanged from the deep copy.


def backup_state(state_path, backup_root, original):  # Global: establish recovery before any app-state write.
    """Local: copy JSON bytes and snapshot SQLite. Global: preserve a consistent history backup."""
    if state_path.read_bytes() != original:  # Local: ensure the provided snapshot is still current.
        raise RuntimeError("State changed before backup; aborting")  # Global: do not build a stale repair.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")  # Local: use a unique, explicit UTC name.
    directory = backup_root / stamp  # Local: keep this run's recovery files together.
    directory.mkdir(parents=True, exist_ok=False)  # Global: never overwrite an older backup.
    state_backup = directory / state_path.name  # Local: retain the original JSON filename.
    state_backup.write_bytes(original)  # Local: copy the exact bytes, including formatting.
    if state_backup.read_bytes() != original:  # Global: a verified backup is mandatory.
        raise RuntimeError("JSON backup verification failed")  # Local: stop before modifications.
    database = state_path.with_name("state_5.sqlite")  # Local: target only the observed Codex state database.
    database_backup = directory / database.name  # Local: save a standalone SQLite snapshot.
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as source:  # Global: source is read-only.
        with closing(sqlite3.connect(database_backup)) as destination:  # Local: only the backup is writable.
            deadline = time.monotonic() + 30  # Global: bound retries if another process keeps the database busy.
            def progress(status, remaining, total):  # Local: receive backup progress without querying chat contents.
                """Global: abort stalled backups before allowing a state write."""
                if time.monotonic() > deadline:  # Local: use an elapsed-time deadline.
                    raise TimeoutError("SQLite backup exceeded 30 seconds")  # Global: no incomplete backup can authorize repair.
            source.backup(destination, pages=256, progress=progress)  # Global: include committed WAL contents through SQLite's backup API.
            if destination.execute("PRAGMA quick_check").fetchall() != [("ok",)]:  # Local: verify snapshot consistency.
                raise RuntimeError("SQLite backup integrity check failed")  # Global: never proceed with a bad backup.
            tables = {row[0] for row in destination.execute("SELECT name FROM sqlite_master WHERE type='table'")}  # Local: inspect schema only.
            counts = {name: destination.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0] for name in ("threads", "projects") if name in tables}  # Local: count only fixed, trusted table names.
    report = {"source_home": str(state_path.parent.resolve()), "directory": str(directory), "state_backup": str(state_backup), "state_sha256": hashlib.sha256(original).hexdigest(), "database_backup": str(database_backup), "database_sha256": hashlib.sha256(database_backup.read_bytes()).hexdigest(), "database_counts": counts}  # Global: record recovery locations, identity, and checks.
    (directory / "manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")  # Local: keep the backup self-describing.
    logging.info("Verified JSON and SQLite backup: %s", report)  # Global: log metadata, never full chat contents.
    return report  # Local: give the caller a precise recovery record.


def replace_preserving_metadata(target, replacement):  # Global: atomically replace content while retaining Windows ACLs.
    """Local: call ReplaceFileW. Global: keep the replaced file's security and metadata."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)  # Local: retain the Windows failure code.
    replace = kernel.ReplaceFileW  # Local: use the documented file-replacement primitive.
    replace.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID]  # Local: match the native signature.
    replace.restype = wintypes.BOOL  # Local: interpret the native success result correctly.
    if not replace(str(target), str(replacement), None, 0, None, None):  # Global: keep normal metadata-merge error checking.
        raise ctypes.WinError(ctypes.get_last_error())  # Local: report the precise filesystem failure.


def commit_state(state_path, original, candidate, assert_closed):  # Global: perform the only live-state mutation.
    """Local: validate, guard, and replace JSON. Global: refuse concurrent edits and active Codex."""
    payload = (json.dumps(candidate, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")  # Local: serialize without truncating values.
    if json.loads(payload) != candidate:  # Global: a serialization mismatch must never reach disk.
        raise RuntimeError("JSON round-trip verification failed")  # Local: fail before replacement.
    temporary = state_path.with_name(state_path.name + ".repair-" + uuid.uuid4().hex + ".tmp")  # Local: keep both files on the same volume.
    try:  # Global: clean up only this helper's exact temporary file.
        with temporary.open("xb") as stream:  # Local: create exclusively; never overwrite another file.
            stream.write(payload)  # Local: write the complete candidate JSON.
            stream.flush()  # Local: push Python's buffer to the operating system.
            os.fsync(stream.fileno())  # Global: finish the replacement file before committing it.
        assert_closed()  # Global: check again immediately before the app-state write.
        if state_path.read_bytes() != original:  # Global: preserve any intervening user or app edit.
            raise RuntimeError("State changed before commit; leaving it untouched")  # Local: abort safely.
        replace_preserving_metadata(state_path, temporary)  # Local: replace this one file while preserving its DACL.
        if state_path.read_bytes() != payload:  # Global: verify what actually reached the live state file.
            raise RuntimeError("Saved JSON changed unexpectedly; inspect the verified backup")  # Local: avoid overwriting a concurrent update.
        logging.info("Committed and verified the reviewed rootPaths repair")  # Global: distinguish applied state from a preview.
    finally:  # Local: execute cleanup on both success and failure.
        temporary.unlink(missing_ok=True)  # Global: remove only the exact temporary file created above.
