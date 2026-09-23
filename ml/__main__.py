"""Worker process entry point: ``python -m ml`` (task S2.5).

Reads the active tier from the registry and runs until SIGINT or a
``data/stop`` file appears. The soak runs this against ``data/soak.db``
(``SENTINEL_DB=data/soak.db``) so synthetic reads never touch the
working database (decision F26).
"""

from ml.supervisor import Supervisor

if __name__ == "__main__":
    raise SystemExit(Supervisor().run())
