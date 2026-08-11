from django.core.management.base import BaseCommand

from apps.donations.recurrence_services import ensure_recurring_donations_posted


class Command(BaseCommand):
    help = (
        "Auto-post today's listings for DAILY/CUSTOM recurring donations "
        "(Mon=0…Sun=6). Safe to run frequently via cron."
    )

    def handle(self, *args, **options):
        created = ensure_recurring_donations_posted()
        self.stdout.write(
            self.style.SUCCESS(f"Created {len(created)} recurring donation listing(s).")
        )
        for food in created:
            self.stdout.write(f"  - {food.name} ({food.id}) restaurant={food.restaurant_id}")
