"""Local: Windows/WSL operations. Global: fail closed and never terminate Codex.

Sources: https://docs.python.org/3.14/library/subprocess.html,
https://learn.microsoft.com/windows/win32/api/synchapi/nf-synchapi-createmutexw,
https://learn.microsoft.com/powershell/module/appx/get-appxpackagemanifest,
https://learn.microsoft.com/en-us/windows/dev-environment/wsl-interop
"""
import csv  # Local: parse tasklist's machine-readable format.
import ctypes  # Local: use a kernel lifetime guard instead of stale lockfiles.
import hashlib  # Local: derive a non-personal mutex name from the profile.
import json  # Local: parse package metadata returned by PowerShell.
import logging  # Global: log decoded output from completed diagnostic commands.
import os  # Local: compare Windows paths case-insensitively.
import subprocess  # Local: argument arrays avoid interpolating user data into shell code.
import time  # Local: use monotonic deadlines for shutdown.
from contextlib import contextmanager  # Global: always release the worker guard.
from ctypes import wintypes  # Local: match the Windows API's pointer widths.
from pathlib import Path, PurePosixPath, PureWindowsPath  # Local: keep Linux and Windows path semantics explicit.


def run_hidden(arguments):  # Global: centralize bounded, invisible diagnostic processes.
    """Local: capture then decode bytes; global: log completed commands, not live child streams."""
    result = subprocess.run(arguments, capture_output=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)  # Local: no shell parsing or visible console.
    for field in ("stdout", "stderr"):  # Local: decode each stream independently.
        raw = getattr(result, field)  # Local: preserve the complete captured stream.
        setattr(result, field, raw.decode("utf-16-le" if b"\x00" in raw else "utf-8", errors="replace").lstrip("\ufeff"))  # Local: handle native WSL and normal UTF-8 output.
    logging.debug("Command %r returned %s; stdout=%s; stderr=%s", arguments, result.returncode, result.stdout, result.stderr)  # Global: retain useful failures without truncation.
    return result  # Local: let the caller interpret expected test exit codes.


def discover_app():  # Global: discover the registered desktop without hardcoding package versions.
    """Local: read the MSIX manifest; global: reject ambiguous or unsupported installations."""
    script = r"""
$ErrorActionPreference = 'Stop' # Local: metadata failures must propagate.
$items = @(Get-AppxPackage -Name OpenAI.Codex | ForEach-Object { # Global: inspect only the supported package.
    $package = $_ # Local: retain family identity for the launch ID.
    (Get-AppxPackageManifest -Package $package).Package.Applications.Application | Where-Object { $_.Executable -match '(?:^|[\\/])(ChatGPT|Codex)\.exe$' } | ForEach-Object { # Local: identify desktop executables.
        [pscustomobject]@{ app_id = $package.PackageFamilyName + '!' + $_.Id; executable = [IO.Path]::GetFileName($_.Executable); version = $package.Version.ToString() } # Global: return launch and guard metadata only.
    }
})
if ($items.Count -ne 1) { throw 'Expected exactly one supported OpenAI.Codex desktop installation' } # Global: never guess the process to guard.
$items[0] | ConvertTo-Json -Compress # Local: give Python a structured result.
"""  # Global: the script is constant; no project paths are interpolated.
    result = run_hidden(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script])  # Local: read installation metadata.
    result.check_returncode()  # Global: failed discovery blocks application.
    return json.loads(result.stdout)  # Local: retain the actual registered identity.


def list_distros():  # Global: help users choose an explicit WSL distribution.
    """Local: list registered names; global: do not infer a Linux home from another distro."""
    result = run_hidden(["wsl.exe", "--list", "--quiet"])  # Local: use the documented machine-readable list.
    result.check_returncode()  # Global: missing WSL is an error, not an empty filesystem.
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]  # Local: omit blank lines and trim distribution-name whitespace.


