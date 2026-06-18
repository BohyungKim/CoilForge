from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_sanitized_ez_json(path: str | Path) -> dict[str, Any]:
    """Load a committed sanitized EZ JSON compatibility fixture."""

    fixture_path = Path(path)
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("sanitized EZ JSON fixture must be an object")
    return payload
