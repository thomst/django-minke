# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from fabric.api import env, execute
from fabric.network import disconnect_all
from fabric.operations import _AttributeString

from django.test import TestCase
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User

from minke import sessions
from minke.utils import UnicodeResult
from minke.sessions import register
from minke.sessions import Session
from minke.sessions import UpdateEntriesSession
from minke.exceptions import InvalidMinkeSetup
from minke.models import Host
from minke.engine import process
from ..models import Server
from ..sessions import MethodTestSession
from .utils import create_multiple_hosts
from .utils import create_testapp_player
from .utils import create_localhost
from .utils import create_user


def process_session(session, hoststring):
    try: result = execute(session.process, hosts=[hoststring])
    finally: disconnect_all()
    return result[hoststring]


class SessionTest(TestCase):
    def setUp(self):
        create_user()
        create_multiple_hosts()
        create_testapp_player()
        create_localhost()
        self.host = Host.objects.get(host='localhost')
        self.server = Server.objects.get(host=self.host)
        self._registry = sessions.registry[:]

    def reset_registry(self):
        MethodTestSession.models = tuple()
        sessions.registry = self._registry[:]

    def init_session(self, player, data=None):
        user = User.objects.get(username='admin')
        return MethodTestSession(user=user, player=player, session_data=data)

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
        session = self.init_session(self.server, session_data)
        cmd = session.format_cmd(cmd_format)
        self.assertEqual(cmd, 'localhost foo')

        # session-data should be have precedence
        session_data = dict(hostname='foobar', foo='foo')
        session = self.init_session(self.server, session_data)
        cmd = session.format_cmd(cmd_format)
        self.assertEqual(cmd, 'foobar foo')

    # TODO: skipIf-decorator if localhost cannot be connected
    def test_03_processing(self):

        # test message-calls
        session = self.init_session(self.server, dict(test='execute'))
        session = process_session(session, self.host.hoststring)
        news = session.news
        self.assertEqual(news[0].level, 'info')
        self.assertEqual(news[1].level, 'warning')
        self.assertEqual(news[2].level, 'error')
        self.assertEqual(news[0].text, 'hello wörld')
        self.assertRegex(news[1].text, 'code\[0\] +echo "hello wörld" 1>&2')
        self.assertRegex(news[2].text, 'code\[1\] +\[ 1 == 2 \]')

        # test update_field
        session = self.init_session(self.server, dict(test='update'))
        session = process_session(session, self.host.hoststring)
        self.assertEqual(session.player.hostname, 'foobär')

        # test update_field with regex
        session = self.init_session(self.server, dict(test='update_regex'))
        session = process_session(session, self.host.hoststring)
        self.assertEqual(session.player.hostname, 'foo')

        # test update_field with failing regex
        session = self.init_session(self.server, dict(test='update_regex_fails'))
        session = process_session(session, self.host.hoststring)
        self.assertEqual(session.news[0].level, 'error')
        self.assertRegex(session.news[0].text, 'code\[0\] +echo "foobär"')

        # test update_field-call with invalid field
        session = self.init_session(self.server, dict(test='update_invalid_field'))
        self.assertRaises(AttributeError, session.update_field, 'nofield', 'echo')

    def test_04_unicdoe_result(self):

        # test with utf-8-encoding
        session = self.init_session(self.server, dict(test='unicode_result'))
        result = process_session(session, self.host.hoststring)
        self.assertEqual(type(result), UnicodeResult)
        self.assertEqual(type(result.stdout), unicode)
        self.assertEqual(type(result.stderr), unicode)
        self.assertEqual(result, 'hällo')
        self.assertEqual(result.stderr, 'wörld')

        # test with ascii-encoding using replace
        session = self.init_session(self.server, dict(test='unicode_result_replace'))
        result = process_session(session, self.host.hoststring)
        self.assertEqual(result, 'h��llo')
        self.assertEqual(result.stderr, 'w��rld')

        # test UnicodeResult directly
        attr_str = _AttributeString('hällo'.encode('utf-8'))
        attr_str.command = 'any command ø'
        attr_str.real_command = 'any real-command ø'
        attr_str.stderr = 'wörld'.encode('utf-8')
        attr_str.return_code = 0
        attr_str.succeeded = True
        attr_str.failed = False

        result = UnicodeResult(attr_str, 'utf-8', 'replace')
        self.assertEqual(type(result), UnicodeResult)
        self.assertEqual(type(result.stdout), unicode)
        self.assertEqual(type(result.stderr), unicode)
        self.assertEqual(result, 'hällo')
        self.assertEqual(result.stdout, 'hällo')
        self.assertEqual(result.stderr, 'wörld')

        # test with ascii-encoding using replace
        result = UnicodeResult(attr_str, 'ascii', 'replace')
        self.assertEqual(result, 'h��llo')
        self.assertEqual(result.stderr, 'w��rld')

    def test_05_set_status(self):

        session = self.init_session(self.server)

        session.set_status('error')
        self.assertTrue(session.status == 'error')
        session.set_status('WARNING')
        self.assertTrue(session.status == 'warning')
        session.set_status(True)
        self.assertTrue(session.status == 'success')
        session.set_status(False)
        self.assertTrue(session.status == 'error')
        self.assertRaises(InvalidMinkeSetup, session.set_status, 'foobar')
