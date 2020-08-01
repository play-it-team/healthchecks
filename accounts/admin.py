from django.contrib import admin
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.db.models import Count, F
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe
from accounts.models import Profile, Project


# Register your models here.
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    search_fields = ["id", "user__email"]
    list_per_page = 30
    list_select_related = ("user",)
    list_display = (
        "id",
        "user",
        "projects",
    )
    list_filter = (
        "user__date_joined",
    )
