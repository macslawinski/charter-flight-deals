from ingest.config import load_settings


def test_database_url_is_stripped(monkeypatch):
    # GitHub secrets pasted with a trailing newline produced: database "postgres\n" does not exist
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/postgres\n")
    assert load_settings().database_url == "postgresql://u:p@host:5432/postgres"


def test_blank_database_url_is_none(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "  \n")
    assert load_settings().database_url is None
