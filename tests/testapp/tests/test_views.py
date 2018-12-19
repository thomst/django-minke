# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.auth.models import User
from django.test import TransactionTestCase
from django.test import Client

from minke import sessions
from minke.models import BaseSession
from ..sessions import LeaveAMessageSession
from ..models import Host, Server, AnySystem
from .utils import create_test_data


class ViewsTest(TransactionTestCase):
    def setUp(self):
        create_test_data()

    def test_01_session_view(self):
        models = [Host, Server, AnySystem]
        admin = User.objects.get(username='admin')
        anyuser = User.objects.get(username='anyuser')
        player_ids = [1, 2, 3]
        post_data = dict(action='LeaveAMessageSession', _selected_action=player_ids)
        baseurl = '/admin/{}/{}/'

        # work with admin-user
        self.client.force_login(admin)

        # valid action-requests for Host, Server and AnySystem
        # also check the current-sessions that were created
        for model in models:
            url = baseurl.format(model._meta.app_label, model._meta.model_name)
            resp = self.client.post(url, post_data, follow=True)
            self.assertEqual(resp.redirect_chain[0][0], url)
            self.assertEqual(resp.status_code, 200)
            self.assertIn(LeaveAMessageSession.MSG, resp.content.decode('utf8'))
            user = resp.context['user']
            current_sessions = BaseSession.objects.get_currents_by_model(user, model)
            object_ids = list(current_sessions.values_list('object_id', flat=True))
            self.assertEqual(sorted(object_ids), sorted(player_ids))
        else:
            self.client.logout()

        # TODO: Find a way to check 403-response when calling SessionView
        # without proper session-permissions. Right now we only get a
        # 'No action selected'-message.
        # work with unprivileged user
        url = '/admin/minke/host/'
        self.client.force_login(anyuser)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('DummySession', resp.content)
        self.assertNotIn('LeaveAMessageSession', resp.content)

        # If user lacks permissions to run a session, the session won't be
        # listed as action-option. The response is a changelist with a
        # 'No action selected'-message instead of a 403.
        resp = self.client.post(url, post_data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('No action selected', resp.content)

        # call DummySession should not be a problem - there are no permissions
        post_data['action'] = 'DummySession'
        resp = self.client.post(url, post_data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('No action selected', resp.content)

    def test_02_session_api(self):
        pass
