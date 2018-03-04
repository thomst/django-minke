# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from django.contrib import admin

from .sessions import registry
from .actions import clear_news
from .messages import Messenger


class MinkeAdmin(admin.ModelAdmin):

    def get_actions(self, request):
        actions = super(MinkeAdmin, self).get_actions(request)
        minke_actions = [s.as_action() for s in registry if self.model in s.action_models]

        messenger = Messenger(request)
        data = messenger.get(self.model)
        if data: minke_actions.append(clear_news)

        for action in minke_actions:
            actions[action.__name__] = (
                action,
                action.__name__,
                action.short_description)

        return actions
