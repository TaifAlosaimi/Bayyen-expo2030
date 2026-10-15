from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Item


class Command(BaseCommand):
    help = "Replace current demo items with the four Bayyen Expo 2030 sample items."

    @transaction.atomic
    def handle(self, *args, **options):
        demo_items = [
            {
                "title": "Ground Slab Pouring",
                "description": "Inspect and review the ground slab pouring works for the Expo project.",
                "zone": "Service Building",
                "contractor_company": "Alofuq Contracting",
                "due_date": date(2026, 10, 11),
                "status": Item.Status.NEEDS_REVISION,
            },
            {
                "title": "Façade Panel Installation",
                "description": "Review façade panel installation and verify alignment and finish.",
                "zone": "Zone B",
                "contractor_company": "Alofuq Contracting",
                "due_date": date(2026, 10, 13),
                "status": Item.Status.PENDING_REVIEW,
            },
            {
                "title": "Entrance Floor Tiling",
                "description": "Track entrance floor tiling progress ahead of the handover date.",
                "zone": "Zone C",
                "contractor_company": "Alofuq Contracting",
                "due_date": date(2026, 10, 30),
                "status": Item.Status.IN_PROGRESS,
            },
            {
                "title": "Electrical Installation",
                "description": "Prepare and inspect the electrical installation works.",
                "zone": "Zone A",
                "contractor_company": "Alofuq Contracting",
                "due_date": date(2026, 11, 5),
                "status": Item.Status.NOT_STARTED,
            },
        ]
        # This is demo-data setup: deleting extra Items also deletes their related
        # Tasks and Messages because those relationships use on_delete=CASCADE.
        Item.objects.all().delete()
        Item.objects.bulk_create([Item(**data) for data in demo_items])
        self.stdout.write(self.style.SUCCESS("Created exactly four Bayyen demo items."))
