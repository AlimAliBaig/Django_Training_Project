from django.urls import path
from django.contrib.auth import views as auth_views

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("accounts/register/", views.register, name="register"),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("home/", views.home, name="home"),
    path("groups/new/", views.group_create, name="group_create"),
    path("groups/join/", views.group_join, name="group_join"),
    path("groups/<int:pk>/", views.group_detail, name="group_detail"),
    path("groups/<int:pk>/leave/", views.group_leave, name="group_leave"),
    path("groups/<int:pk>/expenses/add/", views.expense_create, name="expense_create"),
    path("groups/<int:pk>/expenses/<int:expense_pk>/edit/", views.expense_update, name="expense_update"),
    path("groups/<int:pk>/expenses/<int:expense_pk>/delete/", views.expense_delete, name="expense_delete"),
    path("groups/<int:pk>/settle/", views.settlement_create, name="settlement_create"),
    path("groups/<int:pk>/export/", views.export_csv, name="export_csv"),
    path("profile/", views.profile, name="profile"),
]
