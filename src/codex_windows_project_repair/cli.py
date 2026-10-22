"""Local: four readable CLI phases. Global: default to inspection, never automatic repair.

Sources: https://docs.python.org/3.14/library/argparse.html and https://docs.python.org/3.14/library/logging.html
"""
import argparse  # Local: expose explicit diagnosis, planning, application, and verification commands.
import hashlib  # Local: bind scheduled execution to the reviewed plan bytes.
import json  # Local: print complete structured results to stdout.
import logging  # Global: stream operational diagnostics to stderr and timestamped files.
import os  # Local: refuse non-Windows execution before touching app state.
import subprocess  # Local: classify failures from Windows discovery commands.
import sys  # Local: return useful process exit codes.
import time  # Local: format log timestamps in UTC.
from datetime import datetime, timezone  # Local: name log files unambiguously.
from pathlib import Path  # Local: resolve explicit CLI paths.
from .config import Settings, parse_json, read_json  # Global: keep configuration and JSON handling reusable.
from .planning import create_plan, inspect_state  # Local: import the read-only planning phases.
from .windows import discover_app, list_distros  # Local: inspect only relevant installed services.
from .workflow import apply_plan, preflight, verify_backup  # Global: delegate implementation to named phases.


def parser():  # Global: keep user input interpretation separate from mutation logic.
    """Local: define four commands; global: require explicit application of a saved plan."""
    root = argparse.ArgumentParser(description="Backed-up repair of legacy WSL project roots in Windows Codex Desktop")  # Local: describe the narrow purpose.
    root.add_argument("--home", type=Path, help="Override CODEX_REPAIR_HOME")  # Local: allow deterministic scheduler and fixture configuration.
    root.add_argument("--output", type=Path, help="Override CODEX_REPAIR_OUTPUT")  # Local: keep generated private files separate.
    commands = root.add_subparsers(dest="command")  # Global: absent command becomes read-only inspect.
    commands.add_parser("inspect", help="Read-only profile and installation diagnosis")  # Local: safe first interaction.
    plan = commands.add_parser("plan", help="Save a proposal for explicitly selected single-root projects")  # Global: planning does not change app state.
    plan.add_argument("--project", action="append", required=True, help="Project ID; repeat for additional selected projects")  # Local: never select every candidate implicitly.
    plan.add_argument("--distro", required=True, help="Exact WSL distribution name")  # Global: avoid guessing Linux filesystem ownership.
    plan.add_argument("--detach-missing", action="store_true", help="Explicitly allow clearing verified missing folder links")  # Local: preserve project and chat records.
    plan.add_argument("--save", type=Path, help="New plan file; defaults to output/plan.json")  # Global: refuse overwriting existing review plans.
    apply = commands.add_parser("apply", help="Back up and apply a reviewed plan while Codex is closed")  # Local: sole public write command.
    apply.add_argument("--plan", required=True, type=Path)  # Global: require an inspectable proposal.
    apply.add_argument("--check-only", action="store_true", help="Validate without waiting, backing up, or applying")  # Local: scheduler preflight.
    apply.add_argument("--wait", action="store_true", help="Wait up to 30 minutes for user-controlled exit")  # Global: use the scheduler when called from Codex.
    apply.add_argument("--reopen", action="store_true", help="Request desktop launch after successful repair")  # Local: separate launch intent from mutation.
    apply.add_argument("--plan-sha256", help="Require these reviewed plan bytes; used by the scheduler")  # Global: reject a plan edited after scheduling.
    verify = commands.add_parser("verify", help="Read-only preservation comparison against a backup")  # Local: make validation independent of application.
    verify.add_argument("--backup", required=True, type=Path)  # Global: require a specific recovery snapshot.
    return root  # Local: parser construction has no filesystem side effects.


