# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.test import TransactionTestCase
from django.test import Client

from minke.models import BaseSession
from ..sessions import LeaveAMessageSession
from .utils import create_test_data


class ViewsTest(TransactionTestCase):
    def setUp(self):
        create_test_data()

    def test_01_change_list(self):
        c = Client()
        c.login(username='admin', password='adminpassword')
        player_ids = [1, 2, 3, 4, 5]
        post_data = dict(
            action='LeaveAMessageSession',
            _selected_action=player_ids)
        url = '/admin/minke/host/'
        resp = c.post(url, post_data)
        self.assertEqual(resp.status_code, 302)
        sessions = BaseSession.objects.all()
        object_ids = list(sessions.values_list('object_id', flat=True))
        self.assertEqual(sorted(object_ids), sorted(player_ids))
        resp = c.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(LeaveAMessageSession.MSG, resp.content.decode('utf8'))