def probe_root(distro, root):  # Global: distinguish absence from permissions and WSL failure.
    """Local: gather path metadata; global: reject detected access failures before proposing roots."""
    def test(flag, path):  # Local: reuse argument-array invocation for every metadata test.
        """Global: preserve the conventional 0/1 test result and reject execution errors."""
        result = run_hidden(["wsl.exe", "-d", distro, "--exec", "/usr/bin/test", flag, path])  # Local: inspect metadata without reading project files.
        if result.returncode not in (0, 1):  # Global: a WSL error is never evidence of absence.
            raise RuntimeError(f"WSL metadata check failed: {path}")  # Local: require a usable environment.
        return result.returncode == 0  # Local: expose the exact predicate result.
    parent = str(PurePosixPath(root).parent)  # Local: test the immediate containing path before interpreting child predicates.
    if not test("-d", parent) or not test("-x", parent):  # Global: require directory type and search access; https://www.gnu.org/software/coreutils/manual/coreutils.html#test-invocation.
        raise RuntimeError(f"Cannot access parent of {root}")  # Local: stop before -d could be misread.
    if test("-d", root):  # Local: resolve only a known directory.
        result = run_hidden(["wsl.exe", "-d", distro, "--exec", "wslpath", "-w", root])  # Global: let the selected distro translate drive mounts and UNC paths.
        result.check_returncode()  # Local: never use an error as a destination.
        ending = "\r\n" if result.stdout.endswith("\r\n") else "\n"  # Local: select at most one terminal line ending.
        target = result.stdout.removesuffix(ending)  # Global: preserve filename whitespace; https://docs.python.org/3.14/builtins/stdtypes.html#str.removesuffix.
        if not target or "\r" in target or "\n" in target:  # Global: reject empty or multiline output before any Windows query.
            raise RuntimeError("Expected one nonempty path from wslpath")  # Local: ambiguous output cannot become a proposed root.
        if not PureWindowsPath(target).is_absolute() or not Path(target).is_dir():  # Global: verify native Windows can access the proposed root.
            raise RuntimeError(f"Translated directory is not accessible from Windows: {target}")  # Local: reject unusable paths.
        return [target]  # Local: v1 changes one root only.
    if test("-e", root) or test("-L", root):  # Global: files and broken symlinks require manual review.
        raise RuntimeError(f"Not a directory, but not absent: {root}")  # Local: preserve the original link.
    return []  # Global: only verified absence can be proposed for explicit detachment.


def app_running(executable):  # Global: guard every process with the observed desktop executable name.
    """Local: query tasklist CSV; global: localized no-match text is not parsed as a process."""
    result = run_hidden(["tasklist.exe", "/FI", f"IMAGENAME eq {executable}", "/FO", "CSV", "/NH"])  # Local: never terminate or signal the desktop.
    result.check_returncode()  # Global: failed observation does not establish closure.
    return any(row and row[0].casefold() == executable.casefold() for row in csv.reader(result.stdout.splitlines()))  # Local: check the exact image name.


def assert_closed(executable):  # Global: reusable guard immediately before backup and commit.
    """Local: observe processes again; global: refuse changes while the desktop owns its state."""
    if app_running(executable):  # Local: use a fresh observation rather than cached readiness.
        raise RuntimeError("Codex is still running; fully quit it before applying")  # Global: fail without forcing user exit.


def wait_for_exit(executable):  # Global: allow user-controlled shutdown with a bounded wait.
    """Local: require six quiet seconds within 30 minutes; global: never kill active work."""
    deadline, quiet = time.monotonic() + 1800, None  # Local: use time unaffected by clock changes.
    while time.monotonic() < deadline:  # Global: abandoned workers expire.
        if app_running(executable):  # Local: reopening resets the quiet period.
            quiet = None  # Global: do not repair through a transient exit.
        elif quiet is None:  # Local: record the beginning of continuous absence.
            quiet = time.monotonic()  # Local: begin a grace period without claiming to observe buffer flushing.
        elif time.monotonic() - quiet >= 6:  # Global: require sustained observed absence, not proof of orderly shutdown.
            return  # Local: the caller still performs final guards.
        time.sleep(2)  # Local: avoid expensive busy polling.
    raise TimeoutError("Codex remained open for 30 minutes; nothing applied")  # Global: no timeout overrides safety guards.


@contextmanager  # Global: release the kernel handle on every exit path.
def single_worker(home):
    """Local: reserve a profile-specific named object; global: exclude workers in this Windows session."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)  # Local: capture native result codes.
    kernel.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]  # Local: preserve native pointer widths.
    kernel.CreateMutexW.restype = wintypes.HANDLE  # Local: receive a full-width handle.
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [wintypes.HANDLE], wintypes.BOOL  # Local: declare cleanup's ABI.
    identity = hashlib.sha256(os.path.normcase(str(Path(home).resolve())).encode()).hexdigest()  # Global: all output directories share the same profile guard.
    handle = kernel.CreateMutexW(None, False, "Local\\CodexProjectRepair-" + identity)  # Local: session namespace; the object expires when its last handle closes.
    error = ctypes.get_last_error()  # Local: capture ERROR_ALREADY_EXISTS before another API call.
    if not handle:  # Global: inability to lock blocks repair.
        raise ctypes.WinError(error)  # Local: expose the Windows failure.
    try:  # Global: even duplicate acquisition closes its own handle.
        if error == 183:  # Local: another worker still holds this named object.
            raise RuntimeError("A repair worker already exists for this profile")  # Global: no second write workflow starts.
        yield  # Local: run the protected lifecycle.
    finally:  # Global: release even after backup or validation failures.
        kernel.CloseHandle(handle)  # Local: never remove another worker's filesystem lock.


def reopen_app(app_id):  # Global: reopening is separate from successful state application.
    """Local: use the discovered AppUserModelID; global: avoid package-version paths."""
    subprocess.Popen(["explorer.exe", "shell:AppsFolder\\" + app_id], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # Local: ask Windows to open the desktop normally.
