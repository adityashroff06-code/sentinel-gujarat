"""Account administration — ``/api/users``, admin only (docs/api.md §7, §9;
task S3.0). Passwords are accepted on create/update, hashed immediately
(backend/core/passwords.py) and never returned, logged or audited."""

from __future__ import annotations

import sqlite3
from typing import Iterator, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.audit import set_audit
from backend.app.auth import require_admin
from backend.core import db as dbmod
from backend.core import passwords

router = APIRouter(prefix="/api/users", tags=["users"])

USERNAME_PATTERN = r"^[A-Za-z0-9_.-]{3,32}$"


def get_db() -> Iterator[sqlite3.Connection]:
    con = dbmod.connect()
    try:
        yield con
    finally:
        con.close()


class UserIn(BaseModel):
    username: str = Field(pattern=USERNAME_PATTERN)
    password: str = Field(min_length=8, max_length=1024)
    role: Literal["viewer", "evaluator", "admin"]


class UserPatch(BaseModel):
    password: str | None = Field(default=None, min_length=8, max_length=1024)
    role: Literal["viewer", "evaluator", "admin"] | None = None
    active: bool | None = None


class UserOut(BaseModel):
    user_id: int
    username: str
    role: str
    active: bool
    created_at: str
    last_login: str | None = None


class UserMessageOut(BaseModel):
    detail: str


def _row_out(row: sqlite3.Row) -> dict:
    """The response/audit shape — password_hash never leaves the table."""
    return {
        "user_id": row["user_id"],
        "username": row["username"],
        "role": row["role"],
        "active": bool(row["active"]),
        "created_at": row["created_at"],
        "last_login": row["last_login"],
    }


def _fetch(con: sqlite3.Connection, user_id: int) -> sqlite3.Row:
    row = con.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="user not found")
    return row


def _revoke_sessions(con: sqlite3.Connection, user_id: int) -> None:
    con.execute(
        "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
        (dbmod.utcnow(), user_id),
    )


@router.get("", response_model=list[UserOut])
def list_users(
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_admin),
):
    """List accounts (names, roles, status — never password material)."""
    return [_row_out(r) for r in con.execute("SELECT * FROM users ORDER BY username")]


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    request: Request,
    body: UserIn,
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_admin),
):
    """Create an account; 409 on a duplicate username."""
    try:
        con.execute(
            "INSERT INTO users (username, password_hash, role, active, created_at)"
            " VALUES (?, ?, ?, 1, ?)",
            (body.username, passwords.hash_password(body.password), body.role, dbmod.utcnow()),
        )
        con.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"user '{body.username}' already exists")
    row = con.execute("SELECT * FROM users WHERE username = ?", (body.username,)).fetchone()
    out = _row_out(row)
    set_audit(request, entity="users", entity_id=body.username, after=out)
    return out


@router.patch("/{user_id}", response_model=UserOut)
def patch_user(
    request: Request,
    user_id: int,
    patch: UserPatch,
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_admin),
):
    """Change role, active flag or password. Disabling an account or
    changing its password revokes its open sessions."""
    before_row = _fetch(con, user_id)
    before = _row_out(before_row)
    changes = patch.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="no fields to change")
    sets, values = [], []
    if "role" in changes and changes["role"] is not None:
        sets.append("role = ?"); values.append(changes["role"])
    if "active" in changes and changes["active"] is not None:
        sets.append("active = ?"); values.append(1 if changes["active"] else 0)
    if changes.get("password"):
        sets.append("password_hash = ?")
        values.append(passwords.hash_password(changes["password"]))
    if sets:
        con.execute(f"UPDATE users SET {', '.join(sets)} WHERE user_id = ?", [*values, user_id])
    if changes.get("password") or changes.get("active") is False:
        _revoke_sessions(con, user_id)
    con.commit()
    after = _row_out(_fetch(con, user_id))
    set_audit(request, entity="users", entity_id=before["username"], before=before, after=after)
    return after


@router.delete("/{user_id}", response_model=UserMessageOut)
def delete_user(
    request: Request,
    user_id: int,
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_admin),
):
    """Delete an account and its sessions."""
    before = _row_out(_fetch(con, user_id))
    con.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    con.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    con.commit()
    set_audit(request, entity="users", entity_id=before["username"], before=before)
    return {"detail": f"user '{before['username']}' deleted"}
