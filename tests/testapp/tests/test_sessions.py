# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from fabric.api import env, execute
from fabric.network import disconnect_all
from fabric.operations import _AttributeString

from django.test import TestCase
from django.contrib.auth.models import Permission

from minke import sessions
from minke.utils import UnicodeResult
from minke.sessions import register
from minke.sessions import Session
from minke.sessions import UpdateEntriesSession
from minke.exceptions import InvalidMinkeSetup
from minke.models import Host
from minke.engine import process
from ..models import Server
from .utils import create_multiple_hosts
from .utils import create_testapp_player
from .utils import create_localhost


class TestSession(UpdateEntriesSession):
    def process(self):
        return getattr(self, 'test_' + self.session_data['test'])()

    def test_execute(self):
        # execute-calls: valid, valid + stderr, invalid
        self.execute('echo "hello wörld"')
        self.execute('echo "hello wörld" 1>&2')
        self.execute('[ 1 == 2 ]')
        return self

    def test_update(self):
        self.update_field('hostname', 'echo "foobär"')
        return self

    def test_update_regex(self):
        self.update_field('hostname', 'echo "foobär"', '(foo).+')
        return self

    def test_update_regex_fails(self):
        self.update_field('hostname', 'echo "foobär"', 'fails')
        return self

    def test_unicode_result(self):
        return self.run('(echo "hällo"; echo "wörld" 1>&2)')

    def test_unicode_result_replace(self):
        return self.run('(echo "hällo"; echo "wörld" 1>&2)', 'ascii')


def process_session(session, hoststring):
    try: result = execute(session.process, hosts=[hoststring])
    finally: disconnect_all()
    return result[hoststring]


class SessionTest(TestCase):
    def setUp(self):
        create_multiple_hosts()
        create_testapp_player()
        create_localhost()
        self.host = Host.objects.get(host='localhost')
        self.server = Server.objects.get(host=self.host)
        self._registry = sessions.registry[:]

    def reset_registry(self):
        TestSession.models = tuple()
        sessions.registry = self._registry[:]

    def test_01_register_session(self):
        # a monkey-class
        class Foobar(object):
            pass

        # wrong session-class
        args = [Foobar]
        regex = 'must subclass Session'
        self.assertRaisesRegex(InvalidMinkeSetup, regex, register, *args)
        self.reset_registry()

        # missing minke-models
        args = [TestSession]
        regex = 'one model must be specified'
        self.assertRaisesRegex(InvalidMinkeSetup, regex, register, *args)
        self.reset_registry()

        # missing get_host-method
        args = [TestSession, Foobar]
        regex = 'get_host-method'
        self.assertRaisesRegex(InvalidMinkeSetup, regex, register, *args)
        self.reset_registry()

        # FIXME: how to clear the registry!
        # register TestSession
        register(TestSession, Server)
        self.assertTrue(TestSession in sessions.registry)
        self.reset_registry()

        # register TestSession with Host-object
        register(TestSession, Host)
        self.assertTrue(TestSession in sessions.registry)
        self.reset_registry()

        # register with create_permission
        register(TestSession, Server, create_permission=True)
        self.assertTrue(TestSession in sessions.registry)
        Permission.objects.get(codename='run_test_session_on_server')
        self.reset_registry()

    def test_02_set_status(self):

        session = TestSession(self.host, self.server)

        session.set_status('error')
        self.assertTrue(session.status == 'error')
        session.set_status(session.ERROR)
        self.assertTrue(session.status == 'error')
        session.set_status('ERROR')
        self.assertTrue(session.status == 'error')
        session.set_status(True)
        self.assertTrue(session.status == 'success')
        session.set_status(False)
        self.assertTrue(session.status == 'error')
        self.assertRaises(ValueError, session.set_status, 'foobar')

    def test_03_cmd_format(self):

        # get formatted command-string (using players-attributes and session-data)
        cmd_format = '{hostname} {foo}'
        session_data = dict(foo='foo')
        session = TestSession(self.host, self.server, **session_data)
        cmd = session.format_cmd(cmd_format)
        self.assertEqual(cmd, 'localhost foo')

        # session-data should be have precedence
        session_data = dict(hostname='foobar', foo='foo')
        session = TestSession(self.host, self.server, **session_data)
        cmd = session.format_cmd(cmd_format)
        self.assertEqual(cmd, 'foobar foo')

    # TODO: skipIf-decorator if localhost cannot be connected
    def test_04_processing(self):

        # test message-calls
        session = TestSession(self.host, self.server, test='execute')
        session = process_session(session, self.host.hoststring)
        news = session.news
        self.assertEqual(news[0].level, 'info')
        self.assertEqual(news[1].level, 'warning')
        self.assertEqual(news[2].level, 'error')
        self.assertEqual(news[0].text, 'hello wörld')
        self.assertRegex(news[1].text, 'code\[0\] +echo "hello wörld" 1>&2')
        self.assertRegex(news[2].text, 'code\[1\] +\[ 1 == 2 \]')

        # test update_field
        session = TestSession(self.host, self.server, test='update')
        session = process_session(session, self.host.hoststring)
        self.assertEqual(session.player.hostname, 'foobär')

        # test update_field with regex
        session = TestSession(self.host, self.server, test='update_regex')
        session = process_session(session, self.host.hoststring)
        self.assertEqual(session.player.hostname, 'foo')

        # test update_field with failing regex
        session = TestSession(self.host, self.server, test='update_regex_fails')
        session = process_session(session, self.host.hoststring)
        self.assertEqual(session.news[0].level, 'error')
        self.assertRegex(session.news[0].text, 'code\[0\] +echo "foobär"')

        # test update_field-call with invalid field
        session = TestSession(self.host, self.server, test='update_invalid_field')
        self.assertRaises(AttributeError, session.update_field, 'nofield', 'echo')

    def test_05_unicdoe_result(self):

        # test with utf-8-encoding
        session = TestSession(self.host, self.server, test='unicode_result')
        result = process_session(session, self.host.hoststring)
        self.assertEqual(type(result), UnicodeResult)
        self.assertEqual(type(result.stdout), unicode)
        self.assertEqual(type(result.stderr), unicode)
        self.assertEqual(result, 'hällo')
        self.assertEqual(result.stderr, 'wörld')

        # test with ascii-encoding using replace
        session = TestSession(self.host, self.server, test='unicode_result_replace')
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
