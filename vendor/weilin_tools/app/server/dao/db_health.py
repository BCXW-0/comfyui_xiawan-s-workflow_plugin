from __future__ import annotations

import os


FULL_CHECK_ENV = "WEILIN_DB_FULL_CHECK"
QUICK_CHECK_THRESHOLD_BYTES = 32 * 1024 * 1024


def full_check_requested() -> bool:
    value = os.getenv(FULL_CHECK_ENV, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_check_mode(file_size_bytes: int, full_check: bool | None = None) -> str:
    """Select a startup check that keeps large SQLite databases responsive."""
    if full_check is None:
        full_check = full_check_requested()
    if full_check or file_size_bytes < QUICK_CHECK_THRESHOLD_BYTES:
        return "integrity"
    return "quick"


def get_db_file_signature(db_path: str):
    """Return a cheap signature for the database and its WAL sidecar."""
    signature = []
    for path in (db_path, f"{db_path}-wal"):
        try:
            stat = os.stat(path)
        except OSError:
            signature.append(None)
        else:
            signature.append((stat.st_size, stat.st_mtime_ns))

    return tuple(signature) if signature[0] is not None else None
