# -*- coding: utf-8 -*-

import paramiko

from django.shortcuts import render
from django.core.exceptions import FieldDoesNotExist

from fabric.api import env

from .messages import Messenger
from .models import Host
from .engine import Session
from .engine import process
from .forms import SSHKeyPassPhrase


def clear_news(modeladmin, request, queryset):
    messenger = Messenger(request)
    messenger.remove(objects=queryset)
clear_news.short_description = 'Clear minke-news'


registry = list()
def register(session_cls, models=None, short_description=None):
    """Register sessions to use them as an admin-action for all models passed
    as parameter or defined as the session's action_models.
    """

    if models:
        if not type(models) == list: models = [models]
        session_cls.action_models = models

    if short_description:
        session_cls.action_description = short_description

    if not issubclass(session_cls, Session):
        raise ValueError('Registered class must subclass Session.')

    if not session_cls.action_models:
        raise ValueError('At least one model must be specified for a session.')

    for model in session_cls.action_models:
        try:
            assert model == Host or model._meta.get_field('host').rel.to == Host
        except (AssertionError, FieldDoesNotExist):
            raise ValueError('Sessions could only be used with Host '
                             'or a model with a relation to Host.')

    registry.append(session_cls)


class Action(object):
    """
    Action should be initialized with a session-class and could be then used as
    an admin-action.
    """
    def __init__(self, session_cls):
        self.session_cls = session_cls
        self.__name__ = session_cls.__name__
        self.short_description = session_cls.action_description or self.__name__

    def __call__(self, modeladmin, request, queryset):

        # Be sure that the config is sufficient to give fabric
        # a chance for key-authentications.

        # do we get keys via an agent?
        agent_works = False
        if not env.no_agent:
            from paramiko.agent import Agent
            agent = Agent()
            agent_works = agent.get_keys()

        # do we have any option to get a key at all?
        if not agent_works and not env.key and not env.key_filename:
            #TODO: error-msg and redirect
            return

        # no agent-keys or env.key?
        # we will probably need a passphrase...
        elif not agent_works and not env.key:
            if request.POST.has_key('pass_phrase'):
                form = SSHKeyPassPhrase(request.POST)
            else:
                form = SSHKeyPassPhrase()
            if form.is_valid():
                env.password = request.POST.get('pass_phrase', None)
            else:
                return render(request, 'minke/ssh_private_key_form.html',
                    {'title': u'Pass the pass-phrase to encrypt the ssh-key.',
                    'action': self.__name__,
                    'objects': queryset,
                    'form': form})

        # hopefully we are prepared...
        process(request, self.session_cls, queryset)
