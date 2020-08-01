from threading import Thread

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


class EmailBase(Thread):
    def __init__(self, subject, text, html, to, headers):
        Thread.__init__(self)
        self.subject = subject
        self.text = text
        self.html = html
        self.to = to
        self.headers = headers

    def run(self):
        msg = EmailMultiAlternatives(
            self.subject, self.text, to=(self.to,), headers=self.headers
        )

        msg.attach_alternative(self.html, "text/html")
        msg.send()


class Email(object):
    @staticmethod
    def _send(name, to, context, headers=None):
        subject = render_to_string("notifications/%s-subject.html" % name, context).strip()
        text = render_to_string("notifications/%s-body-text.html" % name, context)
        html = render_to_string("notifications/%s-body-html.html" % name, context)

        t = EmailBase(subject, text, html, to, headers)
        t.start()

    def alert(self, to, context, headers=None):
        self._send("alert", to, context, headers)
