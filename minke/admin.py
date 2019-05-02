# -*- coding: utf-8 -*-

from django.contrib.admin.views.main import ChangeList
from django.urls import reverse
from django.contrib import admin

from .actions import clear_news
from .models import MinkeSession


class MinkeAdmin(admin.ModelAdmin):
    change_list_template = 'minke/change_list.html'

    def get_actions(self, request):
        actions = super().get_actions(request)
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
