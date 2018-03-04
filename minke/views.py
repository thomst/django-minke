# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import paramiko
from fabric.api import env

from django.shortcuts import render
from django.views.generic import View

from . import engine
from .forms import SSHKeyPassPhrase


class SessionView(View):

    def get_queryset(self, request):
        raise NotImplementedError('TODO: implement get_queryset...')

    def get_session_cls(self):
        raise NotImplementedError('TODO: implement get_session_cls...')

    def post(self, request, session_cls=None, queryset=None):

        session_cls = session_cls or self.get_sesssion_class()
        queryset = queryset or self.get_queryset(request)

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
                    'action': session_cls.__name__,
                    'objects': queryset,
                    'form': form})

        # hopefully we are prepared...
        engine.process(request, session_cls, queryset)
