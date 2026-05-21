from django.core.management.base import BaseCommand, CommandError

from apps.finance.db_backup import create_backup, is_sqlite_backend


class Command(BaseCommand):
    help = "Create a timestamped SQLite backup under the backups/ directory."

    def handle(self, *args, **options):
        if not is_sqlite_backend():
            raise CommandError("Only SQLite is supported.")
        path = create_backup()
        self.stdout.write(self.style.SUCCESS(f"Backup created: {path}"))
