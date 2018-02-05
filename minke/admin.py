# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from django.contrib import admin

from engine import registry
from engine import Action
from messages import clear_msgs


class MinkeAdmin(admin.ModelAdmin):

    def get_actions(self, request):
        actions = super(MinkeAdmin, self).get_actions(request)
        sessions = [s for s in registry if self.model in s.models]
        minke_actions = [Action(s) for s in sessions]

        if minke_actions:
            try: assert request.session['minke'][self.model.__name__]
            except (AssertionError, KeyError): pass
            else: minke_actions.append(clear_msgs)

        for action in minke_actions:
            actions[action.__name__] = (
                action,
                action.__name__,
                action.short_description)

        return actions
