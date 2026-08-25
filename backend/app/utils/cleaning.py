"""Reusable cleaning primitives for messy laboratory spreadsheets.

Real exports are not tidy. The same file can carry Excel formula errors
(`#DIV/0!`), several spellings of "missing" (`NA`, `N/A`, `-`), sentences
where a number belongs ("No compound found above 0.01 mg/kg"), and — when a
file is a concatenation of several exports — copies of its own header row
sitting in the middle of the data.

Everything here is deliberately small and independently testable. A template
description (see `templates.py`) says *which* cleaner applies to *which*
column; this module says what each cleaner actually does.

**Nothing here ever discards information.** A cleaner returns the cleaned
value *and* the original text, so the caller can keep the raw row alongside
the tidy one. `docs/architecture.md` states that the stored document is the
source of truth; cleaning that threw the original away would break that.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

# Values that mean "no data". Compared case-insensitively after stripping.
# `#DIV/0!` and `#VALUE!` are Excel formula errors: the spreadsheet tried to
# compute something (usually a ratio) and could not, so the cell never held a
# real measurement.
NULL_TOKENS = {
    "",
    "-",
    "--",
    "n/a",
    "na",
    "n.a.",
    "nd",
    "n.d.",
    "none",
    "null",
    "nan",
    "#div/0!",
    "#value!",
    "#n/a",
    "#ref!",
    "#name?",
    "#num!",
    "#null!",
}

# Sentences that appear where a number is expected and mean "we looked and
# found nothing above the detection limit" — a real result, not missing data.
_BELOW_LIMIT_RE = re.compile(
    r"\b(no\s+compounds?\s+found|not\s+detected|below\s+(the\s+)?(detection|quantification))\b",
    re.IGNORECASE,
)

# A CAS Registry Number: 2-7 digits, 2 digits, 1 check digit (e.g. 58-08-2).
_CAS_RE = re.compile(r"\b(\d{2,7}-\d{2}-\d)\b")


def collapse_whitespace(value: Any) -> str:
    """Trim, and turn any run of whitespace (including newlines) into one space.

    Spreadsheet cells frequently contain hard line breaks — `Comments / Sources`
    in the Cergy export has them throughout. Collapsing keeps the text readable
    on one line without losing any words.
    """
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def is_null_token(value: Any) -> bool:
    """True when a cell means "no data" rather than carrying one."""
    return collapse_whitespace(value).lower() in NULL_TOKENS


def clean_text(value: Any) -> Optional[str]:
    """Tidy free text; `None` when the cell is empty or a missing-data token."""
    text = collapse_whitespace(value)
    return None if text.lower() in NULL_TOKENS else text


@dataclass(frozen=True)
class Measurement:
    """The result of reading a cell that should contain a number.

    `status` explains *why* `value` is None, which a blank cell alone cannot:

    * ``ok``          — parsed, `value` is the number
    * ``missing``     — blank cell, genuinely no data
    * ``error``       — an Excel formula error such as `#DIV/0!`
    * ``below_limit`` — text saying nothing was found above the detection limit
    * ``text``        — some other text we could not turn into a number
    """

    value: Optional[float]
    raw: str
    status: str

    @property
    def below_limit(self) -> bool:
        return self.status == "below_limit"


def parse_measurement(value: Any) -> Measurement:
    """Read a numeric cell, classifying whatever we find instead of a number.

    Accepts both decimal separators: `0.0026` and `0,0026` both parse to
    0.0026. Thousands separators and stray units (`12 mg`) are stripped, so a
    cell that is *mostly* a number still yields one.
    """
    raw = collapse_whitespace(value)
    lowered = raw.lower()

    if lowered == "":
        return Measurement(None, raw, "missing")
    # Excel error tokens are distinguished from ordinary blanks: the cell was
    # meant to hold a computed value, so this is a failed calculation.
    if lowered.startswith("#") and lowered in NULL_TOKENS:
        return Measurement(None, raw, "error")
    if lowered in NULL_TOKENS:
        return Measurement(None, raw, "missing")
    if _BELOW_LIMIT_RE.search(raw):
        return Measurement(None, raw, "below_limit")

    try:
        return Measurement(float(raw), raw, "ok")
    except ValueError:
        pass

    # Not a bare number. Pull out the first numeric-looking run and try that,
    # which rescues cells like "0.0026 mg" or "< 0,01".
    match = re.search(r"[-+]?\d[\d\s.,]*", raw)
    if match:
        candidate = match.group(0).replace(" ", "")
        # A comma is a decimal separator here (European style) unless the text
        # also has a dot, in which case the comma groups thousands.
        if "," in candidate and "." not in candidate:
            candidate = candidate.replace(",", ".")
        else:
            candidate = candidate.replace(",", "")
        try:
            return Measurement(float(candidate), raw, "ok")
        except ValueError:
            pass

    return Measurement(None, raw, "text")


def parse_date(value: Any, dayfirst: bool = False) -> Optional[str]:
    """Normalise a date to `YYYY-MM-DD`, or `None` if it is not a date.

    `dayfirst` picks between the two ambiguous readings of `01/02/2025`.
    The Cergy export is **month-first** (it contains `12/24/2025`, which can
    only be December 24th), while the SLIMS sample templates are day-first —
    hence the flag rather than a guess.
    """
    text = collapse_whitespace(value)
    if is_null_token(text):
        return None

    orders = ("%d/%m/%Y", "%m/%d/%Y") if dayfirst else ("%m/%d/%Y", "%d/%m/%Y")
    for fmt in (*orders, "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text.split(" ")[0], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_cas_numbers(value: Any) -> list[str]:
    """Every well-formed CAS number in a cell, in order, de-duplicated.

    Returns a list because cells legitimately carry more than one — the Cergy
    export has entries like `5398-11-8\\n\\n6386-38-5` where a peak matched two
    candidate substances. Malformed remnants (`-`, `-00-0`) yield an empty
    list rather than a bad identifier.
    """
    text = collapse_whitespace(value)
    if is_null_token(text):
        return []
    seen: list[str] = []
    for cas in _CAS_RE.findall(text):
        if cas not in seen:
            seen.append(cas)
    return seen


def looks_like_header_echo(row: dict[str, str], headers: list[str]) -> bool:
    """True when a data row is actually a repeated copy of the header row.

    A file assembled by appending several exports carries each export's header
    into the middle of the data. Those rows parse perfectly and are pure
    noise, so they must be dropped rather than cleaned.

    The test is deliberately loose: a repeated header often has extra
    explanatory text appended (one Cergy row reads "mg/6dm2 material (in EU
    Regulation the results ...)"), so a cell counts as an echo when it
    *starts with* its own column name.

    Echoes are frequently **partial**. In the Cergy export the repeated rows
    keep real values in the sample-context columns (LIMS, date, factory) and
    echo only the seven result columns — `Name` = "Name", `CAS` = "CAS" and so
    on. A majority-of-columns rule misses those, so the primary test is a
    count: three independent columns naming themselves does not happen by
    accident in real data.
    """
    matches = 0
    filled = 0
    for header in headers:
        cell = collapse_whitespace(row.get(header, ""))
        if not cell:
            continue
        filled += 1
        name = collapse_whitespace(header)
        if cell.lower().startswith(name.lower()) or name.lower().startswith(cell.lower()):
            matches += 1
    if filled == 0:
        return False
    # Three self-naming columns is decisive on its own. The majority clause
    # keeps narrow files covered, where a header echo may fill only two cells.
    return matches >= 3 or (matches >= 2 and matches >= filled / 2)


def stable_hash(*parts: Any) -> str:
    """A short, deterministic id built from the given parts.

    Used to key records that have no natural identifier — the same inputs
    always produce the same id, so re-importing a file does not invent new
    ones.
    """
    joined = "␟".join(collapse_whitespace(p).lower() for p in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]
