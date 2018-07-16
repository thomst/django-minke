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
from .utils import create_multiple_hosts
from .utils import create_testapp_player


class TestSession(Session):
    def process(self):
        pass


class SessionTest(TestCase):
    def setUp(self):
        create_multiple_hosts()
        create_testapp_player()
        self.server = Server.objects.get(id=1)
        self.host = self.server.host

    def test_01_register_session(self):

        # monky-class
        class Foobar(object):
            pass

        # wrong session-class
        args = [Foobar]
        regex = 'must subclass Session'
        self.assertRaisesRegex(InvalidMinkeSetup, regex, register, *args)
        TestSession.models = tuple()

        # missing minke-models
        args = [TestSession]
        regex = 'one model must be specified'
        self.assertRaisesRegex(InvalidMinkeSetup, regex, register, *args)
        TestSession.models = tuple()

        # missing get_host-method
        args = [TestSession, Foobar]
        regex = 'get_host-method'
        self.assertRaisesRegex(InvalidMinkeSetup, regex, register, *args)
        TestSession.models = tuple()

        # register TestSession
        register(TestSession, Server)
        self.assertTrue(TestSession in registry)
        TestSession.models = tuple()

        # register with create_permission
        register(TestSession, Server, create_permission=True)
        self.assertTrue(TestSession in registry)
        Permission.objects.get(codename='run_test_session_on_server')
        TestSession.models = tuple()

    def test_02_set_status(self):
        session = TestSession(self.host, self.server)
        session.set_status('error')
        self.assertTrue(session.status == 'error')
        session.set_status(session.ERROR)
        self.assertTrue(session.status == 'error')
        session.set_status('ERROR')
        self.assertTrue(session.status == 'error')
        self.assertRaises(ValueError, session.set_status, 'foobar')
