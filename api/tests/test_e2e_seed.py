"""Safety checks for the destructive portion of the Playwright seed helper."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import seed_e2e


def _engine(database: str | None, dialect: str = "sqlite") -> SimpleNamespace:
    return SimpleNamespace(
        url=SimpleNamespace(database=database),
        dialect=SimpleNamespace(name=dialect),
    )


def test_seed_accepts_only_the_dedicated_playwright_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = (
        Path(seed_e2e.__file__).resolve().parents[1]
        / "web"
        / "tests"
        / ".e2e-taskable.db"
    ).resolve()
    monkeypatch.setattr(seed_e2e, "engine", _engine(str(expected)))

    assert seed_e2e._validated_database_path() == expected


@pytest.mark.parametrize(
    ("database", "dialect"),
    [
        (None, "sqlite"),
        ("/tmp/taskable.db", "sqlite"),
        (
            str(
                (
                    Path(seed_e2e.__file__).resolve().parents[1]
                    / "web"
                    / "tests"
                    / ".e2e-taskable.db"
                ).resolve()
            ),
            "postgresql",
        ),
    ],
)
def test_seed_refuses_every_other_database(
    monkeypatch: pytest.MonkeyPatch,
    database: str | None,
    dialect: str,
) -> None:
    monkeypatch.setattr(seed_e2e, "engine", _engine(database, dialect))

    with pytest.raises(RuntimeError, match="Playwright|Refusing"):
        seed_e2e._validated_database_path()
