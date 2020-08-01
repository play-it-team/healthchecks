from django.db import models
from uuid import uuid4
from accounts.models import Project
from datetime import datetime, timedelta
from hc.enums import CheckKind, Status, ChannelKind
from django.contrib.sites.models import Site
from hc.transport import Email, Http, Shell
import json

DEFAULT_TIMEOUT = timedelta(days=1)
DEFAULT_GRACE = timedelta(hours=1)


# Create your models here.
class Check(models.Model):
    code = models.UUIDField(default=uuid4, unique=True)
    name = models.CharField(max_length=254)
    tags = models.CharField(max_length=999, blank=True, null=True)
    project = models.ForeignKey(to=Project, on_delete=models.CASCADE)
    kind = models.CharField(max_length=10, default=CheckKind.simple.name, choices=CheckKind.choices())
    timeout = models.DurationField(default=DEFAULT_TIMEOUT)
    grace = models.DurationField(default=DEFAULT_GRACE)
    schedule = models.CharField(max_length=100, default="* * * * *")
    subject_success = models.CharField(max_length=254, blank=True)
    subject_fail = models.CharField(max_length=254, blank=True)
    ping_count = models.IntegerField(default=0)
    last_start = models.DateTimeField(null=True, blank=True)
    last_ping = models.DateTimeField(null=True, blank=True)
    last_duration = models.DurationField(null=True, blank=True)
    last_ping_was_fail = models.NullBooleanField(default=False)
    alert_after = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, default="new", choices=Status.choices())
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Check"
        verbose_name_plural = "Checks"

    def __str__(self):
        return self.name or self.code

    def url(self):
        site = Site.objects.first()
        return "{}/{}".format(site.domain, self.code)


class Ping(models.Model):
    id = models.BigAutoField(primary_key=True)
    count = models.IntegerField(default=0)
    owner = models.ForeignKey(to=Check, on_delete=models.CASCADE)
    kind = models.CharField(max_length=6, blank=True, null=True)
    scheme = models.CharField(max_length=10, default="http")
    remote_addr = models.GenericIPAddressField(blank=True, null=True)
    method = models.CharField(max_length=10, blank=True)
    ua = models.CharField(max_length=254, blank=True)
    body = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ping"
        verbose_name_plural = "Pings"

    def __str__(self):
        return "{}:{}".format(self.owner, self.id)


class Channel(models.Model):
    code = models.UUIDField(default=uuid4, unique=True)
    name = models.CharField(max_length=100, blank=True)
    project = models.ForeignKey(to=Project, on_delete=models.CASCADE)
    kind = models.CharField(max_length=20, choices=ChannelKind.choices())
    value = models.TextField(blank=True)
    email_verified = models.BooleanField(default=False)
    last_error = models.CharField(max_length=200, blank=True)
    checks = models.ManyToManyField(to=Check)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Channel"
        verbose_name_plural = "Channels"

    def __str__(self):
        return self.name or ChannelKind.__getitem__(self.kind).value

    def assign_all_checks(self):
        checks = Check.objects.filter(project=self.project)
        self.checks.add(*checks)

    @property
    def transport(self):
        if self.kind == "email":
            return Email(self)
        elif self.kind == "shell":
            return Shell(self)
        else:
            raise NotImplementedError("Unknown channel kind %s", self.kind)

    def notify(self, check):
        if self.transport.is_noop(check):
            return "no-op"

        notification = Notification(channel=self)
        notification.owner = check
        notification.check_status = check.status
        notification.error = "Sending"
        notification.save()

        if self.kind == "email":
            error = self.transport.notify(check, notification.bounce_url()) or ""
        else:
            error = self.transport.notify(check) or ""

        notification.error = error
        notification.save()

        self.last_error = error
        self.save()

        return error

    @property
    def json(self):
        return json.loads(self.value)

    @property
    def cmd_down(self):
        if self.kind == "shell":
            return self.json["cmd_down"]

    @property
    def cmd_up(self):
        if self.kind == "shell":
            return self.json["cmd_up"]

    @property
    def email_notify_down(self):
        if self.kind == "email":
            if not self.value.startswith("{"):
                return True
            val = json.loads(self.value)
            return val.get("down")

    @property
    def email_notify_up(self):
        if self.kind == "email":
            if not self.value.startswith("{"):
                return True
            val = json.loads(self.value)
            return val.get("up")

    def latest_notification(self):
        return Notification.objects.filter(channel=self).latest()


class Notification(models.Model):
    code = models.UUIDField(default=uuid4, null=True)
    owner = models.ForeignKey(to=Check, on_delete=models.CASCADE, null=True)
    check_status = models.CharField(max_length=6)
    channel = models.ForeignKey(to=Channel, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    error = models.CharField(max_length=200, blank=True)

    def bounce_url(self):
        return None
