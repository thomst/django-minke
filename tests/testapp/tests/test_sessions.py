# -*- coding: utf-8 -*-

from fabric2 import Connection
from django.test import TestCase
from django.test import tag
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User

from minke import sessions
from minke.sessions import Session
from minke.sessions import SessionRegistration
from minke.exceptions import InvalidMinkeSetup
from minke.exceptions import SessionRegistrationError
from minke.models import Host
from minke.models import MinkeSession
from minke.engine import process
from minke.settings import MINKE_FABRIC_CONFIG
from ..models import Server
from ..sessions import MethodTestSession
from ..sessions import SingleActionDummySession
from ..sessions import RunCommands
from ..sessions import RunSessions
from ..sessions import DummySession
from .utils import create_test_data
from .utils import create_session


def process_session(session, host):
    con = Connection(user=host.username, host=host.hostname)
    session.start(con)
    return session.proxy.process()


class SessionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_test_data()

    def setUp(self):
        self.host = Host.objects.get(name='localhost')
        self.server = Server.objects.get(host=self.host)
        self.user = User.objects.get(username='admin')
        config = MINKE_FABRIC_CONFIG.clone()
        self.con = Connection(self.host.hostname, self.host.username, config=config)
        self._REGISTRY = sessions.REGISTRY.copy()

    def tearDown(self):
        self.reset_registry()

    def reset_registry(self, session_name='MySession'):
        sessions.REGISTRY = self._REGISTRY

    def test_01_register_session(self):

        # abstract Session-class
        class MySession(Session):
            abstract = True

        # a monkey-minke-model
        class Foobar(object):
            pass

        # Missing minke-model
        MySession.work_on = tuple()
        self.assertRaises(SessionRegistrationError, MySession.register)

        # Invalid minke-model
        MySession.work_on = (Foobar,)
        self.assertRaises(SessionRegistrationError, MySession.register)

        # valid registration
        MySession.work_on = (Server,)
        MySession.register()
        self.assertIn('MySession', sessions.REGISTRY)

        # register an already registered Session should raise an exception.
        self.assertRaises(SessionRegistrationError, MySession.register)

        # add_permission
        MySession.add_permission()
        self.assertEqual(len(MySession.permissions), 1)

        # create_permission
        perm, created = MySession.create_permission()
        self.assertTrue(created)
        perm = Permission.objects.get(pk=perm.pk)
        self.assertEqual(perm.codename, 'run_mysession')

        # delete permission
        MySession.delete_permission()
        self.assertRaises(Permission.DoesNotExist, Permission.objects.get, pk=perm.pk)

    def test_02_cmd_format(self):

        # get formatted command-string (using players-attributes and session-data)
        cmd_format = '{hostname} {foo}'
        session_data = dict(foo='foo')
        session = create_session(MethodTestSession, self.server, session_data, None)
        cmd = session.format_cmd(cmd_format)
        self.assertEqual(cmd, 'localhost foo')

        # session-data should be have precedence
        session_data = dict(hostname='foobär', foo='foo')
        session = create_session(MethodTestSession, self.server, session_data, None)
        cmd = session.format_cmd(cmd_format)
        self.assertEqual(cmd, 'foobär foo')

    def test_03_set_status(self):

        session = create_session(MethodTestSession, self.server, dict(), None)
        session.set_status('error', update=False)
        self.assertTrue(session.status == 'error')
        session.set_status('WARNING', update=False)
        self.assertTrue(session.status == 'warning')
        session.set_status(True, update=False)
        self.assertTrue(session.status == 'success')
        session.set_status(False, update=False)
        self.assertTrue(session.status == 'error')
        session.set_status('success', update=True)
        self.assertTrue(session.status == 'error')
        self.assertRaises(InvalidMinkeSetup, session.set_status, 'foobar')

    @tag('ssh')
    def test_04_processing(self):

        # test message-calls
        data = dict(test='execute')
        session = create_session(MethodTestSession, self.server, data, self.con)
        session.process()
        self.assertEqual(session._db.messages.all()[0].level, 'info')
        self.assertEqual(session._db.messages.all()[1].level, 'warning')
        self.assertEqual(session._db.messages.all()[2].level, 'error')
        self.assertRegex(session._db.messages.all()[0].text, 'code\[0\] +echo "hello wörld"\n')
        self.assertRegex(session._db.messages.all()[1].text, 'code\[0\] +echo "hello wörld" 1>&2\n')
        self.assertRegex(session._db.messages.all()[2].text, 'code\[1\] +\[ 1 == 2 \]')

        # test update_field
        data = dict(test='update')
        session = create_session(MethodTestSession, self.server, data, self.con)
        session.process()
        self.assertEqual(session.minkeobj.hostname, 'foobär\n')

        # test update_field with regex
        data = dict(test='update_regex')
        session = create_session(MethodTestSession, self.server, data, self.con)
        session.process()
        self.assertEqual(session.minkeobj.hostname, 'foo')

        # test update_field with failing regex
        data = dict(test='update_regex_fails')
        session = create_session(MethodTestSession, self.server, data, self.con)
        session.process()
        self.assertEqual(session._db.messages.all()[0].level, 'error')
        self.assertRegex(session._db.messages.all()[0].text, 'code\[0\] +echo "foobär"\n')

        # test update_field-call with invalid field
        data = dict(test='update_invalid_field')
        session = create_session(MethodTestSession, self.server, data, self.con)
        self.assertRaises(AttributeError, session.update_field, 'nofield', 'echo')

    @tag('ssh')
    def test_05_unicdoe_result(self):
        # test with utf-8-encoding
        data = dict(test='unicode_result')
        session = create_session(MethodTestSession, self.server, data, self.con)
        result = session.process()
        self.assertEqual(result.stdout, 'hällo\n')
        self.assertEqual(result.stderr, 'wörld\n')

    @tag('ssh')
    def test_06_more_sessions(self):
        session = create_session(RunCommands, self.server, con=self.con)
        session.process()
        self.assertEqual(session.status, 'error')
        self.assertEqual(len(session._db.messages.all()), 3)
        session = create_session(RunCommands, self.server, con=self.con)
        session.break_states = ('warning',)
        session.process()
        self.assertEqual(session.status, 'warning')
        self.assertEqual(len(session._db.messages.all()), 2)
        session = create_session(RunCommands, self.server, con=self.con)
        session.break_states = ('success',)
        session.process()
        self.assertEqual(session.status, 'success')
        self.assertEqual(len(session._db.messages.all()), 1)

        session = create_session(RunSessions, self.server, con=self.con)
        session.process()
        self.assertEqual(session.status, 'error')
        self.assertEqual(len(session._db.messages.all()), 6)
        session = create_session(RunSessions, self.server, con=self.con)
        session.break_states = ('warning',)
        session.process()
        self.assertEqual(session.status, 'warning')
        self.assertEqual(len(session._db.messages.all()), 4)
        session = create_session(RunSessions, self.server, con=self.con)
        session.break_states = ('success',)
        session.process()
        self.assertEqual(session.status, 'success')
        self.assertEqual(len(session._db.messages.all()), 2)
