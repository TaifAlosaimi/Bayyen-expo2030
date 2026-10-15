from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    ItemEditForm, ItemMessageForm, ReviewCommentForm, TaskForm,
)
from .models import Item, Message, Task

User = get_user_model()


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(
            attrs={
                "placeholder": "name@company.com",
                "autocomplete": "email",
            }
        ),
    )

    def clean(self):
        email = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if email and password:
            try:
                user = User.objects.get(email__iexact=email)
            except (User.DoesNotExist, User.MultipleObjectsReturned):
                user = None

            if user is not None:
                self.cleaned_data["username"] = user.get_username()

        return super().clean()


def home(request):
    return render(request, "core/home.html")


def login_view(request):
    form = EmailAuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        if user.role == User.Role.CONSULTANT_ENGINEER:
            return redirect("core:consultant_dashboard")
        if user.role == User.Role.CONTRACTOR_ENGINEER:
            return redirect("core:contractor_dashboard")
        
        if user.role == User.Role.PROJECT_MANAGER:
            return redirect("core:project_manager_dashboard")

        return redirect("core:home")
    return render(request, "core/login.html", {"form": form})


def logout_view(request):
    """End the current session and return to the existing login page."""
    if request.method == "POST":
        logout(request)
    return redirect("core:login")


def _sync_item_status_from_tasks(item):
    """Move an item into review once all its tasks are complete.

    If a task later becomes incomplete, reopen the item as In Progress.
    An empty task list never triggers automatic completion or review.
    """
    tasks = item.tasks.all()
    if not tasks.exists():
        return

    all_tasks_completed = not tasks.exclude(status=Task.Status.COMPLETED).exists()
    if all_tasks_completed:
        if item.status != Item.Status.COMPLETED:
            item.status = Item.Status.PENDING_REVIEW
            item.save(update_fields=["status"])
    elif item.status in {Item.Status.PENDING_REVIEW, Item.Status.COMPLETED}:
        item.status = Item.Status.IN_PROGRESS
        item.save(update_fields=["status"])


def _has_consultant_access(user):
    return user.is_authenticated and user.role == User.Role.CONSULTANT_ENGINEER


def _has_contractor_access(user):
    return user.is_authenticated and user.role == User.Role.CONTRACTOR_ENGINEER


@login_required(login_url="core:login")
def contractor_dashboard(request):
    if not _has_contractor_access(request.user):
        return HttpResponseForbidden("Contractor Engineer access required.")

    items = Item.objects.filter(contractor=request.user).order_by("due_date", "title")
    total_items = items.count()
    completed_items = items.filter(status=Item.Status.COMPLETED).count()
    progress = round(completed_items * 100 / total_items) if total_items else 0
    return render(request, "core/contractor_dashboard.html", {
        "items": items,
        "total_items": total_items,
        "completed_items": completed_items,
        "progress": progress,
    })


@login_required(login_url="core:login")
def consultant_dashboard(request):
    if not _has_consultant_access(request.user):
        return HttpResponseForbidden("Consultant Engineer access required.")

    items = Item.objects.prefetch_related("tasks").order_by("due_date", "title")
    total_items = items.count()
    completed_items = items.filter(status=Item.Status.COMPLETED).count()
    progress = round(completed_items * 100 / total_items) if total_items else 0

    return render(
        request,
        "core/consultant_dashboard.html",
        {
            "items": items,
            "total_items": total_items,
            "completed_items": completed_items,
            "progress": progress,
        },
    )


