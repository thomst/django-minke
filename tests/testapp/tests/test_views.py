# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TransactionTestCase
from django.test import Client
from django.urls import reverse

from minke import sessions
from minke import settings
from minke.models import BaseSession
from minke.models import BaseMessage
from ..sessions import LeaveAMessageSession
from ..sessions import DummySession
from ..sessions import ExceptionSession
from ..models import Host, Server, AnySystem
from ..forms import TestForm
from .utils import create_test_data


class ViewsTest(TransactionTestCase):
    def setUp(self):
        create_test_data()
        self.admin = User.objects.get(username='admin')
        self.anyuser = User.objects.get(username='anyuser')

    def test_01_session_view(self):
        url_pattern = 'admin:{}_{}_changelist'
        player_ids = [1, 2, 3]
        post_data = dict(
            action=LeaveAMessageSession.__name__,
            _selected_action=player_ids)

        # work with admin-user
        self.client.force_login(self.admin)

        # valid action-requests for Host, Server and AnySystem
        # also check the current-sessions that were created
        for model in [Host, Server, AnySystem]:
            url = reverse(url_pattern.format(model._meta.app_label, model._meta.model_name))
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
        url = reverse('admin:minke_host_changelist')
        self.client.force_login(self.anyuser)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(DummySession.__name__, resp.content)
        self.assertNotIn('LeaveAMessageSession', resp.content)

        # If user lacks permissions to run a session, the session won't be
        # listed as action-option. The response is a changelist with a
        # 'No action selected'-message instead of a 403.
        resp = self.client.post(url, post_data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('No action selected', resp.content)

        # call DummySession should not be a problem - there are no permissions
        post_data['action'] = DummySession.__name__
        resp = self.client.post(url, post_data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('No action selected', resp.content)

        # Exceptions within session-code:
        old_minke_debug = settings.MINKE_DEBUG
        post_data['action'] = ExceptionSession.__name__

        settings.MINKE_DEBUG = True
        resp = self.client.post(url, post_data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(ExceptionSession.ERR_MSG, resp.content)

        settings.MINKE_DEBUG = False
        resp = self.client.post(url, post_data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('An error occurred', resp.content)

        settings.MINKE_DEBUG = old_minke_debug

    def test_02_session_form(self):
        url = reverse('admin:testapp_anysystem_changelist')
        post_data = dict()
        post_data['action'] = DummySession.__name__
        post_data['_selected_action'] = [1]
        invalid_form_data = post_data.copy()
        invalid_form_data['minke_form'] = True
        invalid_form_data['initial_password'] = ''
        invalid_form_data['one'] = 'abc'
        invalid_form_data['two'] = 'def'
        valid_form_data = post_data.copy()
        valid_form_data['minke_form'] = True
        valid_form_data['initial_password'] = 'password'
        valid_form_data['one'] = 1
        valid_form_data['two'] = 2

        self.client.force_login(self.admin)
        old_minke_password_form = settings.MINKE_PASSWORD_FORM
        indicator_action_form = '<input type="hidden" name="minke_form" value="True">'
        indicator_password = '<input type="password" name="initial_password" maxlength="100"'
        indicator_confirm = 'type="checkbox" name="_selected_action" value="1" checked>'
        indicator_testform = '<input type="number" name="one"'

        get_test = lambda b: self.assertIn if bool(b) else self.assertNotIn

        # calling the form in all possible variations
        for password in [True, False]:
            for confirm in [True, False]:
                for testform in [TestForm, None]:
                    settings.MINKE_PASSWORD_FORM = password
                    DummySession.CONFIRM = confirm
                    DummySession.FORM = testform

                    # without form-data
                    if not (password or confirm or testform): continue
                    resp = self.client.post(url, post_data)
                    self.assertEqual(resp.status_code, 200)
                    self.assertIn(indicator_action_form, resp.content)
                    get_test(password)(indicator_password, resp.content)
                    get_test(confirm)(indicator_confirm, resp.content)
                    get_test(testform)(indicator_testform, resp.content)

                    # with invalid form-data
                    if not (password or testform): continue
                    resp = self.client.post(url, invalid_form_data)
                    self.assertEqual(resp.status_code, 200)
                    self.assertIn(indicator_action_form, resp.content)
                    get_test(password)(indicator_password, resp.content)
                    get_test(confirm)(indicator_confirm, resp.content)
                    get_test(testform)(indicator_testform, resp.content)

                    # with valid data
                    resp = self.client.post(url, valid_form_data, follow=True)
                    self.assertEqual(resp.redirect_chain[0][0], url)
                    self.assertEqual(resp.status_code, 200)

        settings.MINKE_PASSWORD_FORM = old_minke_password_form


    def test_03_session_api(self):
        sessions = list()
        servers = list(Server.objects.filter(hostname__contains='222'))
        server_ct = ContentType.objects.get_for_model(Server)
        for server in servers:
            session = BaseSession(
                object_id=server.id,
                content_type=server_ct,
                session_name=DummySession.__name__,
                user=self.anyuser,
                current=True,
                status='success',
                proc_status='done')
            session.save()
            message = BaseMessage(
                session=session,
                level='info',
                html='<h1>foobär</h1>',
                text='foobär')
            message.save()
            session.messages.add(message)
            sessions.append(session)

        url = reverse('minke_session_api', args=['server'])
        object_ids = [str(s.id) for s in servers]
        url += '?object_ids=' + ','.join(object_ids)

        self.client.force_login(self.anyuser)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.accepted_media_type, 'application/json')
        content = json.loads(resp.content)
        self.assertEqual(len(content), len(servers))
        for session in content:
            self.assertIn(str(session['object_id']), object_ids)
            self.assertEqual(session['status'], 'success')
            self.assertEqual(session['proc_status'], 'done')
            self.assertEqual(session['session_name'], DummySession.__name__)
            self.assertEqual(session['messages'][0]['level'], 'info')
            self.assertEqual(session['messages'][0]['html'], '<h1>foobär</h1>')

        self.client.logout()

        # Those sessions should not only be loaded for the associated user
        self.client.force_login(self.admin)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.accepted_media_type, 'application/json')
        content = json.loads(resp.content)
        self.assertEqual(content, list())
