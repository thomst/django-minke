# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import paramiko
from fabric.api import env

from django.conf import settings
from django.shortcuts import render
from django.views.generic import View
from django.contrib import messages

from minke import engine
from .forms import InitialPasswordForm


class SessionView(View):

    def get_queryset(self, request):
        raise NotImplementedError('TODO: implement get_queryset...')

    def get_session_cls(self, request):
        raise NotImplementedError('TODO: implement get_session_cls...')

    def post(self, request, *args, **kwargs):
        session_cls = self.get_sesssion_class(request)
        queryset = self.get_queryset(request)
        return self.process(self, request, session_cls, queryset)

    def process(self, request, session_cls, queryset):
        """Try to prepare fabric for key-authentication..."""

        if getattr(settings, 'MINKE_INITIAL_PASSWORD_FORM', False):
            if request.POST.has_key('minke_initial_password'):
                form = InitialPasswordForm(request.POST)
            else:
                form = InitialPasswordForm()

            if form.is_valid():
                env.password = request.POST['minke_initial_password']
            else:
                return render(request, 'minke/ssh_private_key_form.html',
                    {'title': u'Pass the pass-phrase to encrypt the ssh-key.',
                    'action': session_cls.__name__,
                    'objects': queryset,
                    'form': form})

        # do we have a chance to get keys from an ssh-agent?
        if not env.no_agent:
            from paramiko.agent import Agent
            env.no_agent = not bool(Agent().get_keys())

        # do we have any option to get a key at all?
        if env.no_agent and not env.key and not env.key_filename:
            msg = 'Got no keys from the agent nor have a key-file!'
            messages.add_message(request, messages.ERROR, msg)
            return

        # hopefully we are prepared...
        engine.process(request, session_cls, queryset)
