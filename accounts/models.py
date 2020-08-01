from django.db import models
from django.contrib.auth.models import User
from uuid import uuid4
from django.db.models import Q


# Create your models here.
class ProfileManager(models.Manager):
    def for_user(self, user):
        try:
            return user.profile
        except Profile.DoesNotExist:
            profile = Profile(user=user)
            profile.save()
            return profile


class Profile(models.Model):
    user = models.OneToOneField(to=User, on_delete=models.CASCADE)
    timezone = models.CharField(max_length=254, default="UTC")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    object = ProfileManager()

    class Meta:
        verbose_name = "Profile"
        verbose_name_plural = "Profiles"

    def __str__(self):
        return self.user.username

    def projects(self):
        return Project.objects.filter(Q(owner=self) | Q(projectmember__user=self)).distinct().order_by("name")


class Project(models.Model):
    code = models.UUIDField(default=uuid4, unique=True)
    name = models.CharField(max_length=254, blank=True)
    owner = models.ForeignKey(to=Profile, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Project"
        verbose_name_plural = "Projects"

    def __str__(self):
        return self.name or self.owner.user.username

    @property
    def owner_profile(self):
        return Profile.objects.for_user(self.owner)

    def team(self):
        return Profile.objects.filter(projectmember__project=self)


class ProjectMember(models.Model):
    user = models.ForeignKey(to=Profile, on_delete=models.CASCADE)
    project = models.ForeignKey(to=Project, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Member"
        verbose_name_plural = "Members"

    def __str__(self):
        return "{}:{}".format(self.project, self.user)
