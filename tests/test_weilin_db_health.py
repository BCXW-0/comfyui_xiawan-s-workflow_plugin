from vendor.weilin_tools.app.server.dao.db_health import (
    FULL_CHECK_ENV,
    QUICK_CHECK_THRESHOLD_BYTES,
    get_check_mode,
    get_db_file_signature,
)


def test_large_databases_use_a_limited_check_by_default():
    assert get_check_mode(QUICK_CHECK_THRESHOLD_BYTES) == "quick"
    assert get_check_mode(QUICK_CHECK_THRESHOLD_BYTES - 1) == "integrity"


def test_full_check_can_be_requested_explicitly(monkeypatch):
    monkeypatch.setenv(FULL_CHECK_ENV, "1")
    assert get_check_mode(QUICK_CHECK_THRESHOLD_BYTES) == "integrity"


def test_database_signature_includes_wal_sidecar(tmp_path):
    database = tmp_path / "tags.db"
    wal = tmp_path / "tags.db-wal"
    database.write_bytes(b"database")

    first = get_db_file_signature(str(database))
    wal.write_bytes(b"wal")
    second = get_db_file_signature(str(database))

    assert first != second
