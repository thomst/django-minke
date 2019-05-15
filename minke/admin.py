# -*- coding: utf-8 -*-

from django.contrib.admin.views.main import ChangeList
from django.urls import reverse
from django.contrib import admin

from .actions import clear_news
from .models import MinkeSession
from .sessions import REGISTRY


class MinkeAdmin(admin.ModelAdmin):
    change_list_template = 'minke/change_list.html'

    def get_actions(self, request):
        # TODO: This method is called three times for each request.
        # Since we access db-data it would be nice to implement a cache,
        # that could be dispatched as long as the request-obj is the same.
        actions = super().get_actions(request)
        prepare = lambda a: (a, a.__name__, a.short_description)

        # add clear-news if there are any minke-news for this model...
        sessions = MinkeSession.objects.get_currents_by_model(request.user, self.model)
        if sessions:
            actions[clear_news.__name__] = prepare(clear_news)

        # add sessions depending on the model and the user-perms...
        REGISTRY.reload()
        for session in REGISTRY.values():
            if not request.user.has_perms(session.permissions): continue
            if not self.model in session.work_on: continue
            actions[session.__name__] = prepare(session.as_action())

        return actions
