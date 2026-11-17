#!/usr/bin/env python3
"""Gọi Concat (trình dựng video mã nguồn mở, https://github.com/jub0t/Concat) từ Python qua MCP, không cần mở cửa sổ.

Cài (Linux x86_64, không cần quyền root):
  python3 -I concat_mcp.py install        # tải bản .deb mới nhất từ trang Concat, giải nén vào ~/.local/concat
Dùng:
  from concat_mcp import Concat
  with Concat() as c:
      c.call("project_create", {"location": "/home/claude/pumdung/test", "name": "v1"})
Biến môi trường: CONCAT_BIN (đường dẫn chương trình), CONCAT_MCP_ROOTS (thư mục được phép ghi, mặc định /home/claude).
"""
import json, os, re, subprocess, sys, shutil, urllib.request
from pathlib import Path

HOME_BIN = Path.home() / ".local" / "concat"
def binary():
    for p in [os.environ.get("CONCAT_BIN"), str(HOME_BIN / "opt/concat/concat"), "/opt/concat/concat", shutil.which("concat")]:
        if p and Path(p).exists(): return p
    raise SystemExit("chưa cài Concat: chạy `python3 -I concat_mcp.py install`")

def install():
    html = urllib.request.urlopen(urllib.request.Request("https://concat.standalones.org/", headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read().decode()
    m = re.search(r"https://github\.com/jub0t/Concat/releases/download/[^\"']+linux-x86_64\.deb", html)
    if not m: raise SystemExit("không tìm thấy bản .deb cho Linux trên trang Concat")
    d = Path("/tmp/concat-dl"); d.mkdir(exist_ok=True); deb = d / "concat.deb"
    print("tải", m[0]); subprocess.run(["curl", "-sL", "-m", "600", "-o", str(deb), m[0]], check=True)
    HOME_BIN.mkdir(parents=True, exist_ok=True)
    subprocess.run(["dpkg-deb", "-x", str(deb), str(HOME_BIN)], check=True)
    print("đã cài:", HOME_BIN / "opt/concat/concat")

class Concat:
    def __init__(self, roots=None):
        env = dict(os.environ); env["CONCAT_MCP_ROOTS"] = roots or env.get("CONCAT_MCP_ROOTS", "/home/claude")
        self.p = subprocess.Popen([binary(), "--mcp", "headless"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=env, bufsize=1)
        self.i = 0
        self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "pum-dung", "version": "1"}})
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"); self.p.stdin.flush()
    def _rpc(self, method, params):
        self.i += 1; self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.i, "method": method, "params": params}) + "\n"); self.p.stdin.flush()
        while True:
            line = self.p.stdout.readline()
            if not line: raise RuntimeError("Concat đã dừng")
            d = json.loads(line)
            if d.get("id") == self.i:
                if "error" in d: raise RuntimeError(f"{method}: {d['error']}")
                return d["result"]
    def call(self, name, args=None):
        r = self._rpc("tools/call", {"name": name, "arguments": args or {}})
        if r.get("isError"): raise RuntimeError(f"{name}: {r['content'][0]['text'][:600]}")
        if r.get("structuredContent") is not None: return r["structuredContent"]
        c = (r.get("content") or [{}])[0]
        if c.get("type") == "text":
            try: return json.loads(c["text"])
            except ValueError: return c["text"]
        return c
    def tools(self): return self._rpc("tools/list", {})["tools"]
    def close(self):
        try: self.p.stdin.close(); self.p.wait(10)
        except Exception: self.p.kill()
    def __enter__(self): return self
    def __exit__(self, *a): self.close()

if __name__ == "__main__":
    if sys.argv[1:2] == ["install"]: install()
    else:
        with Concat() as c: print(json.dumps(c.call("concat_version"), ensure_ascii=False, indent=1))
