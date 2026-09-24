"""Password hashing (docs/api.md §9; task S3.0).

``hashlib.scrypt`` with n=2**14, r=8, p=1 and a fresh per-user salt.
Stored form: ``scrypt$<n>$<r>$<p>$<salt_b64>$<hash_b64>`` — the parameters
travel with the hash so they can be raised later without breaking existing
rows. Verification recomputes with the stored parameters and compares in
constant time (``hmac.compare_digest``). Passwords are never stored, logged
or returned anywhere else (root CLAUDE.md rule 11).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

_N = 2**14
_R = 8
_P = 1
_SALT_BYTES = 16
_DKLEN = 64
# 128 * r * n = 16 MiB for the parameters above; leave headroom.
_MAXMEM = 64 * 1024 * 1024
# Upper bounds when verifying a stored row — a corrupted/hostile row must
# not be able to ask this process for gigabytes of scrypt memory.
_MAX_N = 2**16
_MAX_R = 32
_MAX_P = 4


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def hash_password(password: str) -> str:
    """Hash *password* for storage.

    Returns the ``scrypt$n$r$p$salt_b64$hash_b64`` string. Raises
    ``ValueError`` for an empty password.
    """
    if not password:
        raise ValueError("password must not be empty")
    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P,
        maxmem=_MAXMEM, dklen=_DKLEN,
    )
    return "$".join(("scrypt", str(_N), str(_R), str(_P), _b64(salt), _b64(dk)))


def verify_password(password: str, stored: str) -> bool:
    """Check *password* against a *stored* ``scrypt$...`` string.

    Returns True on a match; False for a mismatch or any malformed/
    out-of-bounds stored value (never raises on bad input).
    """
    try:
        scheme, n_s, r_s, p_s, salt_b64, hash_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        n, r, p = int(n_s), int(r_s), int(p_s)
        if not (0 < n <= _MAX_N and 0 < r <= _MAX_R and 0 < p <= _MAX_P):
            return False
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(hash_b64, validate=True)
        if not salt or not expected:
            return False
        dk = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=n, r=r, p=p,
            maxmem=_MAXMEM, dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk, expected)
