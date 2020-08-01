import os

from django.template.loader import render_to_string
from django.utils import timezone
import requests
from hc.emails import Email as em
from accounts.models import Profile
from hc.enums import Status
from hc.utils import replace
from django.contrib.sites.models import Site


def tmpl(template_name, **context):
    template_path = "integrations/%s" % template_name
    # \xa0 is non-breaking space. It causes SMS messages to use UCS2 encoding
    # and cost twice the money.
    return render_to_string(template_path, context).strip().replace("\xa0", " ")


class Transport(object):
    def __init__(self, channel):
        self.channel = channel

    def notify(self, check):
        """ Send notification about current status of the check.
        This method returns None on success, and error message
        on error.
        """

        raise NotImplementedError()

    def is_noop(self, check):
        """ Return True if transport will ignore check's current status.
        This method is overridden in Webhook subclass where the user can
        configure webhook urls for "up" and "down" events, and both are
        optional.
        """

        return False

    def checks(self):
        return self.channel.project.check_set.order_by("created_at")


class Email(Transport):
    def notify(self, check, bounce_url):
        if not self.channel.email_verified:
            return "Email not verified"

        unsub_link = self.channel.get_unsub_link()

        headers = {
            "X-Bounce-Url": bounce_url,
            "List-Unsubscribe": "<%s>" % unsub_link,
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }

        try:
            # Look up the sorting preference for this email address
            p = Profile.objects.get(user__email=self.channel.email_value)
            sort = p.sort
        except Profile.DoesNotExist:
            # Default sort order is by check's creation time
            sort = "created"

        # list() executes the query, to avoid DB access while
        # rendering a template
        context = {
            "check": check,
            "checks": list(self.checks()),
            "sort": sort,
            "now": timezone.now(),
            "unsub_link": unsub_link,
        }

        em().alert(self.channel.email_value, context, headers)

    def is_noop(self, check):
        if check.status == Status.down.name:
            return not self.channel.email_notify_down
        else:
            return not self.channel.email_notify_up


class Shell(Transport):
    def prepare(self, template, check):

        context = {
            "$CODE": str(check.code),
            "$STATUS": check.status,
            "$NOW": timezone.now().replace(microsecond=0).isoformat(),
            "$NAME": check.name,
            "$TAGS": check.tags,
        }

        for i, tag in enumerate(check.tags_list()):
            context["$TAG%d" % (i + 1)] = tag

        return replace(template, context)

    def is_noop(self, check):
        if check.status == Status.down.name and not self.channel.cmd_down:
            return True

        if check.status == Status.up.name and not self.channel.cmd_up:
            return True

        return False

    def notify(self, check):
        if check.status == Status.up.name:
            cmd = self.channel.cmd_up
        elif check.status == Status.down.name:
            cmd = self.channel.cmd_down

        cmd = self.prepare(cmd, check)
        code = os.system(cmd)

        if code != 0:
            return "Command returned exit code %d" % code


class Http(Transport):
    @classmethod
    def get_error(cls, response):
        return response

    @classmethod
    def _request(cls, method, url, **kwargs):
        try:
            options = dict(kwargs)
            options["timeout"] = 5
            if "headers" not in options:
                options["headers"] = {}
            if "User-Agent" not in options["headers"]:
                options["headers"]["User-Agent"] = Site.objects.first().name

            r = requests.request(method, url, **options)
            if r.status_code not in (200, 201, 202, 204):
                m = cls.get_error(r)
                if m:
                    return f'Received status code {r.status_code} with a message: "{m}"'

                return f"Received status code {r.status_code}"

        except requests.exceptions.Timeout:
            return "Connection timed out"
        except requests.exceptions.ConnectionError:
            return "Connection failed"

    @classmethod
    def get(cls, url, **kwargs):
        error = None
        # Make 3 attempts--
        for x in range(0, 3):
            error = cls._request("get", url, **kwargs)
            if error is None:
                break

        return error

    @classmethod
    def post(cls, url, **kwargs):
        error = None
        # Make 3 attempts--
        for x in range(0, 3):
            error = cls._request("post", url, **kwargs)
            if error is None:
                break

        return error

    @classmethod
    def put(cls, url, **kwargs):
        error = None
        # Make 3 attempts--
        for x in range(0, 3):
            error = cls._request("put", url, **kwargs)
            if error is None:
                break

        return error
