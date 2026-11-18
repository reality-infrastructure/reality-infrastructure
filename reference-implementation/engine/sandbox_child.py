"""Child side of engine/sandbox.py.  Started as ``python -I -B sandbox_child.py`` with the call on stdin.

The audit hook goes in before any tool code is imported and cannot be removed afterwards.  See
engine/sandbox.py for exactly what it refuses and what it does not cover.
"""

import json
import os
import socket
import sys

RESULT_MARK = "@@harness-sandbox-result@@ "
_SPAWN = ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.startfile",
          "os.fork", "ctypes.dlopen")
_PATH_EVENTS = {"os.remove": (0,), "os.rename": (0, 1), "os.mkdir": (0,), "os.rmdir": (0,), "os.chmod": (0,),
                "os.symlink": (0, 1), "os.link": (0, 1), "os.truncate": (0,), "os.utime": (0,),
                "shutil.rmtree": (0,), "shutil.move": (0, 1), "shutil.copyfile": (1,)}
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC


class SandboxContext:
    """What a sandboxed tool body may use: its workspace, its granted hosts, its run id."""

    def __init__(self, workspace: str, network: list[str], run_id: str, pack: str) -> None:
        self.workspace = workspace
        self.network = frozenset(network)
        self.run_id = run_id
        self.pack = pack


def _install_guard(workspace: str, allowed: frozenset) -> None:
    root = os.path.normcase(os.path.realpath(workspace))
    resolved: set = set(allowed)
    real_getaddrinfo = socket.getaddrinfo

    def inside(path) -> bool:
        if isinstance(path, int):
            return True                      # an already-open descriptor
        p = os.path.normcase(os.path.realpath(os.fsdecode(path)))
        return p == root or p.startswith(root + os.sep)

    def hook(event, args):
        if event == "socket.getaddrinfo":
            if args[0] is not None and str(args[0]) not in allowed and str(args[0]) not in resolved:
                raise PermissionError(f"sandbox: name lookup of {args[0]!r} blocked")
        elif event in ("socket.connect", "socket.sendto", "socket.sendmsg"):
            address = args[1] if event != "socket.sendmsg" else args[-1]
            host = address[0] if isinstance(address, tuple) else address
            if str(host) not in resolved:
                raise PermissionError(f"sandbox: network to {host!r} blocked")
        elif event.startswith(_SPAWN):
            raise PermissionError(f"sandbox: {event} blocked")
        elif event == "open":
            path, mode, flags = args
            writing = (mode is not None and any(c in str(mode) for c in "wax+")) or (
                mode is None and isinstance(flags, int) and flags & _WRITE_FLAGS)
            if writing and not inside(path):
                raise PermissionError(f"sandbox: write to {path!r} outside the workspace blocked")
        elif event in _PATH_EVENTS:
            for i in _PATH_EVENTS[event]:
                if i < len(args) and args[i] is not None and not inside(args[i]):
                    raise PermissionError(f"sandbox: {event} on {args[i]!r} outside the workspace blocked")

    def getaddrinfo(host, *a, **kw):
        out = real_getaddrinfo(host, *a, **kw)
        if host is not None and str(host) in allowed:
            resolved.update(str(r[4][0]) for r in out)
        return out

    socket.getaddrinfo = getaddrinfo
    sys.addaudithook(hook)


def main() -> None:
    call = json.loads(sys.stdin.read())
    sys.dont_write_bytecode = True
    for p in reversed(call["sys_path"]):
        sys.path.insert(0, p)
    _install_guard(call["workspace"], frozenset(call["allowed_hosts"]))
    try:
        import importlib
        obj = importlib.import_module(call["module"])
        for part in call["qualname"].split("."):
            obj = getattr(obj, part)
        result = obj(call["args"], SandboxContext(call["workspace"], call["allowed_hosts"], call["run_id"],
                                                  call["pack"]))
        out = {"ok": True, "result": result}
    except Exception as e:  # noqa: BLE001 - reported to the parent, which raises ToolError
        out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    sys.stdout.write("\n" + RESULT_MARK + json.dumps(out, sort_keys=True, default=str) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
