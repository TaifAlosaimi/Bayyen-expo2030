from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core", "0002_consultant_engineer_item_fields")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="company_name",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("PROJECT_MANAGER", "Project Manager"),
                    ("CONSULTANT_ENGINEER", "Consultant Engineer"),
                    ("SITE_ENGINEER", "Site Engineer"),
                    ("CONTRACTOR_ENGINEER", "Contractor Engineer"),
                ],
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="item",
            name="contractor",
            field=models.ForeignKey(
                blank=True, null=True, limit_choices_to={"role": "CONTRACTOR_ENGINEER"},
                on_delete=django.db.models.deletion.PROTECT,
                related_name="contracted_items", to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
