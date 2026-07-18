"""
Shared model helpers.

One rule, applied everywhere: EVERY timestamp is created the same way, in
Python, as a timezone-aware UTC value. Mixing `func.now()` (database clock,
naive) with `datetime.now(timezone.utc)` (app clock, aware) would put strings
in two different formats inside the same SQLite column — which breaks sorting
and forces the frontend to guess which timestamps carry a "Z" suffix. A single
`utcnow()` helper removes the whole bug class.

Rule of thumb: pick ONE clock and ONE format for the whole system. We choose
"application clock, UTC, timezone-aware" everywhere.
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """A timezone-aware 'now' in UTC. Use this for every default timestamp."""
    return datetime.now(timezone.utc)
