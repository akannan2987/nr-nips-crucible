#!/usr/bin/env python3
"""The accounts of the local login, from the terminal (phase SH-3b; docs/13-authentication.md).

Runs inside the container, against the database directly, so it works
whatever AUTH_MODE says: the first administrator is created with it while
the login is still off or on the token rung, and a locked-out operator can
always let themselves back in. It calls the same module as the login route
(`app.accounts`), so the browser, the API and this script cannot disagree.

    ./container-py.sh users add alice --role editor --name "Alice Smith"   # a temporary password, shown once
    ./container-py.sh users add bob --role viewer --prompt                  # asks for the password, twice, hidden
    echo 'a long passphrase' | ./container-py.sh users add carol --password-stdin
    ./container-py.sh users list                                            # who exists, with role, state, token
    ./container-py.sh users reset alice                                     # a new temporary password; her browsers signed out
    ./container-py.sh users role alice admin
    ./container-py.sh users disable bob                                     # a leaver: refused everywhere, at once
    ./container-py.sh users enable bob
    ./container-py.sh users unlock alice                                    # after ten wrong passwords
    ./container-py.sh users token alice                                     # a personal token for scripts, shown once
    ./container-py.sh users token alice --revoke
    ./container-py.sh users remove bob                                      # the account itself; disable is usually enough

(`./container-py.sh users …` is `podman exec -i <container> python /app/backend/scripts/manage_users.py …`.)

Passwords and tokens are printed once, when made, and never again: what
is stored is a hash. Hand them over out of band: in person, or through the
organisation's password manager, never in an e-mail body or a chat.
"""

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("AUTO_INIT_DB", "false")

from sqlalchemy.orm import Session  # noqa: E402

from app import accounts  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.store import delete_row  # noqa: E402


def _password_from(args: argparse.Namespace) -> tuple[str, bool]:
    """The password to set, and whether it was generated (so it must be shown once)."""
    if getattr(args, "password_stdin", False):
        return sys.stdin.readline().rstrip("\n"), False
    if getattr(args, "prompt", False):
        first = getpass.getpass("Password: ")
        second = getpass.getpass("Again: ")
        if first != second:
            raise ValueError("the two passwords differ")
        return first, False
    return accounts.generate_password(), True


def _print_user(user: dict) -> None:
    state = "enabled" if user["enabled"] else "DISABLED"
    if user["locked"]:
        state += ", LOCKED"
    token = f"token issued {user['token_issued_at'][:19]}" if user["has_token"] else "no token"
    last = user["last_login"][:19] if user["last_login"] else "never"
    print(f"  {user['username']:<20} {user['role']:<7} {state:<18} {token:<28} last login {last}   {user['display_name']}")


def cmd_add(db: Session, args: argparse.Namespace) -> int:
    password, generated = _password_from(args)
    user = accounts.add_user(db, args.username, password, role=args.role, display_name=args.name or "")
    print(f"✓ Added {user['username']} ({user['role']}), enabled")
    if generated:
        print(f"  temporary password: {password}")
        print("  Shown once. Hand it over out of band; the person changes it in the page (Change password).")
    return 0


def cmd_reset(db: Session, args: argparse.Namespace) -> int:
    password, generated = _password_from(args)
    user = accounts.set_password(db, args.username, password)
    print(f"✓ Password reset for {user['username']}; every browser signed in as them is signed out")
    if generated:
        print(f"  temporary password: {password}")
        print("  Shown once. Hand it over out of band; the person changes it in the page (Change password).")
    return 0


def cmd_enable(db: Session, args: argparse.Namespace) -> int:
    user = accounts.set_enabled(db, args.username, True)
    print(f"✓ {user['username']} enabled")
    return 0


def cmd_disable(db: Session, args: argparse.Namespace) -> int:
    user = accounts.set_enabled(db, args.username, False)
    print(f"✓ {user['username']} disabled: refused at the login page, by cookie and by token, from now")
    return 0


def cmd_unlock(db: Session, args: argparse.Namespace) -> int:
    user = accounts.unlock(db, args.username)
    print(f"✓ {user['username']} unlocked (failed attempts cleared)")
    return 0


def cmd_role(db: Session, args: argparse.Namespace) -> int:
    user = accounts.set_role(db, args.username, args.role)
    print(f"✓ {user['username']} is now {user['role']}")
    return 0


