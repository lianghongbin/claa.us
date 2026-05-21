"""Create the initial superuser from ADMIN_EMAIL / ADMIN_PASSWORD when none exists."""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a superuser from env when the database has no superuser (idempotent)."

    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write("Superuser already exists; skipped.")
            return

        email = os.getenv("ADMIN_EMAIL", "").strip()
        password = os.getenv("ADMIN_PASSWORD", "")
        if not email or not password:
            self.stdout.write(
                self.style.WARNING(
                    "No superuser in database and ADMIN_EMAIL/ADMIN_PASSWORD not set; "
                    "run: docker compose exec web python manage.py createsuperuser"
                )
            )
            return

        User.objects.create_superuser(email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Created superuser: {email}"))
