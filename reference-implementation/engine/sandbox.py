"""Process sandbox for tools that touch files or the network (JH-C11 G-B17, Brown: "agents with their own
computer").

A tool declared ``sandbox=True``, or any call whose targets name a network host, runs under
``tools.sandbox: subprocess`` in a fresh child interpreter (engine/sandbox_child.py), never in the engine
process.  Per run the engine creates one workspace directory (the agent's own computer), deleted when the run
finishes, and checks ``tools.workspace_quota_mb`` after every call.

What the child IS isolated from:
- the engine's memory, store connection, ledger and secrets: it is a separate process started with
  ``python -I -B`` (no PYTHON* variables, no user site) and an environment scrubbed to nothing but what the OS
  needs to start Python (SYSTEMROOT on Windows), so DATABASE_URL, API keys and tokens are not inherited;
- the network, except the hosts the agent's access.yaml grants: an audit hook installed before the tool module
  is imported refuses ``socket.connect``/``sendto`` to any address that is not a granted host (or an address
  a granted host resolved to) and ``getaddrinfo`` of any other name.  Audit hooks cannot be removed from
  inside the interpreter, so a tool that skips access.check_network still cannot connect;
- spawning processes and loading native code: ``subprocess.Popen``, ``os.system``, ``os.exec*``,
  ``os.posix_spawn``, ``os.spawn*``, ``os.startfile`` and ``ctypes.dlopen`` are refused;
- writing outside its workspace: ``open`` for writing and ``os.remove/rename/mkdir/rmdir/...`` on a path
  outside the workspace are refused.  Granted files the call targets are copied into the workspace first.

What it is NOT isolated from (no OS-level jail is assumed; the same code runs on Windows and Linux):
- READS: the child can read any file the OS user can read (the interpreter must read the stdlib); confine
  reads with access.yaml file grants and the ``files.read`` tool, which stays in process and confined;
- CPU and memory: bounded only by ``tools.sandbox_timeout_seconds`` (the child is killed) and the quota check;
- a native extension module already importable that opens sockets below the Python socket layer.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from engine.config import ENGINE_ROOT
from engine.errors import ToolError

CHILD = Path(__file__).resolve().parent / "sandbox_child.py"
RESULT_MARK = "@@harness-sandbox-result@@ "


def _scrubbed_env() -> dict:
    env = {}
    if os.name == "nt":
        for k in ("SYSTEMROOT", "SystemRoot"):
            if k in os.environ:
                env["SYSTEMROOT"] = os.environ[k]
                break
    return env


def _size_bytes(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


class RunSandbox:
    """One per run: the workspace, the quota, and the child-process dispatch."""

    def __init__(self, *, run_id: str, mode: str, quota_mb: int, timeout_seconds: float, pack) -> None:
        self.run_id = run_id
        self.mode = mode
        self.quota_bytes = int(quota_mb) * 1024 * 1024
        self.timeout = float(timeout_seconds)
        self.pack = pack
        self.workspace = Path(tempfile.gettempdir()) / "harness-sandbox" / run_id
        self.calls = 0

    @classmethod
    def for_run(cls, config, run_id: str, pack) -> "RunSandbox":
        c = config.sandbox
        return cls(run_id=run_id, mode=c["mode"], quota_mb=c["workspace_quota_mb"],
                   timeout_seconds=c["timeout_seconds"], pack=pack)

    def applies(self, spec, args: dict) -> bool:
        if self.mode != "subprocess":
            return False
        return spec.sandbox or any(t.kind == "network" for t in spec.targets(args))

    def call(self, spec, args: dict, ctx, record: dict | None = None):
        self.workspace.mkdir(parents=True, exist_ok=True)
        for t in spec.targets(args):
            if t.kind == "file" and t.mode == "read":
                src = ctx.access.check_file(t.name, "read")
                if src.is_file():
                    dst = self.workspace / t.name
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, dst)
        self.calls += 1
        sandbox_id = f"{self.run_id}:{self.calls}"
        payload = {
            "module": spec.fn.__module__, "qualname": spec.fn.__qualname__, "tool_id": spec.id,
            # -I drops user site-packages; the child imports from exactly the engine's own import path
            "sys_path": [str(ENGINE_ROOT), str(self.pack.root.parent)] + [p for p in sys.path if p and Path(p).is_dir()],
            "args": args, "workspace": str(self.workspace), "allowed_hosts": sorted(ctx.access.network),
            "run_id": self.run_id, "pack": self.pack.name,
        }
        try:
            proc = subprocess.run([sys.executable, "-I", "-B", str(CHILD)], input=json.dumps(payload),
                                  capture_output=True, text=True, encoding="utf-8", cwd=str(self.workspace),
                                  env=_scrubbed_env(), timeout=self.timeout)
        except subprocess.TimeoutExpired as e:
            if record is not None:
                record["sandbox"] = {"id": sandbox_id, "exit": None, "timeout": True}
            raise ToolError(f"sandboxed tool {spec.id!r} exceeded {self.timeout}s") from e
        if record is not None:
            record["sandbox"] = {"id": sandbox_id, "exit": proc.returncode}
        marked = [ln[len(RESULT_MARK):] for ln in proc.stdout.splitlines() if ln.startswith(RESULT_MARK)]
        if not marked:
            raise ToolError(f"sandboxed tool {spec.id!r} exited {proc.returncode} without a result: "
                            f"{proc.stderr.strip()[-300:]}")
        out = json.loads(marked[-1])
        used = _size_bytes(self.workspace)
        if used > self.quota_bytes:
            raise ToolError(f"sandbox workspace holds {used} bytes, over the {self.quota_bytes}-byte quota")
        if not out["ok"]:
            raise ToolError(f"sandboxed tool {spec.id!r}: {out['error']}")
        return out["result"]

    def close(self) -> None:
        if self.workspace.exists():
            shutil.rmtree(self.workspace, ignore_errors=True)
