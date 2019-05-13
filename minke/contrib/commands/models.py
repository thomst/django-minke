# -*- coding: utf-8 -*-

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from minke.models import MinkeModel
from minke.models import MinkeSession
from minke.models import Host
from minke.utils import prepare_shell_command


def get_minketypes():
    minketype_ids = list()
    excludes = ('auth', 'contenttypes', 'sessions', 'commands')
    for ct in ContentType.objects.exclude(app_label__in=excludes):
        if issubclass(ct.model_class(), MinkeModel) or ct.model_class() is Host:
            minketype_ids.append(ct.id)
    return dict(id__in=minketype_ids)


class Command(models.Model):
    cmd = models.TextField()
    label = models.CharField(max_length=256)
    description = models.TextField(blank=True)
    minketypes = models.ManyToManyField(ContentType, limit_choices_to=get_minketypes)
    active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        self.cmd = prepare_shell_command(self.cmd)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.label


class CommandGroupManager(models.Manager):
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.prefetch_related('commands')


class CommandGroup(models.Model):
    objects = CommandGroupManager()
    label = models.CharField(max_length=256)
    description = models.TextField(blank=True)
    commands = models.ManyToManyField(Command, through='CommandOrder')
    minketypes = models.ManyToManyField(ContentType, limit_choices_to=get_minketypes)
    as_options = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    def get_commands(self):
        return Command.objects.filter(commands=self).order_by('commandorder__order')

    def __str__(self):
        return self.label


@receiver(pre_delete)
def delete_permission(sender, instance, **kwargs):
    if not sender in (Command, CommandGroup): return
    codename = 'run_%s_%d' % (sender.__name__.lower(), instance.id)
    Permission.objects.get(codename=codename).delete()


class CommandOrder(models.Model):
    command = models.ForeignKey(Command, on_delete=models.CASCADE)
    commands = models.ForeignKey(CommandGroup, on_delete=models.CASCADE)
    order = models.SmallIntegerField()

    class Meta:
        unique_together = ('commands', 'order')
        get_latest_by = 'order'

    def get_order(self):
        try:
            latest = CommandOrder.objects.filter(commands=self.commands).latest()
        except CommandOrder.DoesNotExist:
            return 1
        else:
            return latest.order + 1

    def save(self, *args, **kwargs):
        self.order = self.get_order()
        super().save(*args, **kwargs)
