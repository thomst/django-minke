# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.test import TestCase
from django.core.management import call_command

from minke.management.commands.minke import Command
from minke.management.commands.minke import FilterArgumentError
from minke.management.commands.minke import InvalidFormData
from minke.sessions import Session
from minke.models import Host
from ..models import Server, AnySystem


class MinkeManagerTest(TestCase):
    fixtures = ['minke.json', 'testapp.json']

    def setUp(self):

        class TestSession(Session):
            def process(self):
                pass

        self.manager = Command()
        self._options = dict(
            session=TestSession,
            model=Host,
            list=False,
            no_prefix=False,
            silent=False,
            form_data=None,
            url_query=None,
            offset=None,
            limit=None)
        self.options = self._options

    def reset_options(self):
        self.options = self._options

    def test_01_get_queryset(self):
        qs = self.manager.get_queryset(Host, self.options)
        self.assertListEqual(list(Host.objects.all()), list(qs))

        self.options['url_query'] = 'q=local'
        qs = self.manager.get_queryset(Host, self.options)
        for host in qs:
            self.assertRegex(host.host, 'local')
