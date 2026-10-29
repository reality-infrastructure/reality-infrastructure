"""gdex_stdio_client.py — drive the SAME gdex MCP server binary over its stdio JSON-RPC
interface when a session's MCP client cannot connect to it (PREREG A13 R67).

The server is `npx -y @gemachdao/gdex-mcp-server`, the entry in ~/.claude.json, with the
same ~/.gdex account store; the tools, their arguments and the terms are identical to the
MCP path the hand used on Days 3–6. This client observes nothing on its own and submits
nothing on its own: it forwards exactly one tool call per invocation and prints the server's
response verbatim (and saves it beside the previews when --save is given). No secret enters
the conversation: gdex_connect reads the control-wallet key file on this machine itself.

Usage:
  python gdex_stdio_client.py list
  python gdex_stdio_client.py call <tool> '<json args>' [--save <path>] [--timeout S]
"""
from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

SERVER_CMD = ["npx.cmd" if sys.platform == "win32" else "npx", "-y", "@gemachdao/gdex-mcp-server"]


class Server:
    def __init__(self) -> None:
        self.p = subprocess.Popen(
            SERVER_CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1,
        )
        self.q: queue.Queue = queue.Queue()
        self.err: list[str] = []
        self.n = 0
        threading.Thread(target=self._read_out, daemon=True).start()
        threading.Thread(target=self._read_err, daemon=True).start()

    def _read_out(self) -> None:
        assert self.p.stdout is not None
        for line in self.p.stdout:
            line = line.strip()
            if line.startswith("{"):
                try:
                    self.q.put(json.loads(line))
                except ValueError:
                    pass

    def _read_err(self) -> None:
        assert self.p.stderr is not None
        for line in self.p.stderr:
            self.err.append(line.rstrip())

    def _send(self, msg: dict) -> None:
        assert self.p.stdin is not None
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()

    def call(self, method: str, params: dict | None = None, timeout: float = 120) -> dict:
        self.n += 1
        i = self.n
        self._send({"jsonrpc": "2.0", "id": i, "method": method, "params": params or {}})
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                m = self.q.get(timeout=1)
            except queue.Empty:
                continue
            if m.get("id") == i:
                return m
        raise TimeoutError(method)

    def notify(self, method: str, params: dict | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def close(self) -> None:
        try:
            self.p.terminate()
        except Exception:
            pass


def start(timeout: float = 150) -> Server:
    s = Server()
    s.call(
        "initialize",
        {"protocolVersion": "2024-11-05", "capabilities": {},
         "clientInfo": {"name": "ri-agent-record-stdio", "version": "A13"}},
        timeout=timeout,
    )
    s.notify("notifications/initialized")
    return s


def tool_text(resp: dict) -> str:
    """The server's text content, verbatim, as the MCP client would show it."""
    res = resp.get("result")
    if isinstance(res, dict):
        parts = [c.get("text", "") for c in res.get("content", []) if c.get("type") == "text"]
        if parts:
            return "\n".join(parts)
        return json.dumps(res)
    return json.dumps(resp)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    save: str | None = None
    timeout = 120.0
    args = list(argv)
    if "--save" in args:
        i = args.index("--save")
        save = args[i + 1]
        del args[i:i + 2]
    if "--timeout" in args:
        i = args.index("--timeout")
        timeout = float(args[i + 1])
        del args[i:i + 2]
    s = start()
    try:
        if args[0] == "list":
            r = s.call("tools/list")
            for t in r["result"]["tools"]:
                print(t["name"])
            return 0
        if args[0] == "call":
            name = args[1]
            params = json.loads(args[2]) if len(args) > 2 else {}
            t_sent = int(time.time() * 1000)
            r = s.call("tools/call", {"name": name, "arguments": params}, timeout=timeout)
            t_recv = int(time.time() * 1000)
            text = tool_text(r)
            print(text)
            if save:
                Path(save).write_text(
                    json.dumps({"tool": name, "arguments": params, "sent_ms": t_sent,
                                "received_ms": t_recv, "response_text": text,
                                "raw": r}, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")
            return 0
        print(__doc__)
        return 2
    finally:
        s.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
