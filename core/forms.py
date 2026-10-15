from django import forms
from django.contrib.auth import get_user_model

from .models import Item, Message, Task

User = get_user_model()


class ItemEditForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ("title", "zone", "due_date", "contractor_company", "description")
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ("title", "description", "area", "site_engineer", "status", "due_date")
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["site_engineer"].queryset = User.objects.filter(
            role=User.Role.SITE_ENGINEER,
            is_active=True,
        )


class ReviewCommentForm(forms.Form):
    comment = forms.CharField(
        label="Comment",
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class ItemMessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ("content", "attachment")
        widgets = {
            "content": forms.TextInput(attrs={"placeholder": "Write a comment..."}),
        }
