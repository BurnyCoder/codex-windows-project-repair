"""Local: synthetic plans and mocked WSL. Global: reject unsafe or ambiguous repairs.

Source: https://docs.python.org/3.14/library/unittest.mock.html
"""
import copy  # Local: isolate input mutations between assertions.
import unittest  # Global: exercise contracts without real Codex data.
from unittest.mock import patch  # Local: replace only OS probes in tests.
from pathlib import Path  # Local: bind synthetic plans to a profile.
from codex_windows_project_repair.planning import create_plan, validate_plan, inspect_state  # Global: test public planning phases.
from codex_windows_project_repair.windows import probe_root, single_worker, wait_for_exit  # Global: exercise lifecycle guards.
from types import SimpleNamespace  # Local: provide minimal command results.


class PlanningTests(unittest.TestCase):  # Global: fixtures never read the user's profile.
    def setUp(self):  # Local: start each test with an independent linked project.
        """Global: keep unrelated roots and chat links in the preservation fixture."""
        self.state = {"local-projects": {"p": {"id": "p", "name": "example", "rootPaths": ["/home/example"]}}, "thread-project-assignments": {"t": {"projectId": "p"}}}  # Local: synthetic IDs only.
        self.home = Path.cwd() / "fixture-home"  # Global: no real state files are needed.

    @patch("codex_windows_project_repair.planning.probe_root", return_value=[r"\\wsl$\TestDistro\home\example"])
    def test_selected_project_plan(self, probe):  # Global: require an explicit distro and selected ID.
        """Local: derive a proposal; global: leave source state unchanged."""
        original = copy.deepcopy(self.state)  # Local: retain a semantic sentinel.
        plan = create_plan(self.state, self.home, ["p"], "TestDistro", False)  # Local: create the proposal with a fake probe.
        self.assertEqual(plan["changes"][0]["id"], "p")  # Global: preserve stable identity.
        self.assertEqual(self.state, original)  # Global: planning is non-mutating.
        validate_plan(plan, self.home)  # Global: a generated proposal must pass its own validation.

    def test_multi_root_rejected(self):  # Global: do not accidentally drop additional folders.
        """Local: provide two roots; global: reject unsupported v1 layouts."""
        self.state["local-projects"]["p"]["rootPaths"].append("/home/second")  # Local: model a multi-root project.
        with self.assertRaises(ValueError):  # Global: no partial plan should be accepted.
            create_plan(self.state, self.home, ["p"], "TestDistro", False)  # Local: attempt an unsupported conversion.

    def test_inspection_reports_supported_shape(self):  # Global: make diagnosis usable before selecting IDs.
        """Local: inspect a Linux root; global: avoid OS or write side effects."""
        self.assertEqual(inspect_state(self.state)[0]["status"], "linux_root")  # Local: classify only the known single-root shape.

    @patch("codex_windows_project_repair.planning.probe_root", return_value=[])
    def test_detach_requires_opt_in(self, probe):  # Global: a missing directory does not implicitly authorize detachment.
        """Local: simulate absence; global: demand explicit permission in the plan."""
        with self.assertRaises(ValueError):  # Local: default behavior preserves the folder link.
            create_plan(self.state, self.home, ["p"], "TestDistro", False)  # Global: refuse implicit detachment.
        plan = create_plan(self.state, self.home, ["p"], "TestDistro", True)  # Local: explicitly authorize the missing-folder case.
        self.assertEqual(plan["changes"][0]["new_roots"], [])  # Global: preserve the project container.

    @patch("codex_windows_project_repair.planning.probe_root", return_value=[])
    def test_plan_bound_to_home(self, probe):  # Global: avoid applying someone else's plan to another profile.
        """Local: change profile identity; global: fail validation."""
        plan = create_plan(self.state, self.home, ["p"], "TestDistro", True)  # Local: bind the fixture to one home.
        with self.assertRaises(ValueError):  # Global: identity mismatch is actionable, not guessed.
            validate_plan(plan, self.home / "different")  # Local: attempt another destination.

    def test_inaccessible_parent_not_missing(self):  # Global: WSL failure must not detach data.
        """Local: simulate a permission error; global: stop before any proposal."""
        with patch("codex_windows_project_repair.windows.run_hidden", return_value=SimpleNamespace(returncode=1, stdout="", stderr="")):
            with self.assertRaises(RuntimeError):  # Local: require an error rather than an empty root list.
                probe_root("TestDistro", "/private/example")  # Global: no real WSL access occurs.

    def test_broken_link_not_missing(self):  # Global: preserve a broken symlink for manual review.
        """Local: model parent success, directory absence, and symlink existence."""
        results = [SimpleNamespace(returncode=code, stdout="", stderr="") for code in (0, 0, 1, 1, 0)]  # Local: parent -d/-x, then child -d/-e/-L responses.
        with patch("codex_windows_project_repair.windows.run_hidden", side_effect=results):
            with self.assertRaises(RuntimeError):  # Global: an existing symlink is not an absent path.
                probe_root("TestDistro", "/home/example")  # Local: test the distinction.

    def test_duplicate_worker_refused(self):  # Global: serialize application across output locations.
        """Local: hold the Windows mutex; global: reject a second worker for the same profile."""
        with single_worker(self.home):  # Local: acquire the profile-specific guard.
            with self.assertRaises(RuntimeError):  # Global: duplicate acquisition must fail immediately.
                with single_worker(self.home):  # Local: simulate a second process using the same profile.
                    self.fail("duplicate worker entered")  # Global: never reach the repair twice.

    def test_wait_expires_without_killing_app(self):  # Global: bound the shutdown wait without terminating work.
        """Local: fake a continuously running app and clock; global: require timeout."""
        with patch("codex_windows_project_repair.windows.app_running", return_value=True), patch("codex_windows_project_repair.windows.time.sleep"), patch("codex_windows_project_repair.windows.time.monotonic", side_effect=[0, 0, 1801]):
            with self.assertRaises(TimeoutError):  # Local: the deadline is a failure, never permission to write.
                wait_for_exit("Example.exe")  # Global: no real process is affected.
