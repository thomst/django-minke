# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import paramiko
from fabric.api import env

from django.shortcuts import render
from django.views.generic import View
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse

from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound

from minke import settings
from minke import engine
from .forms import MinkeForm
from .forms import PasswordForm
from .models import BaseSession
from .serializers import SessionSerializer
from .exceptions import InvalidURLQuery


class SessionView(PermissionRequiredMixin, View):

    raise_exception = True
    permission_denied_message = 'You are not allowed to run {}!'

    def get_permission_denied_message(self):
        session_cls = self.get_session_cls()
        msg = self.permission_denied_message.format(session_cls.__name__)
        return msg

    def get_permission_required(self):
        session_cls = self.get_session_cls()
        return session_cls.permission_required

    def get_queryset(self):
        queryset = self.kwargs.get('queryset', None)
        if queryset is not None: return queryset
        else: raise AttributeError('Missing queryset!')

    def get_session_cls(self):
        session_cls = self.kwargs.get('session_cls', None)
        if session_cls: return session_cls
        else: raise AttributeError('Missing session-class!')

    def post(self, request, *args, **kwargs):
        session_cls = self.get_session_cls()
        queryset = self.get_queryset()
        join = session_cls.JOIN

        # do we have to render a form?
        password_form = settings.MINKE_PASSWORD_FORM
        session_form = bool(session_cls.FORM)
        confirm = session_cls.CONFIRM
        session_data = dict()

        if password_form or session_form or confirm:
            from_form = request.POST.get('minke_form', False)

            if from_form:
                minke_form = MinkeForm(request.POST)
                if password_form: password_form = PasswordForm(request.POST)
                if session_form: session_form = session_cls.FORM(request.POST)
            else:
                minke_form = MinkeForm(dict(action=session_cls.__name__, join=session_cls.JOIN))
                if password_form: password_form = PasswordForm()
                if session_form: session_form = session_cls.FORM()

            valid = minke_form.is_valid()
            if password_form: valid &= password_form.is_valid()
            if session_form: valid &= session_form.is_valid()

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
            else:
                join = minke_form.cleaned_data['join']

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

        # hopefully we are prepared...
        engine.process(session_cls, queryset, session_data, request.user, join, request)


class SessionAPI(ListAPIView):
    """
    API endpoint to retrieve current sessions.
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = SessionSerializer

    def get_queryset(self):
        try:
            object_ids = self.request.GET['object_ids'].split(',')
            object_ids = [int(id) for id in object_ids]
        except KeyError:
            object_ids = list()
        except ValueError:
            msg = 'Object_ids must be a list of integers.'
            raise InvalidURLQuery(msg)

        try:
            model = self.kwargs['model']
            content_type = ContentType.objects.get(model=model)
        except ContentType.DoesNotExist:
            raise NotFound("There is no model named '{}'".format(model))

        return BaseSession.objects.filter(
            object_id__in=object_ids,
            content_type=content_type,
            user=self.request.user,
            current=True
            ).prefetch_related('messages')
