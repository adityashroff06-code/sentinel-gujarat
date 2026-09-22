"""Export the live OpenAPI document — the Model 1 API-documentation
deliverable (decision C3). Re-exported from the fresh build so no stale
path (e.g. the removed ``snapshot.jpg``) survives (docs/api.md B3).

    python -m backend.tools.export_openapi
"""

from __future__ import annotations

import json
from typing import Any

from backend.core import config

OUT_PATH = config.REPO_ROOT / "deliverables" / "registry-api.json"


def generate() -> dict[str, Any]:
    from backend.app.main import app

    return app.openapi()


def main() -> int:
    spec = generate()
    OUT_PATH.write_text(json.dumps(spec, indent=1), encoding="utf-8")
    operations = sum(len(methods) for methods in spec.get("paths", {}).values())
    print(f"openapi: {operations} operations across {len(spec.get('paths', {}))} paths -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
