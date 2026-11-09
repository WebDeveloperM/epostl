from django.core.management.base import BaseCommand

from apps.assignments.services import send_deadline_reminders


class Command(BaseCommand):
    help = "Muddati yaqinlashgan topshiriqlar bo‘yicha talabalarga eslatma yuboradi (cron: har soatda)."

    def handle(self, *args, **options):
        sent = send_deadline_reminders()
        self.stdout.write(self.style.SUCCESS(f"Yuborilgan eslatmalar: {sent}"))
