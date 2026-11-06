"""Static policy gate for agent-written code, checked before any execution.

This is the first containment layer. The second layer is the execution
environment itself: a fresh Docker container per run on the Vultr VM
(--network none, --cap-drop ALL, memory/cpu/pids caps, read-only input
mount, destroyed after the run). The local dev backend in runner.py
applies the same policy plus OS resource limits, but it is NOT claimed
as production containment. Production containment is Docker.
"""

import ast

BLOCKED_MODULES = {
    "os", "sys", "subprocess", "socket", "urllib", "requests", "pathlib",
    "shutil", "pty", "signal", "ctypes", "multiprocessing", "threading",
    "http", "ftplib", "smtplib", "webbrowser", "importlib",
}

BLOCKED_CALLS = {"eval", "exec", "compile", "__import__", "input", "breakpoint"}


def _open_allowed(node: ast.Call) -> bool:
    """open() is allowed only on the literal 'input.csv' in read mode.

    This is the one sanctioned file access: the sandbox directory
    contains only input.csv and task.py, and the Docker backend mounts
    input.csv read-only. Any other path, and any write mode, is blocked.
    """
    if not node.args or not isinstance(node.args[0], ast.Constant):
        return False
    if node.args[0].value != "input.csv":
        return False
    mode = "r"
    if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
        mode = node.args[1].value
    for kw in node.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            mode = kw.value.value
    return isinstance(mode, str) and set(mode) <= set("rbtU") and "r" in mode

ALLOWED_MODULES = {"csv", "json", "math", "statistics", "collections", "re", "datetime"}


def check(code: str) -> tuple[bool, str]:
    """Return (allowed, reason). Reason is empty when allowed."""
    if not code or not code.strip():
        return False, "empty code"
    if len(code) > 20000:
        return False, "code exceeds 20000 characters"
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, f"syntax error: {exc}"
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                if name in BLOCKED_MODULES:
                    return False, f"blocked import: {name}"
                if name not in ALLOWED_MODULES:
                    return False, f"import not on allowlist: {name}"
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "open" and not _open_allowed(node):
                return False, "blocked open(): only open('input.csv') in read mode is allowed"
            if isinstance(func, ast.Name) and func.id in BLOCKED_CALLS:
                return False, f"blocked call: {func.id}"
            if isinstance(func, ast.Attribute) and func.attr in BLOCKED_CALLS:
                return False, f"blocked call: {func.attr}"
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return False, f"blocked dunder attribute: {node.attr}"
    return True, ""
