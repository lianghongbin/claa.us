"""SQLite database backup and restore (local dev / single-file deployments)."""
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db import connection

BACKUP_DIR_NAME = "backups"
BACKUP_PREFIX = "db_backup_"
BACKUP_SUFFIX = ".sqlite3"


def is_sqlite_backend() -> bool:
    engine = settings.DATABASES["default"]["ENGINE"]
    return engine.endswith("sqlite3")


def database_path() -> Path:
    return Path(settings.DATABASES["default"]["NAME"]).resolve()


def backup_directory() -> Path:
    directory = Path(settings.BASE_DIR) / BACKUP_DIR_NAME
    directory.mkdir(exist_ok=True)
    return directory


def backup_filename(timestamp: datetime | None = None) -> str:
    when = timestamp or datetime.now()
    stamp = when.strftime("%Y%m%d_%H%M%S")
    return f"{BACKUP_PREFIX}{stamp}{BACKUP_SUFFIX}"


def _connect_sqlite_database() -> sqlite3.Connection:
    """Open the configured SQLite database (supports shared in-memory URIs)."""
    name = str(settings.DATABASES["default"]["NAME"])
    if name.startswith("file:"):
        return sqlite3.connect(name, uri=True)
    return sqlite3.connect(name)


def create_backup() -> Path:
    """Create a consistent SQLite backup using the online backup API."""
    if not is_sqlite_backend():
        raise RuntimeError("Database backup is only supported for SQLite.")
    from django.db import connection

    connection.close()
    destination = backup_directory() / backup_filename()
    with _connect_sqlite_database() as src_conn:
        with sqlite3.connect(str(destination)) as dest_conn:
            src_conn.backup(dest_conn)
    return destination.resolve()


def list_backups() -> list[Path]:
    directory = backup_directory()
    files = [
        path.resolve()
        for path in directory.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}")
        if path.is_file()
    ]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def resolve_backup_name(name: str) -> Path:
    """Resolve a backup file under the backups directory (no path traversal)."""
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise ValueError("Invalid backup file name.")
    if not name.startswith(BACKUP_PREFIX) or not name.endswith(BACKUP_SUFFIX):
        raise ValueError("Invalid backup file name.")
    path = (backup_directory() / name).resolve()
    root = backup_directory().resolve()
    if path.parent != root or not path.is_file():
        raise ValueError("Backup file not found.")
    return path


def restore_from_path(backup_path: Path) -> None:
    if not is_sqlite_backend():
        raise RuntimeError("Database restore is only supported for SQLite.")
    dest = str(database_path())
    if "mode=memory" in dest:
        raise RuntimeError(
            "Cannot restore into an in-memory SQLite database. "
            "Set SQLITE_PATH to a file path in .env."
        )
    backup_path = backup_path.resolve()
    if not backup_path.is_file():
        raise FileNotFoundError(str(backup_path))
    with sqlite3.connect(str(backup_path)) as conn:
        conn.execute("PRAGMA schema_version")
    from django.db import connection

    connection.close()
    shutil.copy2(backup_path, dest)


def format_backup_label(path: Path) -> str:
    name = path.name
    if name.startswith(BACKUP_PREFIX) and name.endswith(BACKUP_SUFFIX):
        stamp = name[len(BACKUP_PREFIX) : -len(BACKUP_SUFFIX)]
        try:
            when = datetime.strptime(stamp, "%Y%m%d_%H%M%S")
            return when.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    modified = datetime.fromtimestamp(path.stat().st_mtime)
    return modified.strftime("%Y-%m-%d %H:%M:%S")
