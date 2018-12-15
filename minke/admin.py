# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.admin.views.main import ChangeList
from django.core.urlresolvers import reverse
from django.contrib import admin

from .sessions import registry
from .actions import clear_news
from .models import BaseSession
from .views import MessageView
from .utils import item_by_attr


class MinkeChangeList(ChangeList):
    def __init__(self, request, modeladmin, *args, **kwargs):
        super(MinkeChangeList, self).__init__(request, modeladmin, *args, **kwargs)
        sessions = BaseSession.objects.get_currents(request.user, self.result_list)
        sessions = list(sessions.prefetch_related('messages'))
        minke_sessions = list()
        for obj in self.result_list:
            session = item_by_attr(sessions, 'object_id', obj.id)
            if session: minke_sessions.append(session)
            else: minke_sessions.append(None)
        self.minke_sessions = minke_sessions


class MinkeAdmin(admin.ModelAdmin):

    def get_actions(self, request):
        actions = super(MinkeAdmin, self).get_actions(request)
        prep_action = lambda a: (a, a.__name__, a.short_description)

        # add clear-news if there are any minke-news for this model...
        sessions = BaseSession.objects.get_currents_by_model(request.user, self.model)
        if sessions:
            actions[clear_news.__name__] = prep_action(clear_news)

        # add sessions depending on the model and the user-perms...
        for session in registry:
            if not self.model in session.models:
                continue
            if not request.user.has_perms(session.permission_required):
                continue
            action = session.as_action()
            actions[action.__name__] = prep_action(action)

        return actions

    def get_changelist(self, request, **kwargs):
        return MinkeChangeList
