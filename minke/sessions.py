# -*- coding: utf-8 -*-

import re

from fabric.api import run

from django.core.exceptions import FieldDoesNotExist
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.utils.text import camel_case_to_spaces, slugify

from .views import SessionView
from .models import Host
from .messages import ExecutionMessage


registry = list()
def register(session_cls, models=None,
             short_description=None,
             permission_required=None,
             create_permission=False):
    """Register session-classes.
    They will be provided as admin-actions for the specified models"""

    if models:
        if not type(models) == tuple:
            models = (models,)
        session_cls.models = session_cls.models + models

    if permission_required:
        if not type(permission_required) == tuple:
            permission_required = (permission_required,)
        session_cls.permission_required = \
            session_cls.permission_required + permission_required

    if short_description:
        session_cls.short_description = short_description

    if not issubclass(session_cls, Session):
        raise ValueError('Registered class must subclass Session.')

    if not session_cls.models:
        raise ValueError('At least one model must be specified for a session.')

    for model in session_cls.models:
        try:
            assert model == Host or model._meta.get_field('host').rel.to == Host
        except (AssertionError, FieldDoesNotExist):
            raise ValueError('Sessions could only be used with Host '
                             'or a model with a relation to Host.')

    if create_permission:
        # We only create a permission for one model. Otherwise a user would
        # must have all permissions for all session-models and not as expected
        # only the permission for the model she wants to run the session with.
        model = session_cls.models[0]
        # FIXME: Applying minke-migrations before the migrations of registered
        # models will fail at this line...
        content_type = ContentType.objects.get_for_model(session_cls.models[0])
        model_name = slugify(model.__name__)
        session_name = session_cls.__name__
        session_codename = camel_case_to_spaces(session_name).replace(' ', '_')
        codename = 'run_{}_on_{}'.format(session_codename, model_name)
        permission_name = '{}.{}'.format(model._meta.app_label, codename)

        # create permission...
        permission = Permission.objects.get_or_create(
            name='Can run {}'.format(session_name),
            codename=codename,
            content_type=content_type)

        # add permission to permission_required...
        session_cls.permission_required += (permission_name,)

    registry.append(session_cls)


class BaseSession(object):
    """Implement the base-functionality of a session-class."""

    SUCCESS = 'success'
    WARNING = 'warning'
    ERROR = 'error'

    def __init__(self, host, player):
        self.host = host
        self.player = player
        self.news = list()
        self.status = self.SUCCESS

    def set_status(self, status):
        try: status = getattr(self, status)
        except AttributeError: pass

        if status in (self.SUCCESS, self.WARNING, self.ERROR):
            self.status = status
        else:
            raise ValueError('Invalid session-status: {}'.format(status))

    def process(self):
        """Real work is done here...

        This is the part of a session which is executed within fabric's
        multiprocessing-szenario. It's the right place for all
        fabric-operations. But keep it clean of database-related stuff.
        Database-connections are multiplied with spawend processes and
        then are not reliable anymore.
        """
        raise NotImplementedError('Your session must define a process-method!')

    def rework(self):
        """This method is called after fabric's work is done.
        Database-related actions should be done here."""
        pass


class AdminSession(BaseSession):
    """Implement attributes for admin-site-integration."""

    models = tuple()
    short_description = None
    permission_required = tuple()

    @classmethod
    def as_action(cls):
        def action(modeladmin, request, queryset):
            session_view = SessionView.as_view()
            return session_view(request, session_cls=cls, queryset=queryset)
        action.__name__ = cls.__name__
        action.short_description = cls.short_description
        return action


class Session(AdminSession):

    def format_cmd(self, cmd):
        return cmd.format(**vars(self.player))

    def validate(self, result, regex=None):
        if regex and result.return_code == 0:
            return re.match(regex, result.stdout)
        else:
            return result.return_code == 0

    def message(self, cmd, **kwargs):
        result = run(cmd, **kwargs)
        valid = self.validate(result)

        if not valid: level = 'ERROR'
        elif result.stderr: level = 'WARNING'
        else: level = 'INFO'

        self.news.append(ExecutionMessage(result, level))

        return valid


class UpdateEntriesSession(Session):

    def update_field(self, field, cmd, regex='(.*)'):
        try: getattr(self.player, field)
        except AttributeError as e: raise e

        result = run(cmd)
        valid = self.validate(result, regex)

        if valid and result.stdout:
            try: value = re.match(regex, result.stdout).groups()[0]
            except IndexError: value = result.stdout
        else:
            value = None

        if not value:
            self.news.append(ExecutionMessage(result, 'ERROR'))

        setattr(self.player, field, value)
        return bool(value)

    def rework(self):
        self.player.save()
