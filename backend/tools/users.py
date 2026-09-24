"""Account administration CLI (docs/api.md §9; task S3.0).

    python -m backend.tools.users add <username> --role viewer|evaluator|admin
    python -m backend.tools.users passwd <username>
    python -m backend.tools.users disable <username>
    python -m backend.tools.users list

``add`` and ``passwd`` prompt for the password (``getpass``, read from
stdin) — the password is NEVER taken on the command line, never echoed and
never printed. ``list`` shows names, roles and status only.
"""

from __future__ import annotations

import argparse
import getpass
import sqlite3
import sys

from backend.core import db as dbmod
from backend.core import passwords

ROLES = ("viewer", "evaluator", "admin")
MIN_PASSWORD_LEN = 8


def prompt_password() -> str:
    """Prompt twice for a new password; exits with status 2 on mismatch or
    a too-short password. Never echoes, never appears in argv."""
    first = getpass.getpass("Password: ")
    second = getpass.getpass("Repeat password: ")
    if first != second:
        print("passwords do not match", file=sys.stderr)
        raise SystemExit(2)
    if len(first) < MIN_PASSWORD_LEN:
        print(f"password must be at least {MIN_PASSWORD_LEN} characters", file=sys.stderr)
        raise SystemExit(2)
    return first


def add(con: sqlite3.Connection, username: str, role: str) -> int:
    """Create *username* with *role*; prompts for the password."""
    password_hash = passwords.hash_password(prompt_password())
    try:
        con.execute(
            "INSERT INTO users (username, password_hash, role, active, created_at)"
            " VALUES (?, ?, ?, 1, ?)",
            (username, password_hash, role, dbmod.utcnow()),
        )
        con.commit()
    except sqlite3.IntegrityError:
        print(f"user '{username}' already exists", file=sys.stderr)
        return 1
    print(f"added {username} ({role})")
    return 0


def _user_id(con: sqlite3.Connection, username: str) -> int | None:
    row = con.execute("SELECT user_id FROM users WHERE username = ?", (username,)).fetchone()
    return None if row is None else int(row["user_id"])


def passwd(con: sqlite3.Connection, username: str) -> int:
    """Set a new password for *username* and revoke their open sessions."""
    uid = _user_id(con, username)
    if uid is None:
        print(f"no such user: {username}", file=sys.stderr)
        return 1
    password_hash = passwords.hash_password(prompt_password())
    con.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (password_hash, uid))
    con.execute(
        "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
        (dbmod.utcnow(), uid),
    )
    con.commit()
    print(f"password updated for {username}; open sessions revoked")
    return 0


def disable(con: sqlite3.Connection, username: str) -> int:
    """Deactivate *username* and revoke their open sessions."""
    uid = _user_id(con, username)
    if uid is None:
        print(f"no such user: {username}", file=sys.stderr)
        return 1
    con.execute("UPDATE users SET active = 0 WHERE user_id = ?", (uid,))
    con.execute(
        "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
        (dbmod.utcnow(), uid),
    )
    con.commit()
    print(f"disabled {username}; open sessions revoked")
    return 0


def list_users(con: sqlite3.Connection) -> int:
    """Print names, roles and status — never password material."""
    rows = con.execute(
        "SELECT username, role, active, created_at, last_login FROM users ORDER BY username"
    ).fetchall()
    if not rows:
        print("no users (create one with: python -m backend.tools.users add <username> --role admin)")
        return 0
    for r in rows:
        status = "active" if r["active"] else "disabled"
        print(f"{r['username']:<24} {r['role']:<10} {status:<9} last_login={r['last_login'] or '-'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns the process exit status."""
    parser = argparse.ArgumentParser(
        prog="python -m backend.tools.users",
        description="Sentinel account administration (passwords are prompted, never argv).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_add = sub.add_parser("add", help="create an account (prompts for the password)")
    p_add.add_argument("username")
    p_add.add_argument("--role", choices=ROLES, required=True)
    p_passwd = sub.add_parser("passwd", help="change a password (prompts)")
    p_passwd.add_argument("username")
    p_disable = sub.add_parser("disable", help="deactivate an account")
    p_disable.add_argument("username")
    sub.add_parser("list", help="names, roles and status only")
    args = parser.parse_args(argv)

    con = dbmod.connect()
    try:
        dbmod.migrate(con)
        if args.command == "add":
            return add(con, args.username, args.role)
        if args.command == "passwd":
            return passwd(con, args.username)
        if args.command == "disable":
            return disable(con, args.username)
        return list_users(con)
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
