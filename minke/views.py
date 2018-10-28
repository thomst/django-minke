# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import paramiko
from fabric.api import env

from django.conf import settings
from django.shortcuts import render
from django.views.generic import View
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.contenttypes.models import ContentType

from minke import engine
from .forms import MinkeForm
from .forms import InitialPasswordForm
from .models import BaseSession


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
        self.queryset = self.kwargs.get('queryset', None)
        if self.queryset is not None:
            return self.queryset
        else:
            raise AttributeError('Missing queryset!')

    def get_session_cls(self):
        self.session_cls = self.kwargs.get('session_cls', None)
        if self.session_cls:
            return self.session_cls
        else:
            raise AttributeError('Missing session-class!')

    def post(self, request, *args, **kwargs):
        session_cls = self.get_session_cls()
        queryset = self.get_queryset()

        password_form = getattr(settings, 'MINKE_INITIAL_PASSWORD_FORM', None)
        session_form = bool(session_cls.FORM) or None
        confirm = session_cls.CONFIRM
        session_data = dict()

        # do we have to render a form?
        if password_form or session_form or confirm:
            minke_form = MinkeForm(dict(action=session_cls.__name__))

            from_form = request.POST.get('minke_form', False)
            if password_form:
                if from_form: password_form = InitialPasswordForm(request.POST)
                else: password_form = InitialPasswordForm()

            if session_form:
                if from_form: session_form = session_cls.FORM(request.POST)
                else: session_form = session_cls.FORM()

            valid = minke_form.is_valid()
            valid &= not password_form or password_form.is_valid()
            valid &= not session_form or session_form.is_valid()

            params = dict(
                title=session_cls.short_description,
                minke_form=minke_form,
                password_form=password_form,
                session_form=session_form,
                objects=queryset,
                object_list=confirm
            )

            if not valid or not from_form:
                return render(request, 'minke/minke_form.html', params)

            if password_form:
                env.password = password_form.cleaned_data['initial_password']

            if session_form:
                session_data = session_form.cleaned_data


        # do we have a chance to get keys from an ssh-agent?
        if not env.no_agent:
            from paramiko.agent import Agent
            env.no_agent = not bool(Agent().get_keys())

        # do we have any option to get a key at all?
        if env.no_agent and not env.key and not env.key_filename:
            msg = 'Got no keys from the agent nor have a key-file!'
            messages.add_message(request, messages.ERROR, msg)
            return

        # clear current-messages for this model
        BaseSession.objects.clear_currents(request.user, queryset)
        # content_type = ContentType.objects.get_for_model(queryset.model)
        # BaseSession.objects.filter(
        #     user=request.user,
        #     content_type=content_type,
        #     object_id__in=queryset.all().values('id'),
        #     current=True
        #     ).update(current=False)

        # hopefully we are prepared...
        engine.process(session_cls, queryset, session_data, request.user)
