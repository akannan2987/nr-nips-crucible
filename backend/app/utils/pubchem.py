"""Look up chemical metadata in PubChem.

Screening exports name a compound and, less than half the time, give a CAS
number. PubChem can fill in the rest — formula, molecular weight, canonical
SMILES, InChIKey, IUPAC name — which turns a bare name into a usable registry
entry.

Two things this module is careful about:

**It tries the name as well as the CAS number.** A CAS-only lookup misses a
large share of real laboratory entries, because what was measured is often a
salt, a hydrate or a complex whose CAS differs from the parent compound's — and
because more than half of these rows carry no CAS at all. Names are tried both
as given and lightly normalised.

**It is polite to the service.** PubChem asks for no more than five requests a
second; `min_interval` enforces that, results are cached in-process so a
compound seen 300 times is fetched once, and any failure returns `None` rather
than raising — enrichment must never be able to fail an import.

Note that using this sends compound names and CAS numbers to an external
service (the US National Library of Medicine). That is a deliberate choice to
be aware of, not an accident.
"""

from __future__ import annotations

import json
import os
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

# Where a Linux host usually keeps its trusted roots, corporate ones included.
_LINUX_BUNDLES = (
    "/etc/pki/tls/certs/ca-bundle.crt",  # RHEL / CentOS / Fedora
    "/etc/ssl/certs/ca-certificates.crt",  # Debian / Ubuntu
)


