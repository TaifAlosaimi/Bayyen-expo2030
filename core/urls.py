from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("consultant-engineer/", views.consultant_dashboard, name="consultant_dashboard"),
    path("contractor-engineer/", views.contractor_dashboard, name="contractor_dashboard"),
    path(
        "consultant-engineer/items/<int:item_id>/",
        views.consultant_item_detail,
        name="consultant_item_detail",
    ),
    path(
    "contractor-engineer/items/<int:item_id>/",
    views.contractor_item_detail,
    name="contractor_item_detail",
    ),
    path("project-manager/", views.project_manager_dashboard, name="project_manager_dashboard"),
    path("project-manager/items/<int:item_id>/", views.project_manager_item_detail, name="project_manager_item_detail"),

]
