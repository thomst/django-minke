# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType

from .sessions import registry
from .actions import clear_news
from .models import BaseSession


class MinkeAdmin(admin.ModelAdmin):

    def get_actions(self, request):
        actions = super(MinkeAdmin, self).get_actions(request)
        prep_action = lambda a: (a, a.__name__, a.short_description)

        # # add clear-news if there are any minke-news for this model...
        content_type = ContentType.objects.get_for_model(self.model)
        sessions = BaseSession.objects.filter(
            user=request.user,
            content_type=content_type,
            current=True)
        if sessions:
            actions[clear_news.__name__] = prep_action(clear_news)

        # messenger = Messenger(request)
        # data = messenger.get(self.model)
        # if data:
        #     actions[clear_news.__name__] = prep_action(clear_news)

        # add sessions depending on the model and the user-perms...
        for session in registry:
            if not self.model in session.models:
                continue
            if not request.user.has_perms(session.permission_required):
                continue
            action = session.as_action()
            actions[action.__name__] = prep_action(action)

        return actions
