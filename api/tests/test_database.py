import pytest

from api.database import _engine_kwargs


def test_sqlite_engine_allows_cross_thread_connections() -> None:
    assert _engine_kwargs("sqlite:///:memory:") == {
        "echo": False,
        "connect_args": {"check_same_thread": False},
    }


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://app:secret@db.example/mouvadah",
        "postgresql+psycopg2://app:secret@db.example/mouvadah",
    ],
)
def test_postgres_engine_validates_pooled_connections(
    database_url: str,
) -> None:
    assert _engine_kwargs(database_url) == {
        "echo": False,
        "pool_pre_ping": True,
    }
