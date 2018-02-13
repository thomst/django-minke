# -*- coding: utf-8 -*-

import paramiko

from django.shortcuts import render
from fabric.api import env
from .messages import clear_msgs
from .engine import process
from .forms import SSHKeyPassPhrase


def clear_messages(modeladmin, request, queryset):
    clear_msgs(request, modeladmin.model, queryset)
clear_messages.short_description = 'Clear minke-messages'


class Action(object):
    """
    Action should be initialized with a session-class and could be then used as
    an admin-action.
    """
    def __init__(self, session_cls):
        self.session_cls = session_cls
        self.__name__ = session_cls.__name__
        self.short_description = session_cls.short_description or self.__name__

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
        process(request, self.session_cls, queryset, modeladmin)
