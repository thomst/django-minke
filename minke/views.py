# -*- coding: utf-8 -*-

from pydoc import locate

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
from .models import MinkeSession
from .serializers import SessionSerializer
from .exceptions import InvalidURLQuery
from .exceptions import InvalidMinkeSetup


class SessionView(PermissionRequiredMixin, View):

    raise_exception = True
    permission_denied_message = 'You are not allowed to run {}!'

    def get_permission_denied_message(self):
        session_cls = self.get_session_cls()
        msg = self.permission_denied_message.format(session_cls.__name__)
        return msg

    def get_permission_required(self):
        session_cls = self.get_session_cls()
        return session_cls.PERMISSIONS

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
        wait = session_cls.WAIT
        fabric_config = None
        session_data = dict()
        confirm = session_cls.CONFIRM
        session_form_cls = session_cls.get_form()
        fabric_form_cls = None
        render_params = dict()

        # import fabric-form if needed...
        if settings.MINKE_FABRIC_FORM:
            fabric_form_cls = locate(settings.MINKE_FABRIC_FORM)
            if not fabric_form_cls:
                msg = '{} could not be loaded'.format(settings.MINKE_FABRIC_FORM)
                raise InvalidMinkeSetup(msg)

        # do we have to work with a form?
        if confirm or fabric_form_cls or session_form_cls:

            # first time or validation?
            from_form = request.POST.get('minke_form', False)
            if from_form:
                minke_form = MinkeForm(request.POST)
                valid = minke_form.is_valid()
                form_data = [request.POST]
            else:
                minke_form = MinkeForm(dict(
                    action=session_cls.__name__,
                    wait=session_cls.WAIT))
                valid = False
                form_data = list()

            # initiate fabric-form
            if fabric_form_cls:
                fabric_form = fabric_form_cls(*form_data)
                render_params['fabric_form'] = fabric_form
                valid &= fabric_form.is_valid()

            # initiate session-form
            if session_form_cls:
                session_form = session_cls.FORM(*form_data)
                render_params['session_form'] = session_form
                valid &= session_form.is_valid()

            # render minke-form the first time or if form-data where not valid...
            if not valid:
                render_params['title'] = session_cls.VERBOSE_NAME,
                render_params['minke_form'] = minke_form
                render_params['objects'] = queryset
                render_params['object_list'] = confirm
                return render(request, 'minke/minke_form.html', render_params)

            # get fabric-config from fabric-form...
            if fabric_form_cls:
                fabric_config = fabric_form.cleaned_data

            # get session-data from session-form...
            if session_form_cls:
                session_data = session_form.cleaned_data

            # update wait-param from minke-form...
            wait = minke_form.cleaned_data['wait']

        # lets rock...
        engine.process(session_cls, queryset, session_data, request.user,
                       fabric_config=fabric_config, wait=wait)


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

        return MinkeSession.objects.filter(
            minkeobj_id__in=object_ids,
            minkeobj_type=content_type,
            user=self.request.user,
            current=True
            ).prefetch_related('messages')
