"""Local: inspect and plan single-root changes. Global: preserve unrelated application state.

Source: https://docs.python.org/3.14/library/pathlib.html
"""
from pathlib import Path, PurePosixPath, PureWindowsPath  # Local: validate both path conventions explicitly.
from .windows import probe_root  # Global: keep filesystem interpretation outside the state transformation.


def projects(state):  # Global: reject unknown JSON layouts rather than guessing.
    """Local: select the observed legacy dictionary; global: retain every unselected entry."""
    if not isinstance(state, dict) or not isinstance(state.get("local-projects"), dict) or not isinstance(state.get("thread-project-assignments"), dict):  # Local: require the known top-level structures.
        raise ValueError("Unsupported state layout: expected legacy project and assignment dictionaries")  # Global: do not create missing structures.
    return state["local-projects"]  # Local: callers inspect, never mutate, this dictionary.


def linux_root(value):  # Global: accept only unambiguous, normalized Linux absolute roots.
    """Local: reject UNC, relative, traversal, and control-character forms."""
    return isinstance(value, str) and value.startswith("/") and not value.startswith("//") and ".." not in PurePosixPath(value).parts and not any(ord(c) < 32 for c in value) and str(PurePosixPath(value)) == value  # Local: preserve exact reviewable spelling.


def inspect_state(state):  # Global: diagnosis has no filesystem writes or implicit conversions.
    """Local: classify each legacy record; global: give users IDs to select explicitly."""
    result = []  # Local: return a compact diagnostic inventory.
    for project_id, record in projects(state).items():  # Local: visit without changing stored values.
        roots = record.get("rootPaths") if isinstance(record, dict) else None  # Global: malformed records stay visible as unsupported.
        supported = isinstance(record, dict) and record.get("id") == project_id and isinstance(roots, list) and len(roots) == 1 and linux_root(roots[0])  # Local: enforce the v1 repair shape.
        result.append({"id": project_id, "name": record.get("name") if isinstance(record, dict) else None, "roots": roots, "status": "linux_root" if supported else "not_a_supported_repair_target"})  # Global: do not promise fixes for other layouts.
    return result  # Local: callers can print this read-only report.


def create_plan(state, home, selected, distro, detach_missing):  # Global: require explicit project selection and WSL authority.
    """Local: resolve selected roots; global: make every future mutation reviewable."""
    if not selected or len(set(selected)) != len(selected) or not distro.strip():  # Local: reject empty or duplicate selections.
        raise ValueError("Select unique project IDs and an explicit WSL distribution")  # Global: never repair every project by default.
    inventory = {item["id"]: item for item in inspect_state(state)}  # Local: reuse the same supported-layout classification.
    changes = []  # Local: build a proposal without modifying source state.
    for project_id in selected:  # Global: stay within the user's selected IDs.
        item = inventory.get(project_id)  # Local: do not resolve names to potentially ambiguous identities.
        if not item or item["status"] != "linux_root":  # Global: reject multi-root and malformed records.
            raise ValueError(f"Unsupported or missing repair target: {project_id}")  # Local: require manual review.
        root = item["roots"][0]  # Local: the classifier proved this is a single Linux root.
        target = probe_root(distro, root)  # Global: verify the folder through the selected environment.
        if not target and not detach_missing:  # Local: absence alone does not authorize detachment.
            raise ValueError(f"Missing folder for {project_id}; use --detach-missing only after review")  # Global: preserve its link by default.
        changes.append({"id": project_id, "old_root": root, "new_roots": target})  # Local: reuse the proven pure transformation format.
    plan = {"schema_version": 1, "home": str(Path(home).resolve()), "distro": distro, "detach_missing": detach_missing, "changes": changes}  # Global: bind the proposal to one profile and environment.
    validate_plan(plan, home)  # Local: generated and loaded plans use the same checks.
    return plan  # Global: no live state has been written.


def validate_plan(plan, home):  # Global: treat editable plan files as data, not trusted instructions.
    """Local: check types, identity, and allowed transformations; global: reject unexpected edits."""
    if not isinstance(plan, dict) or plan.get("schema_version") != 1 or not isinstance(plan.get("home"), str) or Path(plan["home"]).resolve() != Path(home).resolve():  # Local: require this schema and profile.
        raise ValueError("Unsupported plan or different Codex profile")  # Global: never apply another machine's plan implicitly.
    if not isinstance(plan.get("distro"), str) or not plan["distro"].strip() or type(plan.get("detach_missing")) is not bool:  # Local: require explicit environment and detachment intent.
        raise ValueError("Invalid plan distribution or detachment flag")  # Global: reject ambiguous inputs.
    changes = plan.get("changes")  # Local: inspect the exact proposed mutations.
    if not isinstance(changes, list) or not changes:  # Global: empty and malformed plans do not initiate repair.
        raise ValueError("Plan must contain selected project changes")  # Local: provide an actionable error.
    seen = set()  # Local: prevent duplicate project mutations.
    for change in changes:  # Global: validate every mutation before any is applied.
        if not isinstance(change, dict) or not isinstance(change.get("id"), str) or change["id"] in seen or not linux_root(change.get("old_root")):  # Local: validate identity and original path convention.
            raise ValueError("Invalid or duplicate plan entry")  # Global: no partial application.
        seen.add(change["id"])  # Local: reserve this project identity.
        roots = change.get("new_roots")  # Local: only zero or one new root is supported.
        valid = isinstance(roots, list) and (roots == [] and plan["detach_missing"] or len(roots) == 1 and isinstance(roots[0], str) and PureWindowsPath(roots[0]).is_absolute())  # Global: keep destination paths Windows-native.
        if not valid:  # Local: unknown root shapes cannot be serialized into live state.
            raise ValueError("Invalid Windows destination or unauthorized detachment")  # Global: require an intentional plan.
