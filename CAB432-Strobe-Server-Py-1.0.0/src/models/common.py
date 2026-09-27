from __future__ import annotations

from typing import Any

from ..config.settings import settings


def now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return settings.now_iso()


def copy_record(record: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a shallow copy of a record when present."""
    return dict(record) if record is not None else None