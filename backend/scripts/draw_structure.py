#!/usr/bin/env python3
"""Draw one entry's derived structure as an SVG file, from the terminal (phase CR-12, step B).

The same picture the browser shows and `GET /api/chemicals/{id}/structure.svg`
answers: all three call `app.depict`. The entry needs a derived structure
first (`derive_structures.py --apply`, or the attention page's button).

    .venv/bin/python scripts/draw_structure.py CHEM-000001                    # the SVG on standard output
    .venv/bin/python scripts/draw_structure.py CHEM-000001 -o caffeine.svg    # written to a file
    .venv/bin/python scripts/draw_structure.py CHEM-000001 --width 640 --height 480 -o big.svg

On the server, through the shortcut: ./container-py.sh script draw_structure.py CHEM-000001 -o /app/data/caffeine.svg
(the data folder is the one the container shares with the host: the file lands in data/).
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("AUTO_INIT_DB", "false")

from app.database import SessionLocal  # noqa: E402
from app.depict import DEFAULT_HEIGHT, DEFAULT_WIDTH, DepictUnavailable, svg_for  # noqa: E402
from app.models import Chemical  # noqa: E402
from app.store import find_row  # noqa: E402


def main(argv: list[str] | None = None, db=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("chemical_id", help="the entry, CHEM-000001")
    parser.add_argument("-o", "--out", help="write the SVG here (standard output otherwise)")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    args = parser.parse_args(argv)

    own = db is None
    db = db or SessionLocal()
    try:
        row = find_row(db, Chemical, "chemical_id", args.chemical_id)
        if row is None:
            print(f"No entry {args.chemical_id}.", file=sys.stderr)
            return 1
        doc = row.doc or {}
        try:
            svg = svg_for(doc, args.width, args.height)
        except DepictUnavailable as err:
            print(f"Cannot draw: {err}", file=sys.stderr)
            return 2
    finally:
        if own:
            db.close()
    if svg is None:
        print(f"{args.chemical_id} has no derived structure to draw: run derive_structures.py --apply first"
              " (or Derive structures on the attention page).", file=sys.stderr)
        return 1
    if args.out:
        Path(args.out).write_text(svg)
        print(f"{args.chemical_id}: {len(svg):,} bytes of SVG written to {args.out}")
    else:
        sys.stdout.write(svg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
