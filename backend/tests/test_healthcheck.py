"""Tests for the container healthcheck script (backend/scripts/healthcheck.py).

Regression guard for the proxy-bypass fix: the corporate proxy env vars are
inherited into the container, so the healthcheck must connect to 127.0.0.1
*directly* — otherwise the proxy answers 403 and the container is marked
unhealthy while actually serving fine.
"""

import http.server
import importlib.util
import threading
from pathlib import Path

# Load the standalone script as a module WITHOUT running it. The exit call is
# guarded by `if __name__ == "__main__"`, so importing it has no side effects.
_HC_PATH = Path(__file__).resolve().parent.parent / "scripts" / "healthcheck.py"
_spec = importlib.util.spec_from_file_location("healthcheck", _HC_PATH)
healthcheck = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(healthcheck)


def _serve_200() -> http.server.HTTPServer:
    """Start a throwaway HTTP server on an ephemeral port that returns 200."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):  # keep test output quiet
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_alive_false_for_closed_port():
    """A closed port returns False quickly (no hang, no exception)."""
    assert healthcheck.alive("http://127.0.0.1:9/api/stats") is False


def test_probe_bypasses_proxy(monkeypatch):
    """With a dead proxy configured, the probe must still reach the app.

    If the healthcheck honoured the inherited proxy it would try the dead
    address and return False; because it disables proxying it reaches the
    local 200 server directly and returns True.
    """
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    server = _serve_200()
    try:
        port = server.server_address[1]
        assert healthcheck.alive(f"http://127.0.0.1:{port}/api/stats") is True
    finally:
        server.shutdown()


def test_main_returns_one_when_app_down(monkeypatch):
    """main() returns 1 when neither the HTTP nor HTTPS probe succeeds."""
    monkeypatch.setattr(healthcheck, "alive", lambda *args, **kwargs: False)
    assert healthcheck.main() == 1
