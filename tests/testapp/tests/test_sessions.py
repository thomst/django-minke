# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from fabric2 import Connection

from django.test import TransactionTestCase
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User

from minke import sessions
from minke.sessions import register
from minke.sessions import Session
from minke.sessions import UpdateEntriesSession
from minke.exceptions import InvalidMinkeSetup
from minke.models import Host
from minke.engine import process
from ..models import Server
from ..sessions import MethodTestSession
from ..sessions import SingleActionDummySession
from .utils import create_test_data


def process_session(session, host):
    con = Connection(user=host.user, host=host.hostname)
    session.start(con)
    return session.process()


class SessionTest(TransactionTestCase):
    def setUp(self):
        create_test_data()
        self.host = Host.objects.get(host='localhost')
        self.server = Server.objects.get(host=self.host)
        self.user = User.objects.get(username='admin')
        self._registry = sessions.registry[:]

    def reset_registry(self):
        MethodTestSession.models = tuple()
        sessions.registry = self._registry[:]

    def init_session(self, session_cls, data=None):
        session = session_cls()
        session.init(self.user, self.server, data or dict())
        return session

    def test_01_register_session(self):
        # a monkey-class
        class Foobar(object):
            pass

        # wrong session-class
        args = [Foobar]
        self.assertRaises(InvalidMinkeSetup, register, *args)
        self.reset_registry()

        # missing minke-models
        args = [MethodTestSession]
        self.assertRaises(InvalidMinkeSetup, register, *args)
        self.reset_registry()

        # missing get_host-method
        args = [MethodTestSession, Foobar]
        self.assertRaises(InvalidMinkeSetup, register, *args)
        self.reset_registry()

        # register MethodTestSession
        register(MethodTestSession, Server)
        self.assertTrue(MethodTestSession in sessions.registry)
        self.reset_registry()

        # register MethodTestSession with Host-object
        register(MethodTestSession, Host)
        self.assertTrue(MethodTestSession in sessions.registry)
        self.reset_registry()

        # register with create_permission
        register(MethodTestSession, Server, create_permission=True)
        self.assertTrue(MethodTestSession in sessions.registry)
        Permission.objects.get(codename='run_method_test_session_on_server')
        self.reset_registry()

    def test_02_cmd_format(self):

        # get formatted command-string (using players-attributes and session-data)
        cmd_format = '{hostname} {foo}'
        session_data = dict(foo='foo')
        session = self.init_session(MethodTestSession, session_data)
        cmd = session.format_cmd(cmd_format)
        self.assertEqual(cmd, 'localhost foo')

        # session-data should be have precedence
        session_data = dict(hostname='foobär', foo='foo')
        session = self.init_session(MethodTestSession, session_data)
        cmd = session.format_cmd(cmd_format)
        self.assertEqual(cmd, 'foobär foo')

        # test SingleActionSession.get_cmd
        # should raise an exception if COMMAND is not set
        SingleActionDummySession.COMMAND = None
        session = self.init_session(SingleActionDummySession)
        self.assertRaises(InvalidMinkeSetup, session.get_cmd)

        # otherwise a fromatted command
        session_data = dict(hostname='foobär', foo='foo')
        SingleActionDummySession.COMMAND = '{hostname} {foo}'
        session = self.init_session(SingleActionDummySession, session_data)
        self.assertEqual(session.get_cmd(), 'foobär foo')

    def test_03_set_status(self):

        session = self.init_session(MethodTestSession)

        session.set_status('error')
        self.assertTrue(session.status == 'error')
        session.set_status('WARNING')
        self.assertTrue(session.status == 'warning')
        session.set_status(True)
        self.assertTrue(session.status == 'success')
        session.set_status(False)
        self.assertTrue(session.status == 'error')
        self.assertRaises(InvalidMinkeSetup, session.set_status, 'foobar')

    # TODO: skipIf-decorator if localhost cannot be connected
    def test_04_processing(self):

        # test message-calls
        session = self.init_session(MethodTestSession, dict(test='execute'))
        session = process_session(session, self.host)
        news = session.messages.all()
        self.assertEqual(news[0].level, 'info')
        self.assertEqual(news[1].level, 'warning')
        self.assertEqual(news[2].level, 'error')
        self.assertEqual(news[0].text, 'hello wörld\n')
        self.assertRegex(news[1].text, 'code\[0\] +echo "hello wörld" 1>&2\n')
        self.assertRegex(news[2].text, 'code\[1\] +\[ 1 == 2 \]')

        # test update_field
        session = self.init_session(MethodTestSession, dict(test='update'))
        session = process_session(session, self.host)
        self.assertEqual(session.player.hostname, 'foobär\n')

        # test update_field with regex
        session = self.init_session(MethodTestSession, dict(test='update_regex'))
        session = process_session(session, self.host)
        self.assertEqual(session.player.hostname, 'foo')

        # test update_field with failing regex
        session = self.init_session(MethodTestSession, dict(test='update_regex_fails'))
        session = process_session(session, self.host)
        news = session.messages.all()
        self.assertEqual(news[0].level, 'error')
        self.assertRegex(news[0].text, 'code\[0\] +echo "foobär"\n')

        # test update_field-call with invalid field
        session = self.init_session(MethodTestSession, dict(test='update_invalid_field'))
        self.assertRaises(AttributeError, session.update_field, 'nofield', 'echo')

    # TODO: skipIf-decorator if localhost cannot be connected
    def test_05_unicdoe_result(self):

        # test with utf-8-encoding
        session = self.init_session(MethodTestSession, dict(test='unicode_result'))
        result = process_session(session, self.host)
        self.assertEqual(type(result.stdout), unicode)
        self.assertEqual(type(result.stderr), unicode)
        self.assertEqual(result.stdout, 'hällo\n')
        self.assertEqual(result.stderr, 'wörld\n')
