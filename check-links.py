#!/usr/bin/env python3
"""Check that every relative link and image in the documentation resolves.

Run from the repository root, on any platform:

    python3 check-links.py            # prints "links: clean" or every problem

For every Markdown file it collects the relative links — `[text](path#anchor)`
and `![alt](path)` — resolves the path against the file's own folder, and
checks that the target exists and, for a Markdown target with an anchor, that a
heading producing that anchor exists. Anchors follow the public host's rules:
lower-case, punctuation dropped, each space becomes one hyphen, underscores
kept. Web links are not checked (no network in the gate).

Exit status is the number of problems, so CI can use it as a gate.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", ".venv", "dist", "client"}
LINK = re.compile(r"\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.*)$", re.M)


def slug(heading: str) -> str:
    h = re.sub(r"[`*]", "", heading.strip().lower())
    h = re.sub(r"[^\w\s-]", "", h)
    return h.replace(" ", "-")


def main() -> int:
    root = Path(".").resolve()
    files = [p for p in root.rglob("*.md") if not any(part in SKIP_DIRS for part in p.parts)]
    headings = {p: {slug(m) for m in HEADING.findall(p.read_text(errors="ignore"))} for p in files}
    problems = 0
    for p in files:
        for m in LINK.finditer(p.read_text(errors="ignore")):
            target = m.group(1)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            path, _, anchor = target.partition("#")
            resolved = (p.parent / path).resolve() if path else p
            rel = p.relative_to(root)
            if path and not resolved.exists():
                print(f"MISSING FILE   {rel}: {target}")
                problems += 1
            elif anchor and resolved.suffix == ".md" and resolved.exists() and anchor not in headings.get(resolved, set()):
                print(f"MISSING ANCHOR {rel}: {target}")
                problems += 1
    print("links:", "clean" if problems == 0 else f"{problems} problem(s)")
    return problems


if __name__ == "__main__":
    sys.exit(main())
