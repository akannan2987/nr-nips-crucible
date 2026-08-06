"""Container healthcheck — probes /api/stats over HTTP, then HTTPS.

Used by the Dockerfile HEALTHCHECK. Targets 127.0.0.1 on purpose:
in-container `localhost` resolves to ::1 while uvicorn binds IPv4.

Two loopback gotchas this script handles explicitly:
  * Proxy — the corporate `http_proxy`/`https_proxy` env vars are inherited
    into the container and their `no_proxy` does NOT list 127.0.0.1, so a
    plain urllib call would send the probe to the proxy (which answers 403).
    We build an opener with an empty `ProxyHandler` so the probe always
    connects directly — the same reason every curl in this repo uses
    `--noproxy '*'`.
  * TLS — in HTTPS mode uvicorn serves TLS on the port, so the HTTP probe is
    expected to fail and the HTTPS probe is the one that succeeds; it skips
    certificate verification (a self-signed cert is fine for a loopback
    liveness check).
"""

import os
import ssl
import sys
import urllib.request

PORT = os.environ.get("PORT", "49160")


def alive(url: str, ctx: ssl.SSLContext | None = None) -> bool:
    """True when `url` answers HTTP 200 within the timeout.

    Always connects directly: `ProxyHandler({})` disables proxying for this
    opener, so the loopback probe is never routed through the inherited
    corporate proxy.
    """
    handlers: list = [urllib.request.ProxyHandler({})]
    if ctx is not None:
        handlers.append(urllib.request.HTTPSHandler(context=ctx))
    opener = urllib.request.build_opener(*handlers)
    try:
        return opener.open(url, timeout=8).status == 200
    except Exception:
        return False


def main() -> int:
    """Exit 0 if the app answers on HTTP or HTTPS, else 1."""
    if alive(f"http://127.0.0.1:{PORT}/api/stats") or alive(
        f"https://127.0.0.1:{PORT}/api/stats", ssl._create_unverified_context()
    ):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
