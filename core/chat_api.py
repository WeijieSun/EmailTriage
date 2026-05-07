"""Lightweight chat HTTP server using Python's built-in http.server.

No asyncio/uvicorn needed — avoids event loop conflicts with Streamlit.
Runs on port 8502 as a daemon thread.
"""
from __future__ import annotations
import json, subprocess, shutil, tempfile, os, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


def _find_claude() -> str:
    candidates = [
        shutil.which("claude"),
        r"C:\Users\admin\AppData\Roaming\npm\claude.cmd",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return "claude"


def call_claude_standalone(prompt: str, timeout: int = 120) -> str:
    claude_bin = _find_claude()
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8-sig"
        ) as f:
            f.write(prompt)
            tmp = f.name
        ps_cmd = (
            f"$OutputEncoding = [System.Text.Encoding]::UTF8; "
            f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
            f"Get-Content -Raw -Encoding UTF8 '{tmp}' | & '{claude_bin}' --print"
        )
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=timeout, encoding="utf-8",
            cwd=tempfile.gettempdir(),
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return f"⚠️ Claude error: {(result.stderr or '').strip()[:200] or 'rc=' + str(result.returncode)}"
    except subprocess.TimeoutExpired:
        return f"⚠️ 超时（>{timeout}s）"
    except Exception as e:
        return f"⚠️ {e}"
    finally:
        if tmp and os.path.exists(tmp):
            try: os.unlink(tmp)
            except Exception: pass


class ChatHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # suppress access logs

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            message = body.get("message", "")
            if not message:
                reply = "⚠️ 消息为空"
            else:
                from .email_assistant import answer
                reply = answer(message, lambda p, timeout=120: (call_claude_standalone(p, timeout), ""))
        except Exception as e:
            reply = f"⚠️ 服务器错误: {e}"

        resp = json.dumps({"reply": reply}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


_server_started = False
_lock = threading.Lock()


def start_chat_server(port: int = 8502) -> None:
    global _server_started
    with _lock:
        if _server_started:
            return
        _server_started = True

    def _run():
        class ReuseServer(HTTPServer):
            allow_reuse_address = True
        server = ReuseServer(("127.0.0.1", port), ChatHandler)
        server.serve_forever()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
