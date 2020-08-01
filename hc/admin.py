from django.contrib import admin
from django.contrib import admin
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Count, F
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe
from hc.models import Channel, Check, Notification, Ping


# Register your models here.


@admin.register(Check)
class ChecksAdmin(admin.ModelAdmin):
    search_fields = ["name", "code", "project__owner__email"]
    raw_id_fields = ("project",)
    list_display = (
        "id",
        "name_tags",
        "project_",
        "created_at",
        "ping_count",
        "timeout_schedule",
        "status",
        "last_start",
        "last_ping",
    )
    list_filter = ("status", "kind", "last_ping", "last_start")

    actions = ["send_alert"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(project_name=F("project__name"))
        return qs

    @mark_safe
    def project_(self, obj):
        url = reverse("hc-checks", args=[obj.project.code])
        name = escape(obj.project_name or "Default")
        email = escape(obj.email)
        return f'{email} &rsaquo; <a href="{url}"">{name}</a>'

    @mark_safe
    def name_tags(self, obj):
        url = reverse("hc-details", args=[obj.code])
        name = escape(obj.name or "unnamed")

        s = f'<a href="{url}"">{name}</a>'
        for tag in obj.tags_list():
            s += " <span>%s</span>" % escape(tag)

        return s

    def timeout_schedule(self, obj):
        if obj.kind == "simple":
            return obj.timeout
        elif obj.kind == "cron":
            return obj.schedule
        else:
            return "Unknown"

    timeout_schedule.short_description = "Schedule"

    def send_alert(self, request, qs):
        for check in qs:
            for channel in check.channel_set.all():
                channel.notify(check)

        self.message_user(request, "%d alert(s) sent" % qs.count())

    send_alert.short_description = "Send Alert"


class SchemeListFilter(admin.SimpleListFilter):
    title = "Scheme"
    parameter_name = "scheme"

    def lookups(self, request, model_admin):
        return (("http", "HTTP"), ("https", "HTTPS"), ("email", "Email"))

    def queryset(self, request, queryset):
        if self.value():
            queryset = queryset.filter(scheme=self.value())
        return queryset


class MethodListFilter(admin.SimpleListFilter):
    title = "Method"
    parameter_name = "method"
    methods = ["HEAD", "GET", "POST", "PUT", "DELETE"]

    def lookups(self, request, model_admin):
        return zip(self.methods, self.methods)

    def queryset(self, request, queryset):
        if self.value():
            queryset = queryset.filter(method=self.value())
        return queryset


class KindListFilter(admin.SimpleListFilter):
    title = "Kind"
    parameter_name = "kind"
    kinds = ["start", "fail"]

    def lookups(self, request, model_admin):
        return zip(self.kinds, self.kinds)

    def queryset(self, request, queryset):
        if self.value():
            queryset = queryset.filter(kind=self.value())
        return queryset


# Adapted from: https://djangosnippets.org/snippets/2593/
class LargeTablePaginator(Paginator):
    """ Overrides the count method to get an estimate instead of actual count
    when not filtered
    """

    def _get_estimate(self):
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT reltuples FROM pg_class WHERE relname = %s",
                [self.object_list.query.model._meta.db_table],
            )
            return int(cursor.fetchone()[0])
        except:
            return 0

    def _get_count(self):
        """
        Changed to use an estimate if the estimate is greater than 10,000
        Returns the total number of objects, across all pages.
        """
        if not hasattr(self, "_count") or self._count is None:
            try:
                estimate = 0
                if not self.object_list.query.where:
                    estimate = self._get_estimate()
                if estimate < 10000:
                    self._count = self.object_list.count()
                else:
                    self._count = estimate
            except (AttributeError, TypeError):
                # AttributeError if object_list has no count() method.
                # TypeError if object_list.count() requires arguments
                # (i.e. is of type list).
                self._count = len(self.object_list)
        return self._count

    count = property(_get_count)


@admin.register(Ping)
class PingsAdmin(admin.ModelAdmin):
    search_fields = ("owner__name", "owner__code")
    readonly_fields = ("owner",)
    list_select_related = ("owner",)
    list_display = ("id", "created_at", "owner", "scheme", "method", "ua")
    list_filter = ("created_at", SchemeListFilter, MethodListFilter, KindListFilter)

    paginator = LargeTablePaginator
    show_full_result_count = False


@admin.register(Channel)
class ChannelsAdmin(admin.ModelAdmin):
    search_fields = ["value", "project__owner__email"]
    list_display = (
        "id",
        "kind_",
        "name",
        "project_",
        "value",
        "num_notifications",
    )
    list_filter = ("kind",)
    raw_id_fields = ("project", "checks")

    @mark_safe
    def project_(self, obj):
        url = reverse("hc-checks", args=[obj.project_code])
        name = escape(obj.project_name or "Default")
        email = escape(obj.email)
        return f"{email} &rsaquo; <a href='{url}'>{name}</a>"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(Count("notification", distinct=True))
        qs = qs.annotate(project_code=F("project__code"))
        qs = qs.annotate(project_name=F("project__name"))
        return qs

    @mark_safe
    def kind_(self, obj):
        return f'<span class="icon-{obj.kind}"></span> &nbsp; {obj.kind}'

    def num_notifications(self, obj):
        return obj.notification__count

    num_notifications.short_description = "# Notifications"


@admin.register(Notification)
class NotificationsAdmin(admin.ModelAdmin):
    search_fields = ["owner__name", "owner__code", "channel__value"]
    readonly_fields = ("owner",)
    list_select_related = ("owner", "channel")
    list_display = (
        "id",
        "created_at",
        "check_status",
        "owner",
        "channel_kind",
        "channel_value",
        "error",
    )
    list_filter = ("created_at", "check_status", "channel__kind")
    raw_id_fields = ("channel",)

    def channel_kind(self, obj):
        return obj.channel.kind

    def channel_value(self, obj):
        return obj.channel.value