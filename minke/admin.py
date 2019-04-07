# -*- coding: utf-8 -*-

from django.contrib.admin.views.main import ChangeList
from django.urls import reverse
from django.contrib import admin

from .actions import clear_news
from .models import MinkeSession
from .utils import item_by_attr


class MinkeChangeList(ChangeList):
    def __init__(self, request, modeladmin, *args, **kwargs):
        super(MinkeChangeList, self).__init__(request, modeladmin, *args, **kwargs)
        sessions = MinkeSession.objects.get_currents(request.user, self.result_list)
        sessions = list(sessions.prefetch_related('messages'))
        minke_sessions = list()
        for obj in self.result_list:
            session = item_by_attr(sessions, 'minkeobj_id', obj.id)
            if session: minke_sessions.append(session)
            else: minke_sessions.append(None)
        self.minke_sessions = minke_sessions


class MinkeAdmin(admin.ModelAdmin):

    def get_actions(self, request):
        actions = super(MinkeAdmin, self).get_actions(request)
        prep_action = lambda a: (a, a.__name__, a.short_description)

        # add clear-news if there are any minke-news for this model...
        sessions = MinkeSession.objects.get_currents_by_model(request.user, self.model)
        if sessions:
            actions[clear_news.__name__] = prep_action(clear_news)

        # add sessions depending on the model and the user-perms...
        for session in MinkeSession.REGISTRY.values():
            if (self.model in session.WORK_ON and
                request.user.has_perms(session.PERMISSIONS)):
                action = session.as_action()
                actions[action.__name__] = prep_action(action)

        return actions

    def get_changelist(self, request, **kwargs):
        return MinkeChangeList
