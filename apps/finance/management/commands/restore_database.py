from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.finance.db_backup import (
    is_sqlite_backend,
    list_backups,
    resolve_backup_name,
    restore_from_path,
)


class Command(BaseCommand):
    help = "Restore SQLite database from a backup file in backups/ or an absolute path."

    def add_arguments(self, parser):
        parser.add_argument(
            "backup",
            nargs="?",
            help="Backup file name (in backups/) or path to a .sqlite3 file",
        )
        parser.add_argument(
            "--latest",
            action="store_true",
            help="Restore the most recent backup in backups/",
        )

    def handle(self, *args, **options):
        if not is_sqlite_backend():
            raise CommandError("Only SQLite is supported.")

        backup_arg = options.get("backup")
        if options["latest"]:
            backups = list_backups()
            if not backups:
                raise CommandError("No backups found.")
            backup_path = backups[0]
        elif not backup_arg:
            raise CommandError("Provide a backup file name or use --latest.")
        else:
            raw = Path(backup_arg)
            if raw.is_absolute() or raw.exists():
                backup_path = raw.resolve()
            else:
                backup_path = resolve_backup_name(backup_arg)

        restore_from_path(backup_path)
        self.stdout.write(self.style.SUCCESS(f"Database restored from: {backup_path}"))
