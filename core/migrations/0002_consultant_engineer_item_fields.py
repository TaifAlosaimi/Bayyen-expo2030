from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrate_legacy_role_and_item_statuses(apps, schema_editor):
    User = apps.get_model("core", "User")
    Item = apps.get_model("core", "Item")
    Task = apps.get_model("core", "Task")

    User.objects.filter(role="SENIOR_ENGINEER").update(
        role="CONSULTANT_ENGINEER"
    )

    for item in Item.objects.all().iterator():
        statuses = list(
            Task.objects.filter(item_id=item.pk).values_list("status", flat=True)
        )
        if statuses and all(status == "COMPLETED" for status in statuses):
            item.status = "COMPLETED"
        elif "NEEDS_CORRECTION" in statuses:
            item.status = "NEEDS_REVISION"
        elif "PENDING_REVIEW" in statuses:
            item.status = "PENDING_REVIEW"
        elif "IN_PROGRESS" in statuses:
            item.status = "IN_PROGRESS"
        else:
            item.status = "NOT_STARTED"
        item.save(update_fields=["status"])


def reverse_legacy_role(apps, schema_editor):
    User = apps.get_model("core", "User")
    User.objects.filter(role="CONSULTANT_ENGINEER").update(
        role="SENIOR_ENGINEER"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="zone",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="item",
            name="contractor_company",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="item",
            name="due_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="item",
            name="status",
            field=models.CharField(
                choices=[
                    ("NOT_STARTED", "Not Started"),
                    ("IN_PROGRESS", "In Progress"),
                    ("PENDING_REVIEW", "Pending Review"),
                    ("NEEDS_REVISION", "Needs Revision"),
                    ("COMPLETED", "Completed"),
                ],
                default="NOT_STARTED",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="item",
            name="submitted_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="submitted_items",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="item",
            name="submitted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="item",
            name="submission_note",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("PROJECT_MANAGER", "Project Manager"),
                    ("CONSULTANT_ENGINEER", "Consultant Engineer"),
                    ("SITE_ENGINEER", "Site Engineer"),
                ],
                max_length=24,
            ),
        ),
        migrations.RunPython(
            migrate_legacy_role_and_item_statuses,
            reverse_legacy_role,
        ),
        migrations.RenameField(
            model_name="task",
            old_name="senior_engineer",
            new_name="consultant_engineer",
        ),
        migrations.AlterField(
            model_name="task",
            name="consultant_engineer",
            field=models.ForeignKey(
                limit_choices_to={"role": "CONSULTANT_ENGINEER"},
                on_delete=django.db.models.deletion.PROTECT,
                related_name="consultant_tasks",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="message",
            name="task",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="messages",
                to="core.task",
            ),
        ),
        migrations.AddField(
            model_name="message",
            name="item",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="messages",
                to="core.item",
            ),
        ),
        migrations.AlterModelOptions(
            name="message",
            options={"ordering": ["created_at"]},
        ),
    ]
