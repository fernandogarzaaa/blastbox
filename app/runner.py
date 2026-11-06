"""Sandboxed execution for agent-written code.

Two backends, one policy:
- "local": dev and test backend. Runs the code in a fresh temp dir
  containing only input.csv, with a scrubbed environment, CPU/memory/
  file-size rlimits and a wall-clock timeout. This backend exists so
  the analysis logic can be developed and tested without Docker. It is
  not production containment.
- "docker": production backend for the Vultr VM. Builds a
  `docker run` command with --network none, --cap-drop ALL, memory,
  cpu and pids caps, a read-only input mount and --rm, so the
  container is destroyed after the run. No API keys or host paths
  are passed into the container.

Every run returns a receipt: hashes of code and input, the limits
applied, duration, and whether the run was blocked, timed out, or
completed. Nothing else is trusted as evidence of execution.
"""

import hashlib
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import time

from .policy import check

DEFAULT_TIMEOUT_S = 10
DEFAULT_MEMORY_MB = 256
DEFAULT_MAX_OUTPUT = 65536


def docker_command(image: str, input_csv: str, work_dir: str) -> list[str]:
    """Build the production Docker invocation. Pure function, unit tested.

    input.csv is mounted read-only at /work/input.csv, after the work
    volume mount, so the policy-allowed open('input.csv') resolves to
    the read-only file while task.py lives in the throwaway work dir.
    The container is removed after the run (--rm).
    """
    return [
        "docker", "run", "--rm",
        "--network", "none",
        "--cap-drop", "ALL",
        "--memory", "256m",
        "--cpus", "0.5",
        "--pids-limit", "64",
        "--read-only",
        "-w", "/work",
        "-v", f"{work_dir}:/work",
        "-v", f"{input_csv}:/work/input.csv:ro",
        "--env", "-i",
        image, "python3", "/work/task.py",
    ]


def _limits(memory_mb: int):
    def apply():
        mem = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        resource.setrlimit(resource.RLIMIT_CPU, (DEFAULT_TIMEOUT_S + 2, DEFAULT_TIMEOUT_S + 2))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    return apply


def run(code: str, csv_text: str, timeout_s: int = DEFAULT_TIMEOUT_S,
        memory_mb: int = DEFAULT_MEMORY_MB, backend: str = "local") -> dict:
    allowed, reason = check(code)
    started = time.monotonic()
    receipt_base = {
        "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
        "input_sha256": hashlib.sha256(csv_text.encode()).hexdigest(),
        "timeout_s": timeout_s,
        "memory_mb": memory_mb,
        "backend": backend,
    }
    if not allowed:
        return {**receipt_base, "status": "blocked", "reason": reason,
                "stdout": "", "stderr": "", "duration_ms": 0}
    if backend == "docker":
        if shutil.which("docker") is None:
            return {**receipt_base, "status": "error",
                    "reason": "docker binary not found on this host",
                    "stdout": "", "stderr": "", "duration_ms": 0}
        base = tempfile.mkdtemp(prefix="blastbox-docker-")
        work_dir = os.path.join(base, "work")
        os.makedirs(work_dir)
        input_csv = os.path.join(base, "input.csv")
        try:
            with open(input_csv, "w", encoding="utf-8") as fh:
                fh.write(csv_text)
            with open(os.path.join(work_dir, "task.py"), "w", encoding="utf-8") as fh:
                fh.write(code)
            image = os.environ.get("SANDBOX_IMAGE", "blastbox-sandbox:latest")
            try:
                proc = subprocess.run(
                    docker_command(image, input_csv, work_dir),
                    capture_output=True, text=True, timeout=timeout_s,
                    env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
                )
                status = "ok" if proc.returncode == 0 else "error"
                return {**receipt_base, "status": status, "exit_code": proc.returncode,
                        "stdout": proc.stdout[:DEFAULT_MAX_OUTPUT],
                        "stderr": proc.stderr[:DEFAULT_MAX_OUTPUT],
                        "duration_ms": int((time.monotonic() - started) * 1000)}
            except subprocess.TimeoutExpired:
                return {**receipt_base, "status": "timeout", "stdout": "",
                        "stderr": "", "duration_ms": int((time.monotonic() - started) * 1000)}
        finally:
            shutil.rmtree(base, ignore_errors=True)
    tmp = tempfile.mkdtemp(prefix="blastbox-")
    try:
        with open(os.path.join(tmp, "input.csv"), "w", encoding="utf-8") as fh:
            fh.write(csv_text)
        with open(os.path.join(tmp, "task.py"), "w", encoding="utf-8") as fh:
            fh.write(code)
        env = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}
        try:
            proc = subprocess.run(
                [sys.executable, "task.py"], cwd=tmp, env=env,
                capture_output=True, text=True, timeout=timeout_s,
                preexec_fn=_limits(memory_mb),
            )
            stdout = proc.stdout[:DEFAULT_MAX_OUTPUT]
            stderr = proc.stderr[:DEFAULT_MAX_OUTPUT]
            status = "ok" if proc.returncode == 0 else "error"
            return {**receipt_base, "status": status, "exit_code": proc.returncode,
                    "stdout": stdout, "stderr": stderr,
                    "stdout_truncated": len(proc.stdout) > DEFAULT_MAX_OUTPUT,
                    "duration_ms": int((time.monotonic() - started) * 1000)}
        except subprocess.TimeoutExpired as exc:
            return {**receipt_base, "status": "timeout",
                    "stdout": (exc.stdout or b"").decode(errors="replace")[:DEFAULT_MAX_OUTPUT] if isinstance(exc.stdout, bytes) else (exc.stdout or "")[:DEFAULT_MAX_OUTPUT],
                    "stderr": "", "duration_ms": int((time.monotonic() - started) * 1000)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