def _item_detail_context(item, consultant_user=None, **overrides):
    project_manager = User.objects.filter(
        role=User.Role.PROJECT_MANAGER,
        is_active=True,
    ).order_by("id").first()
    tasks = list(
        item.tasks.select_related(
            "site_engineer", "consultant_engineer"
        ).order_by("id")
    )
    editing_task_id = overrides.get("editing_task_id")
    task_edit_form = overrides.get("task_edit_form")
    task_rows = []
    for task in tasks:
        form = TaskForm(instance=task)
        if task_edit_form is not None and task.pk == editing_task_id:
            form = task_edit_form
        task_rows.append({"task": task, "form": form})

    selected_conversation = overrides.get("selected_conversation", "project_manager")
    base_messages = item.messages.filter(task__isnull=True).select_related(
        "sender", "receiver"
    )
    if selected_conversation == "contractor_engineer":
        contractor = item.contractor
        if contractor is None:
            comments = base_messages.none()
        else:
            comments = base_messages.filter(
                ((Q(sender=consultant_user, receiver=contractor) | Q(sender=contractor, receiver=consultant_user)))
            )
    else:
        selected_conversation = "project_manager"
        comments = base_messages.filter(
            ((Q(sender=consultant_user, receiver=project_manager) | Q(sender=project_manager, receiver=consultant_user)))
        )
    contractor_engineers = User.objects.filter(
        pk=item.contractor_id,
        role=User.Role.CONTRACTOR_ENGINEER,
        is_active=True,
    ) if item.contractor_id else User.objects.none()
    context = {
        "item": item,
        "tasks": tasks,
        "completed_tasks": sum(1 for task in tasks if task.status == Task.Status.COMPLETED),
        "task_rows": task_rows,
        "comments": comments,
        "selected_conversation": selected_conversation,
        "item_form": ItemEditForm(instance=item),
        "task_form": TaskForm(),
        "review_form": ReviewCommentForm(),
        "message_form": ItemMessageForm(),
        "project_manager": project_manager,
        "contractor_engineers": contractor_engineers,
    }
    context.update(overrides)
    return context


@login_required(login_url="core:login")
def consultant_item_detail(request, item_id):
    if not _has_consultant_access(request.user):
        return HttpResponseForbidden("Consultant Engineer access required.")

    item = get_object_or_404(Item, pk=item_id)

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "edit_item":
            form = ItemEditForm(request.POST, instance=item)
            if form.is_valid():
                form.save()
                messages.success(request, "Item details updated.")
                return redirect("core:consultant_item_detail", item_id=item.pk)
            return render(
                request,
                "core/consultant_item_detail.html",
                _item_detail_context(item, consultant_user=request.user, item_form=form),
            )

        if action == "add_task":
            form = TaskForm(request.POST)
            if form.is_valid():
                task = form.save(commit=False)
                task.item = item
                task.consultant_engineer = request.user
                task.save()
                _sync_item_status_from_tasks(item)
                messages.success(request, "Task added.")
                return redirect("core:consultant_item_detail", item_id=item.pk)
            return render(
                request,
                "core/consultant_item_detail.html",
                _item_detail_context(item, consultant_user=request.user, task_form=form),
            )

        if action == "edit_task":
            task = get_object_or_404(Task, pk=request.POST.get("task_id"), item=item)
            form = TaskForm(request.POST, instance=task)
            if form.is_valid():
                updated_task = form.save(commit=False)
                updated_task.consultant_engineer = request.user
                updated_task.save()
                _sync_item_status_from_tasks(item)
                messages.success(request, "Task updated.")
                return redirect("core:consultant_item_detail", item_id=item.pk)
            return render(
                request,
                "core/consultant_item_detail.html",
                _item_detail_context(
                    item,
                    consultant_user=request.user,
                    editing_task_id=task.pk,
                    task_edit_form=form,
                ),
            )

        if action == "review_approve":
            if item.status != Item.Status.PENDING_REVIEW:
                messages.error(request, "Only items pending review can be approved.")
            else:
                item.status = Item.Status.COMPLETED
                item.save(update_fields=["status"])
                messages.success(request, "Item approved.")
            return redirect("core:consultant_item_detail", item_id=item.pk)

        if action == "review_return":
            form = ReviewCommentForm(request.POST)
            if form.is_valid():
                project_manager = User.objects.filter(
                    role=User.Role.PROJECT_MANAGER,
                    is_active=True,
                ).order_by("id").first()
                if project_manager is None:
                    messages.error(
                        request,
                        "No active Project Manager account is available to receive this comment.",
                    )
                elif item.status != Item.Status.PENDING_REVIEW:
                    messages.error(request, "Only items pending review can be returned.")
                else:
                    with transaction.atomic():
                        item.status = Item.Status.NEEDS_REVISION
                        item.save(update_fields=["status"])
                        Message.objects.create(
                            item=item,
                            sender=request.user,
                            receiver=project_manager,
                            content=form.cleaned_data["comment"],
                        )
                    messages.success(request, "Item returned with comment.")
                return redirect("core:consultant_item_detail", item_id=item.pk)
            return render(
                request,
                "core/consultant_item_detail.html",
                _item_detail_context(item, consultant_user=request.user, review_form=form),
            )

        if action == "send_comment":
            form = ItemMessageForm(request.POST, request.FILES)
            selected_conversation = request.POST.get("conversation", "project_manager")
            if selected_conversation == "contractor_engineer":
                recipient = item.contractor if item.contractor and item.contractor.is_active else None
                missing_recipient_message = (
                    "No active Contractor Engineer is assigned to this item yet."
                )
            else:
                selected_conversation = "project_manager"
                recipient = User.objects.filter(
                    role=User.Role.PROJECT_MANAGER,
                    is_active=True,
                ).order_by("id").first()
                missing_recipient_message = "No active Project Manager account is available to receive this comment."
            if recipient is None:
                messages.error(request, missing_recipient_message)
                return redirect(f"{redirect('core:consultant_item_detail', item_id=item.pk).url}?conversation={selected_conversation}")
            if form.is_valid():
                comment = form.save(commit=False)
                comment.item = item
                comment.sender = request.user
                comment.receiver = recipient
                comment.save()
                messages.success(request, "Comment sent.")
                return redirect(f"{redirect('core:consultant_item_detail', item_id=item.pk).url}?conversation={selected_conversation}")
            return render(
                request,
                "core/consultant_item_detail.html",
                _item_detail_context(item, consultant_user=request.user, message_form=form, selected_conversation=selected_conversation),
            )

    selected_conversation = request.GET.get("conversation", "project_manager")
    if selected_conversation not in {"project_manager", "contractor_engineer"}:
        selected_conversation = "project_manager"
    return render(
        request,
        "core/consultant_item_detail.html",
        _item_detail_context(item, consultant_user=request.user, selected_conversation=selected_conversation),
    )


