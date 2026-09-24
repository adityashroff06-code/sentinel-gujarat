"""backend/core/db.py — connection threading regression (S3.2 smoke find).

FastAPI runs a sync generator dependency's teardown in a different anyio
worker thread than its body under concurrent requests, so ``get_db``'s
``con.close()`` crossed threads and raised ``sqlite3.ProgrammingError``,
500-ing random requests (reproduced by ``scripts/smoke_frontend.py``:
the header stats poll racing a page load). ``connect()`` now passes
``check_same_thread=False``; each connection still serves one request.
"""

from __future__ import annotations

import threading

from backend.core import db as dbmod


def test_connection_survives_use_and_close_from_another_thread(tmp_path, monkeypatch):
    monkeypatch.setenv("SENTINEL_DB", str(tmp_path / "threading.db"))
    con = dbmod.connect()
    dbmod.migrate(con)
    con.execute("SELECT COUNT(*) FROM cameras").fetchone()

    errors: list[BaseException] = []

    def use_and_close() -> None:  # the anyio-teardown shape: other thread
        try:
            con.execute("SELECT COUNT(*) FROM schema_version").fetchone()
            con.close()
        except BaseException as exc:  # pragma: no cover - the regression
            errors.append(exc)

    worker = threading.Thread(target=use_and_close)
    worker.start()
    worker.join(timeout=10)
    assert not worker.is_alive()
    assert errors == [], f"cross-thread use/close raised: {errors!r}"
