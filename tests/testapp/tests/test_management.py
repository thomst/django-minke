# -*- coding: utf-8 -*-

import io
import sys
import os

from django.test import TestCase
from django.core.management import call_command
from django.contrib.auth.models import User

from minke import settings
from minke.models import Host
from minke.management.commands import minkerun
from minke.management.commands.minkerun import Command
from minke.management.commands.minkerun import CommandError

from .utils import create_test_data
from ..sessions import TestFormSession
from ..sessions import DummySession


class InOut(list):
    def __init__(self, *inputs):
        self.inputs = iter(inputs)

    def __enter__(self):
        minkerun.input = lambda x: next(self.inputs)
        self._stdin = sys.stdin
        self._stdout = sys.stdout
        sys.stdout = self._out = io.StringIO()
        return self

    def __exit__(self, *args):
        minkerun.input = input
        self.extend(self._out.getvalue().splitlines())
        sys.stdout = self._stdout


class MinkeManagerTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_test_data()

    def setUp(self):
        self.manager = Command()
        self.admin = User.objects.get(username='admin')
        self.anyuser = User.objects.get(username='anyuser')
        self._options = dict(
            session=TestFormSession,
            model=Host,
            list=False,
            form_data=None,
            url_query=None,
            offset=None,
            user=None,
            limit=None)
        self.options = self._options

    def tearDown(self):
        self.options = self._options

    def test_01_get_queryset(self):
        # simple queryset - just all elements
        qs = self.manager.get_queryset(self.options, Host, self.admin)
        self.assertListEqual(list(Host.objects.all()), list(qs))

        # get a changelist-query
        self.options['url_query'] = 'q=label111'
        qs = self.manager.get_queryset(self.options, Host, self.admin)
        for host in qs:
            self.assertRegex(host.name, 'label111')

        # get a more complex changelist-query
        self.options['url_query'] = 'q=1&username=userlabel222'
        qs = self.manager.get_queryset(self.options, Host, self.admin)
        for host in qs:
            self.assertRegex(host.name, '1')
            self.assertEqual(host.username, 'userlabel222')

    def test_02_get_form_data(self):
        # fails because of missing data
        self.options['form_data'] = 'one=123'
        self.assertRaisesRegex(
            CommandError,
            'This field is required',
            self.manager.get_form_data,
            self.options,
            TestFormSession)

        # fails because of wrong data-type
        self.options['form_data'] = 'one=123,two="abc"'
        self.assertRaisesRegex(
            CommandError,
            'Enter a whole number',
            self.manager.get_form_data,
            self.options,
            TestFormSession)

        # fails because of invalid dict-data
        self.options['form_data'] = 'one=123&two="abc"'
        self.assertRaisesRegex(
            CommandError,
            'invalid syntax',
            self.manager.get_form_data,
            self.options,
            TestFormSession)

        # this should pass
        self.options['form_data'] = 'one=123,two="234"'
        cleaned_data = self.manager.get_form_data(self.options, TestFormSession)
        self.assertEqual(cleaned_data['one'], 123)
        self.assertEqual(cleaned_data['two'], 234)

    def test_get_user(self):
        perm, created = DummySession.create_permission()
        self.anyuser.user_permissions.add(perm)

        user = self.manager.get_user(self.options, DummySession)
        self.assertEqual(settings.MINKE_CLI_USER, user.username)

        os.environ['MINKE_CLI_USER'] = 'anyuser'
        user = self.manager.get_user(self.options, DummySession)
        self.assertEqual('anyuser', user.username)

        self.options['user'] = 'anyuser'
        user = self.manager.get_user(self.options, DummySession)
        self.assertEqual('anyuser', user.username)

        self.options['user'] = 'foobar'
        self.assertRaises(
            CommandError,
            self.manager.get_user,
            self.options,
            DummySession)

        self.anyuser.user_permissions.remove(perm)
        self.options['user'] = 'anyuser'
        self.assertRaises(
            CommandError,
            self.manager.get_user,
            self.options,
            DummySession)


    def test_03_invalid_calls(self):

        # call without model
        with InOut() as out:
            self.assertRaises(SystemExit, call_command, 'minkerun', 'DummySession')
        self.assertRegex(out[0], '[ERROR].+model.*')

        # call with invalid session
        with InOut() as out:
            self.assertRaises(SystemExit, call_command, 'minkerun', 'Fake')
        self.assertRegex(out[0], '[ERROR].+session.*')

        # call with invalid model
        with InOut() as out:
            self.assertRaises(SystemExit, call_command, 'minkerun', 'DummySession', 'Fake')
        self.assertRegex(out[0], '[ERROR].+model.*')

        # call with invalid url_query
        with InOut() as out:
            self.assertRaises(SystemExit, call_command, 'minkerun', 'DummySession', 'Server', '--url-query=foobar')
        self.assertRegex(out[0], '[ERROR].+url-query.*')

    def test_04_valid_calls(self):
        # list sessions
        with InOut() as out:
            call_command('minkerun', '--list-sessions')
        self.assertIn('DummySession', out)
        self.assertIn('TestFormSession', out)
        self.assertIn('TestUpdateFieldSession', out)

        # list items
        with InOut() as out:
            call_command('minkerun', 'DummySession', 'Server', '--list-items')
        self.assertIn('host_0_label000', out)
        self.assertIn('host_1_label111', out)
        self.assertIn('host_2_label222', out)

        # slicing the queryset with offset and limit
        with InOut() as out_0_10:
            call_command('minkerun', 'SingleModelDummySession',
                         '--offset=0', '--limit=10', '--list-items')
        self.assertEqual(len(out_0_10), 10)

        with InOut() as out_10_20:
            call_command('minkerun', 'SingleModelDummySession',
                         '--offset=10', '--limit=10', '--list-items')
        self.assertEqual(len(out_10_20), 10)

        with InOut() as out_0_20:
            call_command('minkerun', 'SingleModelDummySession',
                         '--offset=0', '--limit=20', '--list-items')
        self.assertEqual(len(out_0_20), 20)
        self.assertListEqual(sorted(out_0_10 + out_10_20), sorted(out_0_20))

        # read form-data from stdin
        with InOut('123', '', 'abc', '123') as out:
            call_command('minkerun', 'TestFormSession', 'Server', '--limit=0')
        self.assertRegex(out[2], 'This field is required')
        self.assertRegex(out[3], 'Enter a whole number')

        # valid call with url-query that really process some items
        with InOut() as out:
            call_command('minkerun', 'DummySession', 'Server', '--url-query=q=222')
        self.assertRegex(out[0], 'host_[0-9]{1,2}_label222')
        self.assertEqual(len(out), 5)