@login_required(login_url="core:login")
def contractor_item_detail(request, item_id):
    """Show one assigned item to its contractor and allow only agreed actions."""
    if not _has_contractor_access(request.user):
        return HttpResponseForbidden("Contractor Engineer access required.")

    # Scope the lookup itself so changing the URL cannot expose another contractor's item.
    item = get_object_or_404(
        Item.objects.select_related("contractor"),
        pk=item_id,
        contractor=request.user,
    )

    tasks = list(
        item.tasks.select_related("site_engineer", "consultant_engineer").order_by("id")
    )
    consultant = next(
        (task.consultant_engineer for task in tasks
         if task.consultant_engineer_id and task.consultant_engineer.is_active),
        None,
    )

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "update_task_status":
            task_id = request.POST.get("task_id")
            task = get_object_or_404(Task, pk=task_id, item=item)
            allowed_statuses = {
                Task.Status.PENDING,
                Task.Status.IN_PROGRESS,
                Task.Status.COMPLETED,
            }
            new_status = request.POST.get("status", "")
            if item.status in {Item.Status.PENDING_REVIEW, Item.Status.COMPLETED}:
                messages.error(request, "Task statuses cannot be changed while the item is under review or approved.")
            elif new_status not in allowed_statuses:
                messages.error(request, "Invalid task status.")
            else:
                task.status = new_status
                task.save(update_fields=["status", "updated_at"])
                if item.status == Item.Status.NOT_STARTED:
                    item.status = Item.Status.IN_PROGRESS
                    item.save(update_fields=["status"])
                messages.success(request, "Task status updated.")
            return redirect("core:contractor_item_detail", item_id=item.pk)

        if action == "submit_item":
            task_queryset = item.tasks.all()
            if consultant is None:
                messages.error(request, "This item has no active Consultant Engineer assigned yet.")
            elif not task_queryset.exists():
                messages.error(request, "Add at least one task before submitting this item.")
            elif task_queryset.exclude(status=Task.Status.COMPLETED).exists():
                messages.error(request, "Complete all tasks before submitting this item.")
            elif item.status == Item.Status.COMPLETED:
                messages.info(request, "This item has already been approved.")
            elif item.status == Item.Status.PENDING_REVIEW:
                messages.info(request, "This item has already been submitted for review.")
            else:
                item.status = Item.Status.PENDING_REVIEW
                item.submitted_by = request.user
                item.submitted_at = timezone.now()
                item.save(update_fields=["status", "submitted_by", "submitted_at"])
                messages.success(request, "Item submitted to the Consultant Engineer for review.")
            return redirect("core:contractor_item_detail", item_id=item.pk)

        if action == "send_comment":
            form = ItemMessageForm(request.POST, request.FILES)
            if consultant is None:
                messages.error(request, "This item has no active Consultant Engineer assigned yet.")
                return redirect("core:contractor_item_detail", item_id=item.pk)
            if form.is_valid():
                message = form.save(commit=False)
                message.item = item
                message.sender = request.user
                message.receiver = consultant
                message.save()
                messages.success(request, "Message sent to the Consultant Engineer.")
                return redirect("core:contractor_item_detail", item_id=item.pk)
            message_form = form
        else:
            return HttpResponseForbidden("This action is not available to Contractor Engineers.")
    else:
        message_form = ItemMessageForm()

    task_rows = [{"task": task} for task in tasks]
    return render(request, "core/contractor_item_detail.html", {
        "item": item,
        "tasks": tasks,
        "task_rows": task_rows,
        "completed_tasks": sum(task.status == Task.Status.COMPLETED for task in tasks),
        "consultant": consultant,
        "comments": _contractor_consultant_messages(item, request.user, consultant),
        "message_form": message_form,
    })


