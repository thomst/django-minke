# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
import re

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TransactionTestCase
from django.test import Client
from django.test import override_settings
from django.urls import reverse

from minke import sessions
from minke import settings
from minke.models import BaseSession
from minke.messages import PreMessage
from ..settings import CELERY_TEST_SETTINGS
from ..sessions import LeaveAMessageSession
from ..sessions import DummySession
from ..sessions import ExceptionSession
from ..models import Host, Server, AnySystem
from ..forms import TestForm
from .utils import create_test_data
from .utils import create_session


class ViewsTest(TransactionTestCase):
    def setUp(self):
        create_test_data()
        self.admin = User.objects.get(username='admin')
        self.anyuser = User.objects.get(username='anyuser')

    @override_settings(**CELERY_TEST_SETTINGS)
    def test_01_session_view(self):
        url_pattern = 'admin:{}_{}_changelist'
        player_ids = [1, 2, 3]
        post_data = dict()
        post_data['action'] = LeaveAMessageSession.__name__
        post_data['_selected_action'] = player_ids

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

    @override_settings(**CELERY_TEST_SETTINGS)
    def test_02_permissions(self):
        url = reverse('admin:minke_host_changelist')
        post_data = dict()
        post_data['action'] = LeaveAMessageSession.__name__
        post_data['_selected_action'] = [1]
        # work with unprivileged user
        self.client.force_login(self.anyuser)

        # DummySession should be listed as action.
        # LeaveAMessageSession needs permissions, so it shouldn't.
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(DummySession.__name__, resp.content)
        self.assertNotIn(LeaveAMessageSession.__name__, resp.content)

        # TODO: Find a way to check 403-response when calling SessionView
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

        self.client.logout()

    @override_settings(**CELERY_TEST_SETTINGS)
    def test_03_session_raises_exception(self):
        url = reverse('admin:minke_host_changelist')
        post_data = dict()
        post_data['action'] = ExceptionSession.__name__
        post_data['_selected_action'] = [1]
        self.client.force_login(self.admin)
        old_minke_debug = settings.MINKE_DEBUG

        settings.MINKE_DEBUG = True
        resp = self.client.post(url, post_data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(ExceptionSession.ERR_MSG, resp.content)

        settings.MINKE_DEBUG = False
        resp = self.client.post(url, post_data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('An error occurred', resp.content)

        settings.MINKE_DEBUG = old_minke_debug
        self.client.logout()

    @override_settings(**CELERY_TEST_SETTINGS)
    def test_04_session_form(self):
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
        valid_form_data['connect_kwargs_passphrase'] = 'password'
        valid_form_data['one'] = 1
        valid_form_data['two'] = 2

        self.client.force_login(self.admin)
        old_minke_password_form = settings.MINKE_FABRIC_FORM
        indicator_action_form = '<input type="hidden" name="minke_form" value="True">'
        indicator_password = '<input type="password" name="connect_kwargs_passphrase"'
        indicator_confirm = 'type="checkbox" name="_selected_action" value="1" checked>'
        indicator_testform = '<input type="number" name="one"'

        get_test = lambda b: self.assertIn if bool(b) else self.assertNotIn

        # calling the form in all possible variations
        options = list()
        for passform in ['minke.forms.PassphraseForm', False]:
            for confirm in [True, False]:
                for testform in [TestForm, None]:
                    options.append((passform, confirm, testform))

        for passform, confirm, testform in options:
            settings.MINKE_FABRIC_FORM = passform
            DummySession.CONFIRM = confirm
            DummySession.FORM = testform

            # without form-data
            if not (passform or confirm or testform): continue
            resp = self.client.post(url, post_data)
            self.assertEqual(resp.status_code, 200)
            self.assertIn(indicator_action_form, resp.content)
            get_test(passform)(indicator_password, resp.content)
            get_test(confirm)(indicator_confirm, resp.content)
            get_test(testform)(indicator_testform, resp.content)

            # with invalid form-data
            if not (passform or testform): continue
            resp = self.client.post(url, invalid_form_data)
            self.assertEqual(resp.status_code, 200)
            self.assertIn(indicator_action_form, resp.content)
            get_test(passform)(indicator_password, resp.content)
            get_test(confirm)(indicator_confirm, resp.content)
            get_test(testform)(indicator_testform, resp.content)

            # with valid data
            resp = self.client.post(url, valid_form_data, follow=True)
            self.assertEqual(resp.redirect_chain[0][0], url)
            self.assertEqual(resp.status_code, 200)

        self.client.logout()
        DummySession.CONFIRM = False
        DummySession.FORM = None
        settings.MINKE_FABRIC_FORM = old_minke_password_form

    @override_settings(**CELERY_TEST_SETTINGS)
    def test_05_minke_filter(self):
        self.client.force_login(self.admin)
        baseurl = reverse('admin:minke_host_changelist')

        # create 7 sessions, 1 with success-, 2 with warning-, 4 with error-status
        hosts = Host.objects.all()[:7]
        for i, host in enumerate(hosts):
            status = 'success' if i == 0 else 'error' if i > 2 else 'warning'
            session = create_session(host, status=status)

        # create a matrix for all variations of filter-params
        options = list()
        for success in [True, False]:
            for warning in [True, False]:
                for error in [True, None]:
                    options.append((success, warning, error))

        # get-requests with minkestatus-filter-params
        for success, warning, error in options:
            if not (success or warning or error): continue
            url_query = '?minkestatus='
            url_query += 'success,' if success else ''
            url_query += 'warning,' if warning else ''
            url_query += 'error' if error else ''
            count = 1 if success else 0
            count += 2 if warning else 0
            count += 4 if error else 0
            url = baseurl + url_query
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200)
            matches = re.findall('<tr class="row[12] \w+ done">', resp.content)
            self.assertEqual(len(matches), count)

        self.client.logout()

    @override_settings(**CELERY_TEST_SETTINGS)
    def test_06_session_api(self):
        servers = list(Server.objects.filter(hostname__contains='222'))
        server_ct = ContentType.objects.get_for_model(Server)
        for server in servers:
            session = create_session(server, user='anyuser')
            session.add_msg(PreMessage('foobär'))

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
            self.assertIn(DummySession.short_description, session['get_html'])
            self.assertIn('foobär', session['get_html'])
            self.assertTrue(session['ready'])

        self.client.logout()

        # Those sessions should only be loaded for the associated user
        self.client.force_login(self.admin)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.accepted_media_type, 'application/json')
        content = json.loads(resp.content)
        self.assertEqual(content, list())
