"""Operator CLI for migration upgrade and verification."""

from __future__ import annotations

import argparse

from api.database import engine
from api.migrations.runtime import (
    assert_database_current,
    assert_schema_matches_metadata,
    current_revision,
    upgrade_database,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m api.migrations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    upgrade = subparsers.add_parser(
        "upgrade",
        help="upgrade the configured database through ordered revisions",
    )
    upgrade.add_argument("--revision", default="head")
    upgrade.add_argument(
        "--backup-confirmed",
        action="store_true",
        help="confirm a verified external backup exists for non-SQLite data",
    )
    subparsers.add_parser("current", help="print the current revision")
    subparsers.add_parser(
        "check",
        help="require migration head and exact ORM schema parity",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "upgrade":
        result = upgrade_database(
            engine,
            args.revision,
            backup_confirmed=args.backup_confirmed,
        )
        print(f"database revision: {result.current_revision}")
        if result.backup_path is not None:
            print(f"pre-migration backup: {result.backup_path}")
        return
    if args.command == "current":
        print(current_revision(engine) or "unversioned")
        return

    assert_database_current(engine)
    assert_schema_matches_metadata(engine)
    print("database is at migration head and matches ORM metadata")


if __name__ == "__main__":
    main()