def _contractor_consultant_messages(item, contractor, consultant):
    """Only expose the conversation between this item's contractor and consultant."""
    if consultant is None:
        return item.messages.none()
    return item.messages.filter(task__isnull=True).filter(
        (Q(sender=contractor, receiver=consultant)
         | Q(sender=consultant, receiver=contractor))
    ).select_related("sender", "receiver").order_by("created_at")


def _has_project_manager_access(user):
    return user.is_authenticated and user.role == User.Role.PROJECT_MANAGER


@login_required(login_url="core:login")
def project_manager_dashboard(request):
    """Read-only project overview for Project Managers."""
    if not _has_project_manager_access(request.user):
        return HttpResponseForbidden("Project Manager access required.")

    items = Item.objects.select_related("contractor").prefetch_related("tasks").order_by("due_date", "title")
    total_items = items.count()
    completed_items = items.filter(status=Item.Status.COMPLETED).count()
    progress = round(completed_items * 100 / total_items) if total_items else 0
    return render(request, "core/project_manager_dashboard.html", {
        "items": items,
        "total_items": total_items,
        "completed_items": completed_items,
        "progress": progress,
    })


@login_required(login_url="core:login")
def project_manager_item_detail(request, item_id):
    """Read-only item details and a conversation with the item's consultant."""
    if not _has_project_manager_access(request.user):
        return HttpResponseForbidden("Project Manager access required.")

    item = get_object_or_404(Item, pk=item_id)
    consultant_ids = item.tasks.values_list("consultant_engineer_id", flat=True).distinct()
    consultant = User.objects.filter(
        pk__in=consultant_ids,
        role=User.Role.CONSULTANT_ENGINEER,
        is_active=True,
    ).order_by("id").first()

    if request.method == "POST":
        if request.POST.get("action") != "send_comment":
            return HttpResponseForbidden("This action is not available to Project Managers.")
        if consultant is None:
            messages.error(request, "No active Consultant Engineer is assigned to this item.")
            return redirect("core:project_manager_item_detail", item_id=item.pk)

        form = ItemMessageForm(request.POST, request.FILES)
        if form.is_valid():
            message = form.save(commit=False)
            message.item = item
            message.sender = request.user
            message.receiver = consultant
            message.save()
            messages.success(request, "Comment sent to the Consultant Engineer.")
            return redirect("core:project_manager_item_detail", item_id=item.pk)
    else:
        form = ItemMessageForm()

    comments = item.messages.filter(task__isnull=True)
    if consultant is not None:
        comments = comments.filter(
            Q(sender=request.user, receiver=consultant)
            | Q(sender=consultant, receiver=request.user)
        ).select_related("sender", "receiver").order_by("created_at")
    else:
        comments = comments.none()

    return render(request, "core/project_manager_item_detail.html", {
        "item": item,
        "consultant": consultant,
        "comments": comments,
        "message_form": form,
    })