def cmd_token(db: Session, args: argparse.Namespace) -> int:
    if args.revoke:
        user = accounts.revoke_token(db, args.username)
        print(f"✓ Token revoked for {user['username']}: a script presenting it is refused from now")
        return 0
    token = accounts.issue_token(db, args.username)
    print(f"✓ Personal token for {args.username} (any older one is void):")
    print(f"  {token}")
    print('  Shown once. Scripts send it as:  -H "Authorization: Bearer <the token>"')
    return 0


def cmd_remove(db: Session, args: argparse.Namespace) -> int:
    row = accounts.get_user(db, args.username)
    if row is None:
        raise ValueError(f"no user named {args.username!r}")
    if not args.apply:
        print(f"Would remove the account {row.doc['username']} ({row.doc.get('role')}). Add --apply to do it;")
        print("  'disable' keeps the account and its history and is usually the better choice.")
        return 0
    delete_row(db, row)
    print(f"✓ Removed {args.username}")
    return 0


def cmd_list(db: Session, args: argparse.Namespace) -> int:
    users = accounts.list_users(db)
    if args.json:
        print(json.dumps(users, indent=2))
        return 0
    if not users:
        print("No accounts yet. Add the first administrator:  ./container-py.sh users add <name> --role admin")
        return 0
    print(f"{len(users)} account{'s' if len(users) != 1 else ''}:")
    for user in users:
        _print_user(user)
    print("\nRoles: viewer reads, exports and queries; editor also uploads, links and edits; admin also deletes, merges and clears.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def with_password(p: argparse.ArgumentParser) -> None:
        g = p.add_mutually_exclusive_group()
        g.add_argument("--prompt", action="store_true", help="ask for the password, hidden, twice")
        g.add_argument("--password-stdin", action="store_true", help="read the password from the first line of stdin")

    p = sub.add_parser("add", help="create an account (a temporary password is generated unless --prompt or --password-stdin)")
    p.add_argument("username")
    p.add_argument("--role", choices=accounts.ROLES, default="viewer")
    p.add_argument("--name", default="", help="the display name the page shows (default: the username)")
    with_password(p)
    p.set_defaults(fn=cmd_add)

    p = sub.add_parser("reset", help="a new password (generated unless --prompt or --password-stdin); signs the person out everywhere")
    p.add_argument("username")
    with_password(p)
    p.set_defaults(fn=cmd_reset)

    for name, fn, help_ in (("enable", cmd_enable, "let the account in again"),
                            ("disable", cmd_disable, "refuse the account everywhere, at once (a leaver)"),
                            ("unlock", cmd_unlock, "clear the lockout after too many wrong passwords")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("username")
        p.set_defaults(fn=fn)

    p = sub.add_parser("role", help="change the role")
    p.add_argument("username")
    p.add_argument("role", choices=accounts.ROLES)
    p.set_defaults(fn=cmd_role)

    p = sub.add_parser("token", help="issue a personal token for scripts (shown once), or --revoke it")
    p.add_argument("username")
    p.add_argument("--revoke", action="store_true")
    p.set_defaults(fn=cmd_token)

    p = sub.add_parser("remove", help="delete the account itself (report only without --apply)")
    p.add_argument("username")
    p.add_argument("--apply", action="store_true")
    p.set_defaults(fn=cmd_remove)

    p = sub.add_parser("list", help="every account: role, state, token, last login (never a hash)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_list)
    return parser


def main(argv: list[str] | None = None, db: Session | None = None) -> int:
    args = build_parser().parse_args(argv)
    own = db is None
    db = db or SessionLocal()
    try:
        return args.fn(db, args)
    except ValueError as err:
        print(f"✗ {err}", file=sys.stderr)
        return 1
    finally:
        if own:
            db.close()


if __name__ == "__main__":
    # A database without the table yet (an image older than v2.23.0 was never
    # migrated) fails with a plain message rather than a stack trace.
    from sqlalchemy import inspect

    from app.database import engine

    if User.__tablename__ not in inspect(engine).get_table_names():
        print("✗ There is no users table: the database has not been migrated to v2.23.0 (restart the container, or run scripts/db_bootstrap.py)", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(main())
