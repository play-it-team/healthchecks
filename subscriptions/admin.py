from django.contrib import admin
from subscriptions.models import Subscription, Plan
from django.urls import reverse
from django.utils.safestring import mark_safe
from accounts.models import Profile


# Register your models here.
@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "sku"
    )


@admin.register(Subscription)
class SubsAdmin(admin.ModelAdmin):
    readonly_fields = ("email",)
    search_fields = (
        "customer_id",
        "payment_method_token",
        "subscription_id",
        "profile__user__email",
    )
    list_display = (
        "id",
        "email",
        "customer_id",
        "address_id",
        "payment_method_token",
        "subscription_id",
        "profile",
    )

    list_filter = ("plan",)
    raw_id_fields = ("profile",)
    actions = ("cancel",)

    def email(self, obj):
        return obj.profile.user.email if obj.profile.user else None

    def cancel(self, request, qs):
        for sub in qs.all():
            sub.cancel()

            profile = Profile.objects.for_user(sub.user)
            profile.save()

        self.message_user(request, "%d subscriptions cancelled" % qs.count())
