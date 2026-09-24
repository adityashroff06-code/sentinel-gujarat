"""CDN session (docs/sandbox-findings.md §1) — shared by the probe, the
HLS relay (S3.1b) and the harvest (S4.2).

Form login to ``/auth/login`` (fields ``email``, ``password``), cookie jar,
browser-like User-Agent (the CDN 403s non-browser agents), jittered
exponential backoff with **one** re-login on 403/timeout. The CDN
rate-limits hard: callers keep requests gentle; this class never hammers.
Every log line is masked (root rule 1).
"""

from __future__ import annotations

import random
import time

import httpx

from backend.core import config, logging_setup

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)


class CdnError(RuntimeError):
    """The CDN refused us after retries (rate limit, auth, or outage)."""


def backoff_delay(attempt: int) -> tuple[float, float]:
    """``(base, delay)`` for *attempt* (0-based): base = min(2·2ⁿ, 30),
    delay = base · random(0.5, 1.5) — root rule 7 / decision F36."""
    base = min(2 * (2 ** attempt), 30)
    return base, base * random.uniform(0.5, 1.5)


class CdnSession:
    """A logged-in CDN client. ``get()`` retries with backoff and re-logs
    in once on a 403 before giving up."""

    def __init__(self, timeout_s: float = 15.0) -> None:
        self.log = logging_setup.setup("cdn")
        self._client = httpx.Client(
            headers={"User-Agent": _UA},
            timeout=timeout_s,
            follow_redirects=True,
        )
        self._logged_in = False

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CdnSession":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def login(self) -> None:
        """POST the login form; the CDN sets the session cookie."""
        if not config.email() or not config.password():
            raise CdnError("SENTINEL_EMAIL / SENTINEL_PASSWORD are not set (.env is Adi's)")
        response = self._client.post(
            f"{config.cdn()}/auth/login",
            data={"email": config.email(), "password": config.password()},
        )
        if response.status_code >= 400:
            raise CdnError(f"login refused: HTTP {response.status_code}")
        self._logged_in = True
        self.log.info("cdn login ok (%s)", config.cdn())

    def get(self, path_or_url: str, max_attempts: int = 4) -> httpx.Response:
        """GET with the session cookie. *path_or_url* may be a path on the
        CDN or an absolute URL **inside the CDN origin** (relay rule B11)."""
        url = path_or_url if path_or_url.startswith("http") else f"{config.cdn()}{path_or_url}"
        # Origin check must be boundary-exact: a bare startswith(cdn) admits
        # e.g. https://cctv.example.evil.tld when cdn is https://cctv.example
        # (wave-2 review finding, 25 Sep).
        origin = config.cdn().rstrip("/")
        if url != origin and not url.startswith(origin + "/"):
            raise CdnError(f"refusing non-CDN fetch: {config.masked(url)}")
        if not self._logged_in:
            self.login()
        relogged = False
        for attempt in range(max_attempts):
            try:
                response = self._client.get(url)
            except httpx.HTTPError as exc:
                self.log.warning("cdn get failed (%s): %s", config.masked(url), exc)
                response = None
            if response is not None and response.status_code < 400:
                return response
            status = response.status_code if response is not None else "timeout"
            if status == 403 and not relogged:
                relogged = True
                try:
                    self.login()
                except CdnError as exc:
                    self.log.warning("re-login failed: %s", exc)
            base, delay = backoff_delay(attempt)
            self.log.info(
                "cdn retry attempt=%d base=%ds delay=%.1fs status=%s url=%s",
                attempt + 1, base, delay, status, config.masked(url),
            )
            if attempt < max_attempts - 1:
                time.sleep(delay)
        raise CdnError(f"gave up after {max_attempts} attempts: {config.masked(url)}")
