from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.models import Item, Task

User = get_user_model()


class Command(BaseCommand):
    help = "Create or update Bayyen demo data without resetting existing passwords."

    def handle(self, *args, **options):
        users_data = [
            ("pm_demo", User.Role.PROJECT_MANAGER, "manager@bayyen.com"),
            ("senior_demo", User.Role.CONSULTANT_ENGINEER, "sen.eng@bayyen.com"),
            ("site_demo", User.Role.SITE_ENGINEER, "site.eng@bayyen.com"),
        ]
        users = {}

        for username, role, email in users_data:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"role": role, "email": email},
            )
            changed_fields = []
            if user.role != role:
                user.role = role
                changed_fields.append("role")
            if user.email.lower() != email.lower():
                user.email = email
                changed_fields.append("email")
            if changed_fields:
                user.save(update_fields=changed_fields)
            if created:
                user.set_password("BayyinDemo123!")
                user.save(update_fields=["password"])
            users[role] = user

        items_data = [
            {
                "title": "Site Preparation",
                "description": "Prepare the construction site before the main construction activities begin.",
                "zone": "Zone A",
                "contractor_company": "Al Ofuq Contracting",
                "status": Item.Status.IN_PROGRESS,
                "days": 10,
            },
            {
                "title": "Foundation Works",
                "description": "Coordinate and document the foundation construction and inspection activities.",
                "zone": "Zone B",
                "contractor_company": "Al Ofuq Contracting",
                "status": Item.Status.PENDING_REVIEW,
                "days": 5,
            },
            {
                "title": "Structural Works",
                "description": "Track structural construction tasks and their required handovers.",
                "zone": "Zone C",
                "contractor_company": "Al Noor Contracting",
                "status": Item.Status.NEEDS_REVISION,
                "days": 12,
            },
        ]
        items = {}

        for data in items_data:
            item_data = data.copy()
            days = item_data.pop("days")
            title = item_data["title"]
            item, created = Item.objects.get_or_create(
                title=title,
                defaults={
                    **item_data,
                    "due_date": date.today() + timedelta(days=days),
                },
            )
            items[title] = item

        tasks_data = [
            ("Site Preparation", "Site Inspection", "Inspect the site and document existing conditions.", "Zone A", Task.Status.COMPLETED, -2),
            ("Site Preparation", "Site Clearance", "Clear the designated area before construction.", "Zone A", Task.Status.IN_PROGRESS, 3),
            ("Foundation Works", "Foundation Inspection", "Inspect foundation work and prepare the required handover documentation.", "Zone B", Task.Status.PENDING_REVIEW, 5),
            ("Foundation Works", "Concrete Work", "Complete and document the planned concrete work.", "Zone B", Task.Status.PENDING, 7),
            ("Structural Works", "Structural Inspection", "Inspect structural work and record findings.", "Zone C", Task.Status.NEEDS_CORRECTION, 10),
            ("Structural Works", "Handover Documentation", "Prepare the task documentation for review.", "Zone C", Task.Status.IN_PROGRESS, 12),
        ]

        for item_title, title, description, area, status, days in tasks_data:
            Task.objects.get_or_create(
                item=items[item_title],
                title=title,
                defaults={
                    "description": description,
                    "area": area,
                    "status": status,
                    "due_date": date.today() + timedelta(days=days),
                    "site_engineer": users[User.Role.SITE_ENGINEER],
                    "consultant_engineer": users[User.Role.CONSULTANT_ENGINEER],
                },
            )

        self.stdout.write(self.style.SUCCESS("Bayyen demo data created or updated."))
