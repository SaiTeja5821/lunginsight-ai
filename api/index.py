"""
Vercel WSGI entry-point for LungInsight AI.

Vercel's @vercel/python builder calls `application(environ, start_response)`
for every HTTP request.  This file bridges the existing app.py
(BaseHTTPRequestHandler) into that WSGI interface.

SQLite user.db lives in /tmp (writable, but ephemeral per Vercel instance).
Registered users persist as long as the same warm instance handles the request.
"""
from __future__ import annotations

import io
import os
import sys
import json
import traceback
import sqlite3
from urllib.parse import urlparse

# ── 1. Put project root on sys.path ─────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── 2. Configure paths BEFORE importing app ──────────────────────────────────
_DB_PATH = "/tmp/user.db"
_ANALYSIS_FOLDER = os.path.join(ROOT, "analysis_data")

os.environ.setdefault("DB_PATH", _DB_PATH)
os.environ.setdefault("ANALYSIS_FOLDER", _ANALYSIS_FOLDER)

# ── 3. Import and patch app module globals ───────────────────────────────────
import app as _app                      # noqa: E402  (must come after sys.path)

_app.DB_PATH          = _DB_PATH
_app.ANALYSIS_FOLDER  = _ANALYSIS_FOLDER

# Initialise DB tables (idempotent — safe to call on every cold start)
_app.init_db(_DB_PATH)


# ── 4. Minimal wfile shim that accumulates bytes ─────────────────────────────
class _ByteCollector(io.RawIOBase):
    def __init__(self):
        self._buf = bytearray()

    def write(self, b: bytes | bytearray) -> int:          # type: ignore[override]
        self._buf.extend(b)
        return len(b)

    def getvalue(self) -> bytes:
        return bytes(self._buf)


# ── 5. WSGI application ──────────────────────────────────────────────────────
def application(environ: dict, start_response):           # noqa: C901
    """
    WSGI callable invoked by Vercel for every request.
    Instantiates LungInsightHandler, feeds it the request, captures the
    HTTP/1.1 response bytes, and returns them as a WSGI response.
    """
    # Re-init DB on each call (no-op when tables already exist)
    try:
        _app.init_db(_DB_PATH)
    except Exception:
        pass

    method  = environ.get("REQUEST_METHOD", "GET").upper()
    path    = environ.get("PATH_INFO",      "/") or "/"
    qs      = environ.get("QUERY_STRING",   "") or ""
    cl      = int(environ.get("CONTENT_LENGTH") or 0)
    ct      = environ.get("CONTENT_TYPE",   "") or ""
    host    = environ.get("HTTP_HOST",      "localhost")
    body    = environ["wsgi.input"].read(cl) if cl > 0 else b""

    full_path = f"{path}?{qs}" if qs else path

    # ── Build a minimal HTTP/1.1 request byte-stream ─────────────────────────
    # BaseHTTPRequestHandler.parse_request() reads:
    #   1. self.raw_requestline  → one readline() call
    #   2. self.headers          → http.client.parse_headers(rfile)
    # After parse_request(), do_POST calls _read_json_body() which does
    # self.rfile.read(Content-Length).  We must position rfile correctly.

    req_line = f"{method} {full_path} HTTP/1.1\r\n"
    hdr_block = f"Host: {host}\r\n"
    if ct:
        hdr_block += f"Content-Type: {ct}\r\n"
    if cl:
        hdr_block += f"Content-Length: {cl}\r\n"
    # Forward any extra HTTP_* headers from environ
    for k, v in environ.items():
        if k.startswith("HTTP_"):
            name = k[5:].replace("_", "-").title()
            if name.lower() not in ("host",):
                hdr_block += f"{name}: {v}\r\n"
    hdr_block += "\r\n"

    raw_request = (req_line + hdr_block).encode() + body
    rfile = io.BufferedReader(io.BytesIO(raw_request))

    # ── wfile: captures raw HTTP response bytes ───────────────────────────────
    collector = _ByteCollector()
    wfile     = io.BufferedWriter(collector)

    # ── Instantiate handler without a real socket ─────────────────────────────
    try:
        h = _app.LungInsightHandler.__new__(_app.LungInsightHandler)

        # Attributes expected by BaseHTTPRequestHandler
        h.client_address  = ("127.0.0.1", 0)
        h.server          = type("_S", (), {
            "server_name": "localhost",
            "server_port": 3000,
        })()
        h.rfile           = rfile
        h.wfile           = wfile
        h.close_connection = True
        h.timeout         = None

        # parse_request() needs raw_requestline first
        h.raw_requestline = rfile.readline(65537)
        if not h.parse_request():
            # parse_request already sent 400 to wfile
            wfile.flush()
            raw = collector.getvalue()
            start_response("400 Bad Request", [("Content-Type", "text/plain")])
            return [raw]

        # Dispatch
        dispatch = getattr(h, f"do_{method}", None)
        if dispatch is None:
            start_response("405 Method Not Allowed",
                           [("Content-Type", "text/plain")])
            return [b"Method Not Allowed"]

        dispatch()
        wfile.flush()

    except Exception as exc:
        tb = traceback.format_exc()
        start_response("500 Internal Server Error",
                       [("Content-Type", "text/plain; charset=utf-8")])
        return [f"LungInsight AI — Error\n{exc}\n\n{tb}".encode()]

    # ── Parse raw HTTP response → WSGI status + headers + body ───────────────
    raw_resp = collector.getvalue()
    try:
        sep   = raw_resp.index(b"\r\n\r\n")
        head  = raw_resp[:sep]
        rbody = raw_resp[sep + 4:]
        lines = head.split(b"\r\n")
        sl    = lines[0].decode("utf-8", errors="replace").split(" ", 2)
        code  = sl[1] if len(sl) > 1 else "200"
        rsn   = sl[2] if len(sl) > 2 else "OK"
        hdrs: list[tuple[str, str]] = []
        for line in lines[1:]:
            if b":" in line:
                k, v = line.split(b":", 1)
                hdrs.append((k.decode().strip(), v.decode().strip()))
        start_response(f"{code} {rsn}", hdrs)
        return [rbody]
    except Exception:
        # Fallback: return whatever we collected as plain text
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [raw_resp]
