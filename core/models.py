from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        PROJECT_MANAGER = "PROJECT_MANAGER", "Project Manager"
        CONSULTANT_ENGINEER = "CONSULTANT_ENGINEER", "Consultant Engineer"
        SITE_ENGINEER = "SITE_ENGINEER", "Site Engineer"
        CONTRACTOR_ENGINEER = "CONTRACTOR_ENGINEER", "Contractor Engineer"

    role = models.CharField(max_length=24, choices=Role.choices)
    company_name = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.get_full_name() or self.username


class Item(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = "NOT_STARTED", "Not Started"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        PENDING_REVIEW = "PENDING_REVIEW", "Pending Review"
        NEEDS_REVISION = "NEEDS_REVISION", "Needs Revision"
        COMPLETED = "COMPLETED", "Completed"

    title = models.CharField(max_length=200)
    description = models.TextField()
    zone = models.CharField(max_length=100, blank=True)
    contractor_company = models.CharField(max_length=200, blank=True)
    contractor = models.ForeignKey(
        "User", on_delete=models.PROTECT, related_name="contracted_items",
        null=True, blank=True, limit_choices_to={"role": "CONTRACTOR_ENGINEER"},
    )
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NOT_STARTED,
    )
    submitted_by = models.ForeignKey(
        "User",
        on_delete=models.PROTECT,
        related_name="submitted_items",
        null=True,
        blank=True,
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    submission_note = models.TextField(blank=True)

    def __str__(self):
        return self.title


class Task(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        PENDING_REVIEW = "PENDING_REVIEW", "Pending Review"
        COMPLETED = "COMPLETED", "Completed"
        NEEDS_CORRECTION = "NEEDS_CORRECTION", "Needs Correction"

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    area = models.CharField(max_length=100, blank=True)
    site_engineer = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="assigned_tasks",
        limit_choices_to={"role": User.Role.SITE_ENGINEER},
    )
    consultant_engineer = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="consultant_tasks",
        limit_choices_to={"role": User.Role.CONSULTANT_ENGINEER},
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    due_date = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Message(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="messages",
        null=True,
        blank=True,
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name="messages",
        null=True,
        blank=True,
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="sent_messages",
    )
    receiver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="received_messages",
    )
    content = models.TextField(blank=True)
    attachment = models.FileField(
        upload_to="task_attachments/",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        context = self.task or self.item
        return f"Message for {context}" if context else f"Message #{self.pk}"
