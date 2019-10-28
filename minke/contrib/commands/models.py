# -*- coding: utf-8 -*-

from django.db import models
from django.db.models import Prefetch
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import pre_delete
from django.db.models.signals import post_save
from django.dispatch import receiver

from minke.models import MinkeModel
from minke.models import Host
from minke.utils import prepare_shell_command

from .sessions import BaseCommandSession
from .sessions import BaseCommandChoiceSession
from .sessions import BaseCommandChainSession


def get_minketypes():
    minketype_ids = list()
    excludes = ('auth', 'contenttypes', 'sessions', 'commands')
    for ct in ContentType.objects.exclude(app_label__in=excludes):
        if issubclass(ct.model_class(), MinkeModel) or ct.model_class() is Host:
            minketype_ids.append(ct.id)
    return dict(id__in=minketype_ids)


class CommandManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().prefetch_related('minketypes')


class CommandGroupManager(CommandManager):
    def get_queryset(self):
        cmd_qs = Command.objects.order_by('commandorder__order')
        prefetch = Prefetch('commands', queryset=cmd_qs)
        return super().get_queryset().prefetch_related(prefetch)


class BaseCommands(models.Model):
    class Meta:
        abstract = True

    label = models.CharField(max_length=256)
    description = models.TextField(blank=True)
    minketypes = models.ManyToManyField(ContentType, limit_choices_to=get_minketypes)
    active = models.BooleanField(default=True)

    def _get_session_attrs(self):
        attrs = dict()
        attrs['abstract'] = True
        attrs['model'] = self.__class__
        attrs['model_id'] = self.id
        attrs['verbose_name'] = self.label
        attrs['__doc__'] = self.description
        attrs['work_on'] = tuple((ct.model_class() for ct in self.minketypes.all()))
        return attrs

    def _get_session_class(self):
        return BaseCommandSession

    def _get_session_name(self):
        return '%s_%d' % (self.__class__.__name__, self.id)

    def as_session(self):
        name = self._get_session_name()
        attrs = self._get_session_attrs()
        baseclass = self._get_session_class()
        return type(name, (baseclass,), attrs)


class Command(BaseCommands):
    objects = CommandManager()
    cmd = models.TextField()

    def save(self, *args, **kwargs):
        self.cmd = prepare_shell_command(self.cmd)
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.label

    def _get_session_attrs(self):
        attrs = super()._get_session_attrs()
        attrs['command'] = self.cmd
        return attrs


class CommandGroup(BaseCommands):
    objects = CommandGroupManager()
    commands = models.ManyToManyField(Command, through='CommandOrder')
    as_options = models.BooleanField(default=False)

    def __str__(self):
        return self.label

    def _get_session_attrs(self):
        attrs = super()._get_session_attrs()
        if not self.as_options:
            attrs['commands'] = tuple(self.commands.all())
        return attrs

    def _get_session_class(self):
        if self.as_options:
            return BaseCommandChoiceSession
        else:
            return BaseCommandChainSession


@receiver(pre_delete)
def delete_permission(sender, instance, **kwargs):
    """
    Delete the run-session-permission.
    """
    if not sender in (Command, CommandGroup): return
    session = instance.as_session()
    session.delete_permission()


@receiver(post_save)
def create_permission(sender, instance, **kwargs):
    """
    Create the run-session-permission.
    """
    if not sender in (Command, CommandGroup): return
    session = instance.as_session()
    session.create_permission()


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
