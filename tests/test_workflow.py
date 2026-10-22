"""Local: fixture-only application and recovery. Global: test the real pipeline without live state.

Source: https://docs.python.org/3.14/library/unittest.html
"""
import json  # Local: initialize realistic legacy dictionaries.
import sqlite3  # Local: initialize a disposable history database.
import tempfile  # Global: isolate every test under the ignored runtime directory.
import unittest  # Local: express preservation and failure assertions.
from contextlib import closing  # Global: release fixture database handles on Windows.
from pathlib import Path  # Local: keep fixtures inside the repository.
from unittest.mock import patch  # Local: replace app/WSL observations, not storage operations.
from codex_windows_project_repair.config import Settings, parse_json, read_json  # Global: test the production parser and path model.
from codex_windows_project_repair.workflow import apply_plan, verify_backup  # Global: run actual backup, commit, and verification phases.


class WorkflowTests(unittest.TestCase):  # Global: never operate on a real profile.
    def setUp(self):
        """Local: create synthetic state and chat records; global: make preservation measurable."""
        runtime = Path.cwd() / ".local" / "tests"  # Local: all generated data is ignored.
        runtime.mkdir(parents=True, exist_ok=True)  # Local: prepare the fixture parent.
        self.temp = tempfile.TemporaryDirectory(dir=runtime)  # Global: scope cleanup to this exact test directory.
        self.addCleanup(self.temp.cleanup)  # Local: cleanup also runs after failures.
        base = Path(self.temp.name)  # Local: resolve one independent fixture root.
        home = base / "profile"  # Local: model the Codex profile separately from output.
        home.mkdir()  # Global: create only synthetic state directories.
        self.settings = Settings(home, base / "output")  # Local: production phases use the same path interface.
        state = {"local-projects": {"p": {"id": "p", "rootPaths": ["/home/example"]}}, "thread-project-assignments": {"chat": {"projectId": "p"}}, "other": {"unicode": "Příliš"}}  # Global: include unrelated preservation sentinels.
        self.settings.state.write_text(json.dumps(state), encoding="utf-8")  # Local: write synthetic input only.
        with closing(sqlite3.connect(home / "state_5.sqlite")) as db:  # Local: close before snapshotting.
            db.executescript("CREATE TABLE threads(id TEXT); CREATE TABLE projects(id TEXT); INSERT INTO threads VALUES ('chat'); INSERT INTO projects VALUES ('p');")  # Global: missing records cannot hide behind equal counts.
        self.plan = {"schema_version": 1, "home": str(home), "distro": "FixtureDistro", "detach_missing": True, "changes": [{"id": "p", "old_root": "/home/example", "new_roots": []}]}  # Local: explicitly authorize verified-missing detachment.
        for name, value in (("probe_root", []), ("discover_app", {"executable": "Fixture.exe", "app_id": "fixture!app"}), ("assert_closed", None)):  # Local: OS facts are controlled; storage remains real.
            mocked = patch("codex_windows_project_repair.workflow." + name, return_value=value)  # Global: no real WSL or Codex process is queried.
            mocked.start()  # Local: install the deterministic observation.
            self.addCleanup(mocked.stop)  # Global: restore the production function after each test.

    def test_apply_and_verify_pipeline(self):  # Global: prove the complete storage workflow on Windows.
        """Local: apply, verify, then retry; global: preserve records and idempotence."""
        result = apply_plan(self.settings, self.plan)  # Local: run real backup and ReplaceFileW.
        self.assertEqual(result["stage"], "applied")  # Global: application reports its actual phase.
        audit = verify_backup(self.settings, result["backup"]["directory"])  # Local: compare actual source and snapshot IDs.
        self.assertTrue(audit["records_preserved"])  # Global: old identities and links remain intact.
        self.assertTrue(audit["needs_ui_verification"])  # Global: storage evidence is not UI evidence.
        self.assertEqual(apply_plan(self.settings, self.plan)["stage"], "already_applied")  # Local: a retry does not rewrite the profile.

    def test_backup_failure_blocks_commit(self):  # Global: no state write can precede a verified backup.
        """Local: simulate disk failure; global: preserve the original bytes."""
        original = self.settings.state.read_bytes()  # Local: retain the exact input.
        with patch("codex_windows_project_repair.workflow.backup_state", side_effect=OSError("fixture disk full")):
            with self.assertRaises(OSError):  # Global: failure must propagate to the CLI.
                apply_plan(self.settings, self.plan)  # Local: stop before the commit phase.
        self.assertEqual(self.settings.state.read_bytes(), original)  # Global: prove no live-style mutation occurred.
        self.assertEqual(read_json(self.settings.output / "status.json")["stage"], "failed")  # Local: preserve actionable status.

    def test_corrupt_database_blocks_commit(self):  # Global: a broken backup source cannot authorize repair.
        """Local: replace only fixture database bytes; global: require a verified snapshot."""
        original = self.settings.state.read_bytes()  # Local: retain the original JSON bytes.
        (self.settings.home / "state_5.sqlite").write_bytes(b"not sqlite")  # Local: simulate an unsupported/corrupt history database.
        with self.assertRaises(sqlite3.DatabaseError):  # Global: fail before JSON replacement.
            apply_plan(self.settings, self.plan)  # Local: exercise the real backup error path.
        self.assertEqual(self.settings.state.read_bytes(), original)  # Global: preserve all original JSON.

    def test_unsupported_database_schema_blocks_commit(self):  # Global: require verifiable history before repair.
        """Local: remove a fixture table; global: refuse a layout verification cannot support."""
        original = self.settings.state.read_bytes()  # Local: remember the unchanged JSON.
        with closing(sqlite3.connect(self.settings.home / "state_5.sqlite")) as db:  # Local: alter only this test's database.
            db.execute("DROP TABLE projects")  # Global: simulate a different app schema.
        with self.assertRaises(ValueError):  # Global: unknown database layouts must not authorize repair.
            apply_plan(self.settings, self.plan)  # Local: fail during preflight.
        self.assertEqual(self.settings.state.read_bytes(), original)  # Global: preserve all source state.

    def test_verification_detects_missing_record_despite_same_count(self):  # Global: counts alone cannot establish preservation.
        """Local: swap a fixture ID; global: detect the lost original identity."""
        result = apply_plan(self.settings, self.plan)  # Local: establish a real backup.
        with closing(sqlite3.connect(self.settings.home / "state_5.sqlite")) as db:
            db.execute("UPDATE threads SET id='replacement'")  # Local: mutate only the disposable fixture.
            db.commit()  # Local: make the synthetic loss visible to read-only verification.
        audit = verify_backup(self.settings, result["backup"]["directory"])  # Global: compare identities across snapshots.
        self.assertFalse(audit["records_preserved"])  # Local: equal row counts must not conceal loss.
        self.assertEqual(audit["tables"]["threads"]["missing"], 1)  # Global: report exact missing-record count.

    def test_reopen_failure_keeps_applied_status(self):  # Global: restart failures must not imply a rolled-back repair.
        """Local: simulate failed Windows activation; global: retain successful application evidence."""
        with patch("codex_windows_project_repair.workflow.reopen_app", side_effect=OSError("fixture activation failed")):
            result = apply_plan(self.settings, self.plan, reopen=True)  # Local: commit succeeds before the fake activation failure.
        self.assertEqual(result["stage"], "applied")  # Global: preserve accurate state.
        self.assertIn("reopen_error", result)  # Local: let the user reopen manually.

    def test_strict_json_rejects_duplicate_keys(self):  # Global: prevent silent field loss during parsing.
        """Local: supply ambiguous JSON; global: refuse it before any mutation."""
        with self.assertRaises(ValueError):  # Local: duplicate keys are not a valid repair input.
            parse_json(b'{"key":1,"key":2}')  # Global: no file or profile is involved.
