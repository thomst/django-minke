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
    con = Connection(user=host.username, host=host.hostname)
    session.start(con)
    return session.proxy.process()


class SessionTest(TransactionTestCase):
    def setUp(self):
        create_test_data()
        self.host = Host.objects.get(name='localhost')
        self.server = Server.objects.get(host=self.host)
        self.user = User.objects.get(username='admin')
        self._registry = sessions.registry.copy()

    def reset_registry(self):
        MethodTestSession.WORK_ON = tuple()
        sessions.registry = self._registry.copy()

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

        # invalid minke-model
        MethodTestSession.WORK_ON = (Foobar,)
        args = [MethodTestSession]
        self.assertRaises(InvalidMinkeSetup, register, *args)
        self.reset_registry()

        # register MethodTestSession
        MethodTestSession.WORK_ON = (Server,)
        register(MethodTestSession)
        self.assertTrue(MethodTestSession in sessions.registry.values())
        self.reset_registry()

        # register MethodTestSession with Host-object
        MethodTestSession.WORK_ON = (Host,)
        register(MethodTestSession)
        self.assertTrue(MethodTestSession in sessions.registry.values())
        self.reset_registry()

        # register with create_permission
        MethodTestSession.WORK_ON = (Host, Server)
        register(MethodTestSession, create_permission=True)
        self.assertTrue(MethodTestSession in sessions.registry.values())
        Permission.objects.get(codename='run_methodtestsession_on_host_and_server')
        self.reset_registry()

    def test_02_cmd_format(self):

        # get formatted command-string (using players-attributes and session-data)
        cmd_format = '{hostname} {foo}'
        session_data = dict(foo='foo')
        session = MethodTestSession(None, self.server, session_data)
        cmd = session.format_cmd(cmd_format)
        self.assertEqual(cmd, 'localhost foo')

        # session-data should be have precedence
        session_data = dict(hostname='foobär', foo='foo')
        session = MethodTestSession(None, self.server, session_data)
        cmd = session.format_cmd(cmd_format)
        self.assertEqual(cmd, 'foobär foo')

        # test SingleActionSession.get_cmd
        # should raise an exception if COMMAND is not set
        SingleActionDummySession.COMMAND = None
        session = SingleActionDummySession(None, self.server, dict())
        self.assertRaises(InvalidMinkeSetup, session.get_cmd)

        # otherwise a fromatted command
        session_data = dict(hostname='foobär', foo='foo')
        SingleActionDummySession.COMMAND = '{hostname} {foo}'
        session = SingleActionDummySession(None, self.server, session_data)
        self.assertEqual(session.get_cmd(), 'foobär foo')

    def test_03_set_status(self):

        session = MethodTestSession(None, self.server, dict())
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

        con = Connection(user=self.host.username, host=self.host.hostname)

        # test message-calls
        data = dict(test='execute')
        session = session = MethodTestSession(con, self.server, data)
        session.process()
        self.assertEqual(session.messages[0].level, 'info')
        self.assertEqual(session.messages[1].level, 'warning')
        self.assertEqual(session.messages[2].level, 'error')
        self.assertEqual(session.messages[0].text, 'hello wörld\n')
        self.assertRegex(session.messages[1].text, 'code\[0\] +echo "hello wörld" 1>&2\n')
        self.assertRegex(session.messages[2].text, 'code\[1\] +\[ 1 == 2 \]')

        # test update_field
        data = dict(test='update')
        session = session = MethodTestSession(con, self.server, data)
        session.process()
        self.assertEqual(session.minkeobj.hostname, 'foobär\n')

        # test update_field with regex
        data = dict(test='update_regex')
        session = session = MethodTestSession(con, self.server, data)
        session.process()
        self.assertEqual(session.minkeobj.hostname, 'foo')

        # test update_field with failing regex
        data = dict(test='update_regex_fails')
        session = session = MethodTestSession(con, self.server, data)
        session.process()
        self.assertEqual(session.messages[0].level, 'error')
        self.assertRegex(session.messages[0].text, 'code\[0\] +echo "foobär"\n')

        # test update_field-call with invalid field
        data = dict(test='update_invalid_field')
        session = session = MethodTestSession(con, self.server, data)
        self.assertRaises(AttributeError, session.update_field, 'nofield', 'echo')

    # TODO: skipIf-decorator if localhost cannot be connected
    def test_05_unicdoe_result(self):
        con = Connection(user=self.host.username, host=self.host.hostname)

        # test with utf-8-encoding
        data = dict(test='unicode_result')
        session = session = MethodTestSession(con, self.server, data)
        result = session.process()
        self.assertEqual(type(result.stdout), unicode)
        self.assertEqual(type(result.stderr), unicode)
        self.assertEqual(result.stdout, 'hällo\n')
        self.assertEqual(result.stderr, 'wörld\n')
