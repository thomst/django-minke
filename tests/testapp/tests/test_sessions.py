# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.test import TestCase
from django.contrib.auth.models import Permission

from minke.sessions import register
from minke.sessions import registry
from minke.sessions import Session
from minke.exceptions import InvalidMinkeSetup
from minke.models import Host
from ..models import Server


class SessionTest(TestCase):
    fixtures = ['minke.json', 'testapp.json']

    def setUp(self):
        # session-class
        self.host = Host.objects.get(id=1)
        self.server = Server.objects.get(id=1)

        class TestSession(Session):
            def process(self):
                pass

        self.session_cls = TestSession

    def test_01_register_session(self):

        # monky-class
        class Foobar(object):
            pass

        def reset_registry():
            self.session_cls.models = tuple()
            registry = list()

        # wrong session-class
        args = [Foobar]
        regex = '.*must subclass Session.*'
        self.assertRaisesRegex(InvalidMinkeSetup, regex, register, *args)
        reset_registry()

        # missing minke-models
        args = [self.session_cls]
        regex = '.*one model must be specified.*'
        self.assertRaisesRegex(InvalidMinkeSetup, regex, register, *args)
        reset_registry()

        # missing get_host-method
        args = [self.session_cls, Foobar]
        regex = '.*get_host-method.*'
        self.assertRaisesRegex(InvalidMinkeSetup, regex, register, *args)
        reset_registry()

        # register TestSession
        register(self.session_cls, Server)
        self.assertTrue(self.session_cls in registry)
        reset_registry()

        # register with create_permission
        register(self.session_cls, Server, create_permission=True)
        self.assertTrue(self.session_cls in registry)
        Permission.objects.get(codename='run_test_session_on_server')

    def test_02_set_status(self):
        session = self.session_cls(self.host, self.server)
        session.set_status('error')
        self.assertTrue(session.status == 'error')
        session.set_status(session.ERROR)
        self.assertTrue(session.status == 'error')
        session.set_status('ERROR')
        self.assertTrue(session.status == 'error')
        self.assertRaises(ValueError, session.set_status, 'foobar')
