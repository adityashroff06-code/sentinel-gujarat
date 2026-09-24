-- Schema v2 — docs/api.md §9 (decisions F41, F42; task S3.0): login, roles,
-- sessions and the restart-surviving login throttle.
-- users/sessions are verbatim from docs/api.md §9; login_attempts backs the
-- 5-failure / 15-minute lock (in the database, so a restart keeps it).

CREATE TABLE users (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,          -- hashlib.scrypt(n=2**14, r=8, p=1), per-user salt, stored as
                                          -- scrypt$<n>$<r>$<p>$<salt_b64>$<hash_b64> — never a plain hash
    role          TEXT NOT NULL,          -- viewer | evaluator | admin
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL,
    last_login    TEXT
);

CREATE TABLE sessions (
    session_id    TEXT PRIMARY KEY,       -- secrets.token_urlsafe(32); the cookie value, never a JWT
    user_id       INTEGER NOT NULL REFERENCES users(user_id),
    issued_at     TEXT NOT NULL,
    expires_at    TEXT NOT NULL,          -- issued_at + SENTINEL_SESSION_TTL_H (default 8 h)
    revoked_at    TEXT,
    user_agent    TEXT                    -- truncated, for the audit trail only
);
CREATE INDEX idx_sessions_user ON sessions(user_id, expires_at);

CREATE TABLE login_attempts (
    key          TEXT PRIMARY KEY,        -- 'user:<username>' or 'ip:<address>'
    failures     INTEGER,
    locked_until TEXT
);
