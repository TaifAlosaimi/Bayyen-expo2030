from datetime import date
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from core.models import Item, Message, Task, User


class Command(BaseCommand):
    help = "Replace Bayyen demo records with a coherent Expo 2030 scenario and two contractor accounts."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true", help="Required because existing Items, Tasks and Messages are deleted.")

    def _user(self, *, username, email, first_name, last_name, role, password=None, company_name=""):
        user = User.objects.filter(username=username).first() or User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User(username=username, email=email)
        user.username = username
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.role = role
        user.company_name = company_name
        user.is_active = True
        if password:
            user.set_password(password)
        user.save()
        return user

    @transaction.atomic
    def handle(self, *args, **options):
        if not options["confirm"]:
            self.stderr.write(self.style.ERROR("No changes made. Back up db.sqlite3, then rerun with --confirm to replace demo Items, Tasks, and Messages."))
            return

        # Keep existing accounts and update the named Project Manager and Consultant.
        pm = User.objects.filter(role=User.Role.PROJECT_MANAGER).order_by("id").first()
        if pm is None:
            pm = self._user(username="taif_pm", email="taif@bayyen.example", first_name="Taif", last_name="Alosaimi", role=User.Role.PROJECT_MANAGER, password="BayyenPM2026!")
        else:
            pm.first_name, pm.last_name = "Taif", "Alosaimi"
            pm.save(update_fields=["first_name", "last_name"])

        consultant = User.objects.filter(role=User.Role.CONSULTANT_ENGINEER).order_by("id").first()
        if consultant is None:
            consultant = self._user(username="fahad_consultant", email="fahad@bayyen.example", first_name="Fahad", last_name="Alharbi", role=User.Role.CONSULTANT_ENGINEER, password="BayyenConsultant2026!")
        else:
            consultant.first_name, consultant.last_name = "Fahad", "Alharbi"
            consultant.save(update_fields=["first_name", "last_name"])

        contractor_one = self._user(username="khalid_contractor", email="khalid@alofuq.example", first_name="Khalid", last_name="Alshehri", role=User.Role.CONTRACTOR_ENGINEER, password="BayyenKhalid2026!", company_name="Alofuq Contracting")
        contractor_two = self._user(username="omar_contractor", email="omar@najdbuild.example", first_name="Omar", last_name="Almutairi", role=User.Role.CONTRACTOR_ENGINEER, password="BayyenOmar2026!", company_name="Najd Build Co.")

        # Task.site_engineer is a distinct role in the current schema; retain an active account for task assignment.
        site_engineer = User.objects.filter(role=User.Role.SITE_ENGINEER, is_active=True).order_by("id").first()
        if site_engineer is None:
            site_engineer = self._user(username="site_engineer_demo", email="site.engineer@bayyen.example", first_name="Yousef", last_name="Saleh", role=User.Role.SITE_ENGINEER, password="BayyenSite2026!")

        Message.objects.all().delete()
        Item.objects.all().delete()

        samples = [
            {"title":"Ground Slab Pouring", "status":Item.Status.NEEDS_REVISION, "zone":"Service Building", "due":date(2026,10,11), "company":contractor_one.company_name, "contractor":contractor_one, "description":"Review the ground slab work and address the requested revisions.", "note":"The slab work is submitted for review. Please advise on the noted surface corrections."},
            {"title":"Façade Panel Installation", "status":Item.Status.PENDING_REVIEW, "zone":"Zone B", "due":date(2026,10,13), "company":contractor_two.company_name, "contractor":contractor_two, "description":"Install and inspect façade panels against the approved project specifications.", "note":"Façade panel installation is complete and ready for consultant review."},
            {"title":"Entrance Floor Tiling", "status":Item.Status.IN_PROGRESS, "zone":"Zone C", "due":date(2026,10,30), "company":contractor_one.company_name, "contractor":contractor_one, "description":"Install porcelain floor tiles at the main entrance, including levelling, joint alignment, and final cleaning.", "note":"Base preparation is complete. Tiling is in progress."},
            {"title":"Electrical Installation", "status":Item.Status.COMPLETED, "zone":"Zone A", "due":date(2026,11,5), "company":contractor_two.company_name, "contractor":contractor_two, "description":"Prepare electrical installation work in the assigned project area in line with approved drawings.", "note":"Work is scheduled to begin after the work area is released."},
        ]
        created = []
        for row in samples:
            item = Item.objects.create(title=row["title"], status=row["status"], zone=row["zone"], due_date=row["due"], contractor_company=row["company"], contractor=row["contractor"], description=row["description"], submission_note=row["note"])
            created.append(item)

        task_specs = [
            (created[0], "Slab surface inspection", "Inspect the slab surface and document the required corrections.", Task.Status.NEEDS_CORRECTION, date(2026,10,10)),
            (created[0], "Revision confirmation", "Confirm that the requested surface corrections have been completed.", Task.Status.PENDING, date(2026,10,11)),
            (created[1], "Panel alignment inspection", "Verify façade panel alignment against approved drawings.", Task.Status.COMPLETED, date(2026,10,12)),
            (created[1], "Final façade review", "Complete the final check before handover.", Task.Status.COMPLETED, date(2026,10,13)),
            (created[2], "Prepare tiling base", "Level and prepare the base before laying tiles.", Task.Status.COMPLETED, date(2026,10,20)),
            (created[2], "Install entrance tiles", "Install tiles and align joints at the main entrance.", Task.Status.IN_PROGRESS, date(2026,10,28)),
            (created[3], "Electrical safety inspection", "Complete the electrical safety checks and record the result.", Task.Status.COMPLETED, date(2026,11,3)),
        ]
        for item, title, description, status, due in task_specs:
            Task.objects.create(item=item, title=title, description=description, area=item.zone, site_engineer=site_engineer, consultant_engineer=consultant, status=status, due_date=due)

        # Realistic, clearly fictional sample conversations for the prototype.
        Message.objects.create(item=created[2], sender=pm, receiver=consultant, content="Is the entrance tiling still on track for the 30 Oct handover?")
        Message.objects.create(item=created[2], sender=consultant, receiver=pm, content="The base preparation is complete, and tiling is in progress. The contractor is working toward the planned handover.")
        Message.objects.create(item=created[0], sender=consultant, receiver=contractor_one, content="Please correct the marked slab surface areas and submit an updated note for review.")
        Message.objects.create(item=created[0], sender=contractor_one, receiver=consultant, content="Understood. We will complete the corrections and resubmit the item for inspection.")
        Message.objects.create(item=created[3], sender=contractor_two, receiver=consultant, content="Electrical installation and safety checks are complete. The item is ready for your records.")
        Message.objects.create(item=created[3], sender=consultant, receiver=contractor_two, content="Thank you. The completion has been recorded. Please keep the inspection notes available for handover.")

        self.stdout.write(self.style.SUCCESS("Bayyen demo reset complete: 4 Items, 7 Tasks, sample conversations, Taif Alosaimi (Project Manager), Fahad Alharbi (Consultant Engineer), and two Contractor Engineer accounts created/updated."))
        self.stdout.write("Contractor 1: khalid@alofuq.example / BayyenKhalid2026!")
        self.stdout.write("Contractor 2: omar@najdbuild.example / BayyenOmar2026!")
        self.stdout.write("Note: the reset removes all existing Item, Task, and Message records. User accounts are retained.")
