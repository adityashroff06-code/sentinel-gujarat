"""CDN session (docs/sandbox-findings.md §1) — shared by the probe, the
HLS relay (S3.1b) and the harvest (S4.2).

Form login to ``/auth/login`` (fields ``email``, ``password``), cookie jar,
browser-like User-Agent (the CDN 403s non-browser agents), jittered
exponential backoff with **one** re-login on 403/timeout. The CDN
rate-limits hard: callers keep requests gentle; this class never hammers —
concurrent 403s share ONE re-login. Every request, redirect hops included,
stays inside the configured CDN origin (B11). Every log line is masked
(root rule 1).
"""

from __future__ import annotations

import random
import threading
import time

import httpx

from backend.core import config, logging_setup

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)


class CdnError(RuntimeError):
    """The CDN refused us after retries (rate limit, auth, or outage).

    ``status`` is the last HTTP status seen (``"timeout"`` when no response
    came back, ``"login"`` for a refused or unconfigured login, ``None`` for
    the origin guard) so callers can tell a missing recording (404) from a
    rate-limit ban or an outage without parsing the message.
    """

    def __init__(self, message: str, status: int | str | None = None) -> None:
        super().__init__(message)
        self.status = status


def backoff_delay(attempt: int) -> tuple[float, float]:
    """``(base, delay)`` for *attempt* (0-based): base = min(2·2ⁿ, 30),
    delay = base · random(0.5, 1.5) — root rule 7 / decision F36."""
    base = min(2 * (2 ** attempt), 30)
    return base, base * random.uniform(0.5, 1.5)


#: Redirects followed per request. Every hop is origin-checked, so this is
#: a bound on work, not the guard; the CDN's own 302s are one hop.
MAX_REDIRECTS = 5


def _refuse_off_origin(request: httpx.Request) -> None:
    """httpx request hook, run before EVERY hop is sent — the first request
    and each redirect alike. Raises ``CdnError`` (status ``None``, the
    origin guard) for anything outside the configured CDN origin: scheme,
    host and port must match, and the path must sit under the origin's."""
    origin = httpx.URL(config.cdn())
    url = request.url
    prefix = origin.path.rstrip("/")
    if ((url.scheme, url.host, url.port) != (origin.scheme, origin.host, origin.port)
            or (prefix and url.path != prefix and not url.path.startswith(prefix + "/"))):
        raise CdnError(f"refusing off-origin redirect: {config.masked(str(url))}")


class CdnSession:
    """A logged-in CDN client. ``get()`` retries with backoff and re-logs
    in once on a 403 before giving up."""

    def __init__(self, timeout_s: float = 15.0,
                 transport: httpx.BaseTransport | None = None) -> None:
        """*transport* is for tests only (an ``httpx.MockTransport`` CDN)."""
        self.log = logging_setup.setup("cdn")
        # Redirects stay on (the CDN 302s to /auth/login), but the request
        # hook re-checks the origin on every hop: without it a 3xx carried
        # the session cookie off-origin and the relay served what came back
        # (25 Sep review). A response hook would not do — httpx builds the
        # next hop only after response hooks have run.
        self._client = httpx.Client(
            headers={"User-Agent": _UA},
            timeout=timeout_s,
            follow_redirects=True,
            max_redirects=MAX_REDIRECTS,
            event_hooks={"request": [_refuse_off_origin]},
            transport=transport,
        )
        self._logged_in = False
        # The HLS relay shares one session across request threads: only one
        # of them logs in when the session is fresh, and only one re-logs in
        # when a wave of 403s lands (no login burst — the CDN bans bursts).
        self._login_lock = threading.Lock()
        #: Login attempts FINISHED (ok or refused). A thread that saw a 403
        #: re-logs in only if no attempt finished since its GET went out.
        self._login_gen = 0

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CdnSession":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def login(self) -> None:
        """POST the login form; the CDN sets the session cookie."""
        if not config.email() or not config.password():
            raise CdnError("SENTINEL_EMAIL / SENTINEL_PASSWORD are not set (.env is Adi's)",
                           status="login")
        try:
            response = self._client.post(
                f"{config.cdn()}/auth/login",
                data={"email": config.email(), "password": config.password()},
            )
        except httpx.HTTPError as exc:
            # An unreachable CDN is a refusal like any other (callers catch
            # CdnError); the exception text carries no credential.
            raise CdnError(f"login unreachable: {type(exc).__name__}", status="login") from exc
        if response.status_code >= 400:
            raise CdnError(f"login refused: HTTP {response.status_code}", status="login")
        self._logged_in = True
        self.log.info("cdn login ok (%s)", config.cdn())

    def _login_counted(self) -> None:
        """``login()`` — the caller holds ``_login_lock`` — counted as one
        finished attempt whether it succeeds or is refused."""
        try:
            self.login()
        finally:
            self._login_gen += 1

    def _relogin_once(self, seen_gen: int) -> None:
        """Re-login after a 403, unless another thread's login attempt
        finished after this thread's GET went out (*seen_gen*): that attempt
        already renewed the cookie, or was itself refused, and a second POST
        would only feed the burst the CDN bans (25 Sep review: 16 concurrent
        403s made 16 logins). Raises ``CdnError`` if this attempt is refused."""
        with self._login_lock:
            if self._login_gen != seen_gen:
                return
            self._login_counted()

    def get(self, path_or_url: str, max_attempts: int = 4) -> httpx.Response:
        """GET with the session cookie. *path_or_url* may be a path on the
        CDN or an absolute URL **inside the CDN origin** (relay rule B11);
        a redirect is followed only while it stays inside that origin.
        Returns the (< 400) response. Raises ``CdnError`` — at once for an
        off-origin URL or redirect, else after *max_attempts* refusals."""
        url = path_or_url if path_or_url.startswith("http") else f"{config.cdn()}{path_or_url}"
        # Origin check must be boundary-exact: a bare startswith(cdn) admits
        # e.g. https://cctv.example.evil.tld when cdn is https://cctv.example
        # (wave-2 review finding, 25 Sep).
        origin = config.cdn().rstrip("/")
        if url != origin and not url.startswith(origin + "/"):
            raise CdnError(f"refusing non-CDN fetch: {config.masked(url)}")
        if not self._logged_in:
            with self._login_lock:
                if not self._logged_in:
                    self._login_counted()
        relogged = False
        status: int | str = "timeout"
        for attempt in range(max_attempts):
            seen_gen = self._login_gen  # read before the GET goes out
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
                    self._relogin_once(seen_gen)
                except CdnError as exc:
                    self.log.warning("re-login failed: %s", exc)
            base, delay = backoff_delay(attempt)
            self.log.info(
                "cdn retry attempt=%d base=%ds delay=%.1fs status=%s url=%s",
                attempt + 1, base, delay, status, config.masked(url),
            )
            if attempt < max_attempts - 1:
                time.sleep(delay)
        raise CdnError(f"gave up after {max_attempts} attempts: {config.masked(url)}",
                       status=status)
