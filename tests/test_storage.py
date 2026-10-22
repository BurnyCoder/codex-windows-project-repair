"""Local: exercise preservation and backups. Global: never test on live Codex data.

Sources: https://docs.python.org/3.14/library/unittest.html and
https://docs.python.org/3.14/library/tempfile.html.
"""
import json  # Local: encode fixtures; global: compare real JSON round trips.
import sqlite3  # Local: create a tiny database; global: verify consistent backups.
import tempfile  # Local: isolate fixture files; global: protect real app data.
import unittest  # Local: define assertions; global: use the standard test runner.
from contextlib import closing  # Local: close SQLite handles; global: permit Windows cleanup.
from pathlib import Path  # Local: compose fixture paths; global: avoid shell quoting.
from codex_windows_project_repair.storage import backup_state, build_repair, commit_state  # Global: test production phases.


class RepairTests(unittest.TestCase):  # Global: group the repair's safety contracts.
    """Local: synthetic fixtures. Global: check that only approved roots change in these cases."""

    def setUp(self):  # Local: reset fixtures before every test; global: isolate cases.
        """Local: create linked project/chat state. Global: catch accidental deletion."""
        self.state = {  # Local: combine linked records with unrelated preservation sentinels.
            "local-projects": {"p": {"id": "p", "name": "example", "rootPaths": ["/home/x"]}},  # Local: fixture project.
            "thread-project-assignments": {"chat": {"projectId": "p"}},  # Global: retain the chat association.
            "project-order": ["p"],  # Global: retain sidebar ordering.
            "unrelated": {"text": "Příliš", "number": 12345678901234567890},  # Global: preserve Unicode and large integers.
        }  # Local: finish the independent per-test fixture.
        self.plan = [{"id": "p", "old_root": "/home/x", "new_roots": [r"\\wsl$\Ubuntu\home\x"]}]  # Local: authorize exactly one root.

    def test_changes_only_approved_roots(self):  # Global: preserve every other field.
        """Local: revert the proposed field. Global: require complete original equality."""
        changed = build_repair(self.state, self.plan)  # Local: construct the candidate without writing.
        changed["local-projects"]["p"]["rootPaths"] = ["/home/x"]  # Local: undo the only approved change.
        self.assertEqual(changed, self.state)  # Global: no hidden changes to chats or metadata.

    def test_missing_folder_keeps_project_and_chat(self):  # Global: detach only a missing location.
        """Local: clear roots. Global: preserve the project container and chat link."""
        self.plan[0]["new_roots"] = []  # Local: model the confirmed missing WSL directory.
        changed = build_repair(self.state, self.plan)  # Local: build the empty-folder project.
        self.assertEqual(changed["local-projects"]["p"]["rootPaths"], [])  # Global: no invalid path remains.
        self.assertEqual(changed["thread-project-assignments"], self.state["thread-project-assignments"])  # Global: preserve chats.
        self.assertEqual(changed["project-order"], ["p"])  # Global: keep the project in its original order.

    def test_unexpected_root_aborts(self):  # Global: never overwrite a newer user edit.
        """Local: simulate changed state. Global: require a fresh review instead of guessing."""
        self.state["local-projects"]["p"]["rootPaths"] = [r"C:\new"]  # Local: simulate an intervening edit.
        with self.assertRaises(ValueError):  # Global: changed assumptions must block the write.
            build_repair(self.state, self.plan)  # Local: attempt the outdated plan.

    def test_backups_and_commit_preserve_database(self):  # Global: validate actual filesystem behavior.
        """Local: back up and patch fixtures. Global: verify JSON and database preservation."""
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:  # Local: keep disposable files in this workspace.
            state_path = Path(folder) / ".codex-global-state.json"  # Local: match the real filename.
            original = json.dumps(self.state).encode()  # Local: preserve exact initial bytes.
            state_path.write_bytes(original)  # Local: initialize the synthetic state file.
            database = state_path.with_name("state_5.sqlite")  # Local: model the actual database filename.
            with closing(sqlite3.connect(database)) as connection:  # Local: close the fixture handle before cleanup.
                connection.executescript("CREATE TABLE threads(id TEXT); INSERT INTO threads VALUES ('chat');")  # Global: create a history-preservation sentinel.
            report = backup_state(state_path, Path(folder) / "backups", original)  # Local: exercise the production backup.
            self.assertEqual(Path(report["state_backup"]).read_bytes(), original)  # Global: byte-for-byte recovery is possible.
            self.assertEqual(report["database_counts"]["threads"], 1)  # Global: check the fixture row count; this assertion alone does not compare all record contents.
            candidate = build_repair(self.state, self.plan)  # Local: prepare the reviewed change.
            commit_state(state_path, original, candidate, lambda: None)  # Local: use a synthetic closed-app guard.
            self.assertEqual(json.loads(state_path.read_bytes()), candidate)  # Global: verify the actual saved result.
            with closing(sqlite3.connect(database)) as connection:  # Local: inspect and close the original fixture database.
                self.assertEqual(connection.execute("SELECT count(*) FROM threads").fetchone()[0], 1)  # Global: check the source fixture's row count; this does not prove every field or byte stayed unchanged.

    def test_concurrent_change_aborts_commit(self):  # Global: guard against stale backups and writes.
        """Local: change bytes before commit. Global: refuse to overwrite a concurrent edit."""
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:  # Local: isolate the race fixture inside the workspace.
            state_path = Path(folder) / "state.json"  # Local: create a harmless target.
            state_path.write_text('{"new":true}')  # Local: simulate another writer's update.
            with self.assertRaises(RuntimeError):  # Global: an outdated snapshot cannot authorize a write.
                commit_state(state_path, b"{}", self.state, lambda: None)  # Local: supply stale expected bytes.
            self.assertEqual(state_path.read_text(), '{"new":true}')  # Global: preserve the concurrent writer's data.

    def test_repeat_plan_is_idempotent(self):  # Global: a repeated helper cannot introduce further edits.
        """Local: run the same plan twice. Global: require an identical final state."""
        changed = build_repair(self.state, self.plan)  # Local: perform the first pure transformation.
        self.assertEqual(build_repair(changed, self.plan), changed)  # Global: a second invocation is harmless.

    def test_running_app_guard_prevents_write(self):  # Global: check that the injected running-app guard blocks this write.
        """Local: simulate a running desktop. Global: leave the original file byte-identical."""
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:  # Local: keep the test isolated.
            state_path = Path(folder) / "state.json"  # Local: create a synthetic target.
            original = json.dumps(self.state).encode()  # Local: preserve exact original bytes.
            state_path.write_bytes(original)  # Local: initialize the target.
            def refuse():  # Local: emulate a closed-app guard that detects an active process.
                """Local: reject the write. Global: simulate protection of active user work."""
                raise RuntimeError("app is running")  # Global: fail before replacement.
            with self.assertRaises(RuntimeError):  # Global: the guard must propagate its refusal.
                commit_state(state_path, original, build_repair(self.state, self.plan), refuse)  # Local: attempt the guarded operation.
            self.assertEqual(state_path.read_bytes(), original)  # Global: nothing was written to the target.


if __name__ == "__main__":  # Local: support direct invocation; global: also permit discovery.
    unittest.main()  # Global: return a nonzero exit code when a safety contract fails.
