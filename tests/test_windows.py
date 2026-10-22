"""Local: model WSL metadata and translation. Global: exercise path checks without WSL or Codex.

Sources: https://docs.python.org/3.14/library/unittest.mock.html and
https://docs.python.org/3.14/library/subprocess.html#subprocess.CompletedProcess.
"""
import subprocess  # Local: give fake commands the same result interface as production commands.
import unittest  # Global: report each path contract as an independently named test.
from pathlib import Path  # Local: compare the exact path passed to the Windows metadata check.
from unittest.mock import patch  # Global: prevent real subprocess and filesystem probes.
from codex_windows_project_repair.windows import probe_root  # Local: exercise the production decision logic.


class RootProbeTests(unittest.TestCase):  # Global: isolate path parsing from live installations.
    """Local: synthetic command results; global: distinguish path evidence from assumptions."""

    def setUp(self):  # Local: reset the metadata model for each test.
        """Global: mock both Linux observations and Windows access before calling production code."""
        self.root = "/home/example"  # Local: synthetic Linux folder used only as a command argument.
        self.target = r"\\wsl.localhost\TestDistro\home\example"  # Local: synthetic translated spelling.
        self.output = self.target + "\n"  # Local: model the ordinary wslpath line terminator.
        self.predicates = {("-d", "/home"): 0, ("-x", "/home"): 0, ("-d", self.root): 0, ("-e", self.root): 0, ("-L", self.root): 1}  # Local: explicit test exit codes for a searchable directory parent and existing child.
        commands = patch("codex_windows_project_repair.windows.run_hidden", side_effect=self.command_result)  # Global: no executable is started.
        commands.start()  # Local: intercept every WSL query.
        self.addCleanup(commands.stop)  # Global: restore the production function after each test.
        native = patch("codex_windows_project_repair.windows.Path.is_dir", autospec=True, return_value=True)  # Global: no Windows or UNC directory is queried.
        self.native = native.start()  # Local: retain calls for exact-spelling assertions.
        self.addCleanup(native.stop)  # Global: restore the filesystem method after each test.

    def command_result(self, arguments):  # Local: answer commands by predicate and path rather than call order.
        """Global: unexpected metadata queries fail the fixture instead of receiving invented evidence."""
        if arguments[-3:-1] == ["wslpath", "-w"]:  # Local: recognize only the translation operation.
            return subprocess.CompletedProcess(arguments, 0, self.output, "")  # Local: return the configured full output.
        return subprocess.CompletedProcess(arguments, self.predicates[tuple(arguments[-2:])], "", "")  # Local: require an explicitly modeled test predicate.

    def test_translation_preserves_trailing_whitespace(self):  # Global: never silently select a different folder spelling.
        """Local: combine space/NBSP names with LF/CRLF; global: check the returned and queried path."""
        for suffix in (" ", "\u00a0"):  # Local: cover ASCII and Unicode whitespace removed by str.strip.
            for ending in ("\n", "\r\n"):  # Local: accept one ordinary command-output terminator.
                with self.subTest(suffix=repr(suffix), ending=repr(ending)):  # Global: identify the exact failed spelling.
                    root, target = self.root + suffix, self.target + suffix  # Local: keep the modeled source and target names consistent.
                    self.predicates[("-d", root)] = 0  # Local: this exact Linux directory exists in the fixture.
                    self.output = target + ending  # Local: include significant whitespace before the terminator.
                    self.native.reset_mock()  # Local: inspect only this subcase's Windows query.
                    self.assertEqual(probe_root("TestDistro", root), [target])  # Global: retain all meaningful path characters.
                    self.native.assert_called_once_with(Path(target))  # Global: check the same spelling that will enter the plan.

    def test_translation_accepts_single_line_without_terminator(self):  # Global: do not require a newline to interpret one path.
        """Local: model a single unterminated output line; global: preserve its complete value."""
        self.output = self.target  # Local: omit only the transport terminator.
        self.assertEqual(probe_root("TestDistro", self.root), [self.target])  # Global: no path character is removed.

    def test_translation_rejects_empty_or_multiline_output(self):  # Global: malformed output cannot reach a native path query.
        """Local: reject blank output, repeated endings, embedded lines, and a lone CR."""
        outputs = ("", "\n", "\r\n", self.target + "\n\n", self.target + "\r\n\r\n", self.target + "\n" + self.target + "\n", self.target + "\r", self.target + "\n\r\n")  # Local: exercise ambiguity independently of filesystem acceptance.
        for output in outputs:  # Local: retain one assertion context for each malformed result.
            with self.subTest(output=repr(output)):  # Global: make failures reproducible from the synthetic value.
                self.output = output  # Local: replace only the translation response.
                self.native.reset_mock()  # Local: track whether validation reaches the filesystem.
                with self.assertRaises(RuntimeError):  # Global: malformed output is an error, never a proposed root.
                    probe_root("TestDistro", self.root)  # Local: use the actual parser and validation branch.
                self.native.assert_not_called()  # Global: reject before checking any ambiguous destination.

    def test_executable_file_parent_is_not_a_missing_directory(self):  # Global: execute permission alone does not establish directory traversal.
        """Local: model an executable regular-file parent; global: require an error instead of detachment."""
        self.predicates[("-d", "/home")] = 1  # Local: the supposed parent is not a directory.
        for flag in ("-d", "-e", "-L"):  # Local: a child under this regular file cannot satisfy these predicates.
            self.predicates[(flag, self.root)] = 1  # Local: expose the old false-absence classification.
        with self.assertRaises(RuntimeError):  # Global: preserve the link when its parent is invalid.
            probe_root("TestDistro", self.root)  # Local: parent -x still returns success in this fixture.
        self.native.assert_not_called()  # Global: no Windows destination should be considered.

    def test_unsearchable_directory_parent_is_not_missing(self):  # Global: directory type alone does not establish access.
        """Local: deny traversal on a directory parent; global: refuse an absence proposal."""
        self.predicates[("-x", "/home")] = 1  # Local: distinguish directory status from search permission.
        with self.assertRaises(RuntimeError):  # Global: preserve inaccessible paths for manual review.
            probe_root("TestDistro", self.root)  # Local: no real permission is changed.
        self.native.assert_not_called()  # Global: reject before any destination check.

    def test_missing_directory_returns_empty_proposal(self):  # Global: retain the checked-absence path used by explicit detachment.
        """Local: model a searchable directory parent and absent child; global: propose only an empty root array."""
        for flag in ("-d", "-e", "-L"):  # Local: exclude directories, other existing objects, and broken symlinks.
            self.predicates[(flag, self.root)] = 1  # Local: all child predicates report false.
        self.assertEqual(probe_root("TestDistro", self.root), [])  # Global: planning still separately requires --detach-missing.
        self.native.assert_not_called()  # Local: no translation is needed for a missing location.

    def test_native_inaccessible_directory_is_rejected(self):  # Global: Linux existence alone cannot authorize a Windows root.
        """Local: deny the translated Windows directory check; global: preserve the original root."""
        self.native.return_value = False  # Local: model failed native metadata access.
        with self.assertRaises(RuntimeError):  # Global: an unusable destination blocks the proposal.
            probe_root("TestDistro", self.root)  # Local: exercise the existing Windows check.

    def test_wsl_execution_error_is_not_absence(self):  # Global: unexpected command status cannot authorize detachment.
        """Local: inject a non-predicate status; global: stop before translation or a missing-root result."""
        self.predicates[("-d", self.root)] = 3  # Local: test accepts only its conventional 0/1 predicate results.
        with self.assertRaises(RuntimeError):  # Global: surface the execution failure.
            probe_root("TestDistro", self.root)  # Local: use no actual WSL installation.
        self.native.assert_not_called()  # Global: do not inspect a destination after failed evidence gathering.
