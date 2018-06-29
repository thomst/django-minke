# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import paramiko
from fabric.api import env

from django.conf import settings
from django.shortcuts import render
from django.views.generic import View
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin

from minke import engine
from .forms import InitialPasswordForm
from .messages import Messenger


class SessionView(PermissionRequiredMixin, View):

    raise_exception = True
    permission_denied_message = 'You are not allowed to run {}!'

    def get_permission_denied_message(self):
        session_cls = self.get_session_cls()
        msg = self.permission_denied_message.format(session_cls.__name__)
        return msg

    def get_permission_required(self):
        session_cls = self.get_session_cls()
        self.permission_required = session_cls.permission_required
        return super(SessionView, self).get_permission_required()

    def get_queryset(self):
        if self.kwargs.get('queryset', None):
            self.queryset = self.kwargs['queryset']

        if hasattr(self, 'queryset'):
            return self.queryset
        else:
            raise AttributeError('Missing queryset!')

    def get_session_cls(self):
        if self.kwargs.get('session_cls', None):
            self.session_cls = self.kwargs['session_cls']

        if hasattr(self, 'session_cls'):
            return self.session_cls
        else:
            raise AttributeError('Missing session-class!')

    def post(self, request, *args, **kwargs):
        session_cls = self.get_session_cls()
        queryset = self.get_queryset()

        # Render initial-password-form...
        if getattr(settings, 'MINKE_INITIAL_PASSWORD_FORM', False):
            if request.POST.has_key('minke_initial_password'):
                form = InitialPasswordForm(request.POST)
            else:
                form = InitialPasswordForm()

            if form.is_valid():
                env.password = request.POST['minke_initial_password']
            else:
                return render(request, 'minke/ssh_private_key_form.html',
                    {'title': u'Initial password used by fabric.',
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

        # initiate the messenger and clear already stored messages for this model
        messenger = Messenger(request)
        messenger.remove(queryset.model)

        # hopefully we are prepared...
        engine.process(session_cls, queryset, messenger)
