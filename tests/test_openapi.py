"""S1.3b acceptance: the exported OpenAPI is a real contract — every
operation described, every response schema'd, no stale snapshot path."""

from __future__ import annotations

import json

from backend.tools.export_openapi import generate


def test_every_operation_has_description_and_response_schema():
    spec = generate()
    assert spec["paths"], "no paths exported"
    for path, methods in spec["paths"].items():
        for method, op in methods.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            assert op.get("description") or op.get("summary"), f"{method.upper()} {path} has no description"
            responses = op.get("responses", {})
            ok_codes = [c for c in responses if c.startswith("2")]
            assert ok_codes, f"{method.upper()} {path} has no 2xx response"
            for code in ok_codes:
                if code == "204":
                    continue
                content = responses[code].get("content", {})
                assert content, f"{method.upper()} {path} {code} has no content"
                for media, media_obj in content.items():
                    assert "schema" in media_obj, f"{method.upper()} {path} {code} {media} has no schema"


def test_no_snapshot_endpoint_survives():
    assert "snapshot.jpg" not in json.dumps(generate())
