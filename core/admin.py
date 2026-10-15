from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Item, Message, Task, User


@admin.register(User)
class BayyenUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Bayyen Role", {"fields": ("role", "company_name")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Bayyen Role", {"fields": ("role", "company_name")}),
    )


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "zone", "contractor_company", "contractor", "due_date")
    list_filter = ("status", "zone", "contractor")
    search_fields = ("title", "contractor_company")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "title", "item", "status", "site_engineer",
        "consultant_engineer", "due_date",
    )
    list_filter = ("status", "area")
    search_fields = ("title", "item__title")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "item", "task", "sender", "receiver", "created_at")
    list_filter = ("created_at",)
    search_fields = ("content",)