def build_ssl_context(ca_bundle: Optional[str] = None) -> ssl.SSLContext:
    """An SSL context that trusts the roots this machine trusts.

    On a corporate network an inspecting proxy re-signs HTTPS traffic with an
    internal root. `curl` accepts it because it reads the operating system's
    trust store; Python does not, and fails with
    `CERTIFICATE_VERIFY_FAILED: self-signed certificate in certificate chain`.

    Resolution order:

    1. the `ca_bundle` argument,
    2. `CRUCIBLE_CA_BUNDLE`, then the conventional `SSL_CERT_FILE`,
    3. the platform's own bundle — the standard file on Linux, or the login
       keychain roots exported once and cached on macOS,
    4. Python's defaults, which is right on a machine with no proxy.
    """
    explicit = ca_bundle or os.environ.get("CRUCIBLE_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    if explicit and Path(explicit).is_file():
        return ssl.create_default_context(cafile=explicit)

    discovered = _platform_ca_bundle()
    if discovered:
        return ssl.create_default_context(cafile=discovered)

    return ssl.create_default_context()


def _platform_ca_bundle() -> Optional[str]:
    """The operating system's trust store as a PEM file, if we can find one."""
    for path in _LINUX_BUNDLES:
        if Path(path).is_file():
            return path

    if sys.platform != "darwin":
        return None

    # macOS keeps its roots in keychains rather than a PEM file, so export them
    # once and reuse the result. `security` is part of the base system.
    cache = Path(tempfile.gettempdir()) / "crucible-macos-roots.pem"
    if cache.is_file() and cache.stat().st_size > 0:
        return str(cache)

    keychains = (
        "/System/Library/Keychains/SystemRootCertificates.keychain",
        "/Library/Keychains/System.keychain",
    )
    pem_parts: list[str] = []
    for keychain in keychains:
        try:
            result = subprocess.run(
                ["security", "find-certificate", "-a", "-p", keychain],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode == 0 and result.stdout:
                pem_parts.append(result.stdout)
        except (OSError, subprocess.SubprocessError):
            continue

    if not pem_parts:
        return None
    try:
        cache.write_text("\n".join(pem_parts))
        return str(cache)
    except OSError:
        return None

# The properties worth having on a registry entry. PubChem returns them in one
# request, so asking for all of them costs no more than asking for one.
PROPERTIES = (
    "MolecularFormula",
    "MolecularWeight",
    "CanonicalSMILES",
    "InChI",
    "InChIKey",
    "IUPACName",
    "Title",
)


@dataclass
class PubChemResult:
    """What PubChem knew, and how we found it."""

    cid: int
    matched_by: str  # "cas" | "name" | "normalised name"
    properties: dict[str, Any]

    def as_chemical_fields(self) -> dict[str, Any]:
        """Map onto the field names this application already uses."""
        props = self.properties
        weight = props.get("MolecularWeight")
        try:
            weight = float(weight) if weight is not None else None
        except (TypeError, ValueError):
            weight = None
        return {
            "pubchem_cid": self.cid,
            "pubchem_matched_by": self.matched_by,
            "molecular_formula": props.get("MolecularFormula"),
            "molecular_weight": weight,
            "smiles": props.get("CanonicalSMILES"),
            "inchi": props.get("InChI"),
            "inchi_key": props.get("InChIKey"),
            "iupac_name": props.get("IUPACName"),
            "pubchem_title": props.get("Title"),
        }


class PubChemClient:
    """A small, rate-limited PubChem client with an in-process cache."""

    def __init__(
        self,
        min_interval: float = 0.22,
        timeout: float = 10.0,
        ca_bundle: Optional[str] = None,
    ):
        # 0.22s ≈ 4.5 requests/second, just inside PubChem's stated limit.
        self.min_interval = min_interval
        self.timeout = timeout
        self._context = build_ssl_context(ca_bundle)
        self._last_call = 0.0
        self._cache: dict[str, Optional[PubChemResult]] = {}
        self.requests_made = 0
        self.failures = 0
        self.throttled = 0
        self.last_error: Optional[str] = None

    # -- transport --------------------------------------------------------

    def _get(self, url: str, attempts: int = 3) -> Optional[dict[str, Any]]:
        """One GET, rate-limited and retried. Returns parsed JSON, or None.

        A 404 simply means "PubChem does not know this", which is an ordinary
        outcome here rather than an error worth raising, so it returns
        immediately without retrying.

        Everything else is retried with a growing pause and then gives up
        quietly. Network faults over a long run are certain rather than
        unlikely — a connection dropped mid-response raises `IncompleteRead`,
        for instance — and a single blip must never end a job that has been
        running for half an hour. The exception net is deliberately wide for
        the same reason: a lookup failing is always preferable to the process
        dying.
        """
        for attempt in range(attempts):
            wait = self.min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
            self.requests_made += 1
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "Crucible/2.0"})
                with urllib.request.urlopen(
                    request, timeout=self.timeout, context=self._context
                ) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as err:
                if err.code == 404:
                    return None
                self.last_error = f"HTTP {err.code}"
                if err.code in (429, 503):
                    # PubChem throttles rather than queues: 503 means "you are
                    # asking too fast", and retrying a second later simply
                    # earns another 503. Back off hard, honouring Retry-After
                    # when the server sends one, and slow every subsequent
                    # request so the run recovers instead of burning its
                    # retries. Without this a throttled run reports compounds
                    # as "not in PubChem" when the truth is it never asked.
                    delay = 5.0 * (attempt + 1)
                    header = err.headers.get("Retry-After") if err.headers else None
                    if header:
                        try:
                            delay = max(delay, float(header))
                        except ValueError:
                            pass
                    self.throttled += 1
                    self.min_interval = min(self.min_interval * 1.5, 2.0)
                    time.sleep(delay)
                    continue
            except Exception as err:  # noqa: BLE001 - see the docstring
                self.last_error = f"{type(err).__name__}: {err}"
            if attempt < attempts - 1:
                time.sleep(1.0 * (attempt + 1))
        self.failures += 1
        return None

    def _properties_for_cid(self, cid: int) -> Optional[dict[str, Any]]:
        url = f"{BASE}/compound/cid/{cid}/property/{','.join(PROPERTIES)}/JSON"
        payload = self._get(url)
        try:
            return payload["PropertyTable"]["Properties"][0]
        except (TypeError, KeyError, IndexError):
            return None

    def _cids_for(self, kind: str, value: str) -> list[int]:
        """CIDs matching a name or registry number. `kind` is `name` or `xref/rn`."""
        url = f"{BASE}/compound/{kind}/{urllib.parse.quote(value, safe='')}/cids/JSON"
        payload = self._get(url)
        try:
            return payload["IdentifierList"]["CID"]
        except (TypeError, KeyError):
            return []

    # -- lookup -----------------------------------------------------------

    def lookup(
        self, name: Optional[str], cas: Optional[str], cid_only: bool = False
    ) -> Optional[PubChemResult]:
        """Find a compound by CAS then by name; `None` if nothing matches.

        CAS is tried first because it is unambiguous when present. The name
        follows, which is what rescues the majority of rows here: over half
        carry no CAS, and salts and complexes frequently carry one that PubChem
        files under a different substance.

        `cid_only` skips the second request that fetches the compound's
        properties. A caller that just needs to know *which* compound a name
        resolves to — to check it against a CAS number, say — was otherwise
        paying for a full property fetch and discarding it, which is one
        request in four wasted across a run.
        """
        cache_key = f"{(cas or '').strip()}|{(name or '').strip().lower()}|{cid_only}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        result: Optional[PubChemResult] = None
        for kind, value, label in self._attempts(name, cas):
            cids = self._cids_for(kind, value)
            if not cids:
                continue
            if cid_only:
                result = PubChemResult(cid=cids[0], matched_by=label, properties={})
                break
            props = self._properties_for_cid(cids[0])
            if props:
                result = PubChemResult(cid=cids[0], matched_by=label, properties=props)
                break

        self._cache[cache_key] = result
        return result

    @staticmethod
    def _attempts(name: Optional[str], cas: Optional[str]) -> list[tuple[str, str, str]]:
        """The lookups to try, in order of how much we trust them."""
        attempts: list[tuple[str, str, str]] = []
        if cas:
            attempts.append(("xref/rn", cas, "cas"))
        if name:
            attempts.append(("name", name, "name"))
            simplified = _simplify_name(name)
            if simplified and simplified.lower() != name.lower():
                attempts.append(("name", simplified, "normalised name"))
        return attempts


def _simplify_name(name: str) -> str:
    """Strip the decoration laboratory names accumulate.

    Removes trailing parenthetical qualifiers and common suffixes — "Benzoic
    acid (tentative)" becomes "Benzoic acid" — giving a second chance at a
    match when the decorated form finds nothing. Deliberately conservative: it
    never alters the chemistry, only the annotation around it.
    """
    cleaned = name.strip()
    # Drop bracketed qualifiers: "(tentative)", "[isomer 2]"
    for opener, closer in (("(", ")"), ("[", "]")):
        while opener in cleaned and closer in cleaned[cleaned.index(opener) :]:
            start = cleaned.index(opener)
            end = cleaned.index(closer, start) + 1
            cleaned = (cleaned[:start] + cleaned[end:]).strip()
    for suffix in (" isomer", " tentative", " probable", " possible", " unknown"):
        if cleaned.lower().endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
    return " ".join(cleaned.split())