def execute(args, settings):  # Global: readable wrapper calling named implementation phases.
    """Local: dispatch one command; global: keep inspection and verification read-only."""
    command = args.command or "inspect"  # Local: no command never means apply.
    if command == "inspect":  # Global: inventory without creating plans or state backups.
        report = {"home": str(settings.home), "projects": inspect_state(read_json(settings.state))}  # Local: include IDs needed for explicit selection.
        for name, function in (("desktop", discover_app), ("wsl_distributions", list_distros)):  # Local: independent diagnostics remain useful if one service is unavailable.
            try:  # Global: an unavailable service must not hide the profile inventory.
                report[name] = function()  # Local: query installed metadata.
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:  # Local: expose diagnostic failures without inferring absence.
                report[name + "_error"] = str(error)  # Global: the apply phase still fails closed.
        return report  # Local: stdout contains no chat bodies.
    if command == "plan":  # Global: save a review artifact, never live app state.
        if args.distro not in list_distros():  # Local: require an exact registered distribution.
            raise ValueError("WSL distribution is not registered; run inspect")  # Global: no fallback distro is selected.
        proposal = create_plan(read_json(settings.state), settings.home, args.project, args.distro, args.detach_missing)  # Local: validate and resolve selected roots.
        destination = (args.save or settings.output / "plan.json").resolve()  # Local: choose an explicit private plan path.
        if destination.is_relative_to(settings.home):  # Global: prevent writing a plan into Codex's own profile.
            raise ValueError("Save the plan outside the Codex profile")  # Local: separate artifacts from application state.
        destination.parent.mkdir(parents=True, exist_ok=True)  # Local: create only the review-artifact directory.
        with destination.open("x", encoding="utf-8") as stream:  # Global: never overwrite a reviewed plan.
            json.dump(proposal, stream, indent=2, ensure_ascii=False)  # Local: retain full old and new paths for review.
        return {"plan_file": str(destination), "plan": proposal}  # Global: make the concrete proposed changes visible.
    if command == "apply":  # Local: require explicit selection of the mutating workflow.
        original_plan = args.plan.read_bytes()  # Local: capture the bytes being authorized.
        proposal = parse_json(original_plan)  # Global: validate exactly the bytes whose digest is checked.
        if args.plan.read_bytes() != original_plan or args.plan_sha256 and hashlib.sha256(original_plan).hexdigest().lower() != args.plan_sha256.lower():  # Global: enforce scheduling-time review integrity.
            raise ValueError("Plan changed after review or scheduling")  # Local: refuse stale authorization.
        if args.check_only:  # Global: preflight never enters the mutation lifecycle.
            return preflight(settings, proposal)  # Local: also expose resolved paths to the launcher.
        return apply_plan(settings, proposal, wait=args.wait, reopen=args.reopen)  # Global: guards, backup, and commit stay in one coordinator.
    return verify_backup(settings, args.backup)  # Local: the remaining command is read-only verification.


def main():  # Global: package entry point; argument errors exit before logger setup.
    """Local: resolve configuration and logging; global: never hide a failed repair."""
    args = parser().parse_args()  # Local: help exits before any profile access.
    if os.name != "nt":  # Global: the Windows metadata-preserving writer is platform-specific.
        raise SystemExit("This utility supports native Windows only")  # Local: prevent accidental WSL-host execution.
    defaults = Settings.from_env()  # Local: uv loads .env before invoking the entry point.
    settings = Settings((args.home or defaults.home).resolve(), (args.output or defaults.output).resolve())  # Global: bind this invocation to absolute paths.
    handlers = [logging.StreamHandler()]  # Local: inspect and verify leave no report files by default.
    if args.command in ("plan", "apply"):  # Global: only operational commands create timestamped audit files.
        if settings.output.is_relative_to(settings.home):  # Local: keep every generated report outside app state.
            raise SystemExit("Output directory must be outside the Codex profile")  # Global: prevent report path collisions with live data.
        settings.output.mkdir(parents=True, exist_ok=True)  # Local: create the private audit directory.
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")  # Local: avoid log filename collisions.
        handlers.append(logging.FileHandler(settings.output / f"repair-{stamp}.log", encoding="utf-8"))  # Global: retain diagnostics emitted after setup; earlier failures have no log here.
    logging.Formatter.converter = time.gmtime  # Local: use UTC consistently with report timestamps.
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)sZ %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S", handlers=handlers)  # Global: emit log events to file/stderr; child command output is buffered until completion.
    try:  # Global: every runtime failure produces a nonzero exit code.
        result = execute(args, settings)  # Local: perform the selected named workflow.
        print(json.dumps(result, indent=2, ensure_ascii=False))  # Global: print complete results without truncation.
        if args.command in ("plan", "apply"):  # Local: persist operational results alongside command diagnostics.
            logging.info("Result: %s", json.dumps(result, ensure_ascii=False))  # Global: no LLMs or chat content are involved.
        return 2 if args.command == "verify" and not result["records_preserved"] else 0  # Local: preservation mismatches require review.
    except Exception:  # Global: retain the complete traceback rather than a generic success toast.
        logging.exception("Command failed; inspect the log and any backup in status.json")  # Local: preserve diagnostic context.
        return 1  # Global: scripts and CI can detect failure.


if __name__ == "__main__":  # Local: support both module and installed console invocation.
    sys.exit(main())  # Global: propagate the selected phase's result to the shell.
