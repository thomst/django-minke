# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from StringIO import StringIO
import sys

from django.test import TestCase
from django.core.management import call_command
from django import forms

from minke.management.commands import minke as mm_module
from minke.management.commands.minke import Command
from minke.management.commands.minke import InvalidFormData
from minke.management.commands.minke import FilterArgumentError
from minke.management.commands.minke import InvalidFormData
from minke.sessions import Session
from minke.models import Host

from .utils import create_multiple_hosts
from .utils import create_testapp_player
from ..models import Server, AnySystem
# from ..sessions import TestFormSession, TestUpdateEntriesSession


class InOut(list):
    def __init__(self, *inputs):
        self.inputs = iter(inputs)

    def __enter__(self):
        mm_module.raw_input = lambda x: self.inputs.next()
        self._stdin = sys.stdin
        self._stdout = sys.stdout
        sys.stdout = self._out = StringIO()
        return self

    def __exit__(self, *args):
        mm_module.raw_input = raw_input
        self.extend(self._out.getvalue().splitlines())
        sys.stdout = self._stdout


class TestForm(forms.Form):
    one = forms.IntegerField(
        label='One',
        help_text='A number!',
        required=True,
    )
    two = forms.IntegerField(
        label='Two',
        help_text='Another number!',
        required=True,
    )

class TestSession(Session):
    FORM = TestForm
    def process(self):
        pass


class MinkeManagerTest(TestCase):

    def setUp(self):
        create_multiple_hosts()
        create_testapp_player()

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
        # simple queryset - just all elements
        qs = self.manager.get_queryset(Host, self.options)
        self.assertListEqual(list(Host.objects.all()), list(qs))

        # get a changelist-query
        self.options['url_query'] = 'q=label111'
        qs = self.manager.get_queryset(Host, self.options)
        for host in qs:
            self.assertRegex(host.host, 'label111')

        # get a more complex changelist-query
        self.options['url_query'] = 'q=1&user=userlabel222'
        qs = self.manager.get_queryset(Host, self.options)
        for host in qs:
            self.assertRegex(host.host, '1')
            self.assertEqual(host.user, 'userlabel222')

        self.reset_options()

    def test_02_get_form_data(self):
        # fails because of missing data
        self.options['form_data'] = 'one=123'
        self.assertRaisesRegex(
            InvalidFormData,
            'This field is required',
            self.manager.get_form_data,
            TestSession,
            self.options)

        # fails because of wrong data-type
        self.options['form_data'] = 'one=123,two="abc"'
        self.assertRaisesRegex(
            InvalidFormData,
            'Enter a whole number',
            self.manager.get_form_data,
            TestSession,
            self.options)

        # fails because of invalid dict-data
        self.options['form_data'] = 'one=123&two="abc"'
        self.assertRaisesRegex(
            InvalidFormData,
            'invalid syntax',
            self.manager.get_form_data,
            TestSession,
            self.options)

        # this should pass
        self.options['form_data'] = 'one=123,two="234"'
        cleaned_data = self.manager.get_form_data(TestSession, self.options)
        self.assertEqual(cleaned_data['one'], 123)
        self.assertEqual(cleaned_data['two'], 234)

        self.reset_options()

    def test_03_invalid_calls(self):
        # list sessions
        with InOut() as out:
            call_command('minke', '--list')
        self.assertIn('DummySession', out)
        self.assertIn('TestFormSession', out)
        self.assertIn('TestUpdateEntriesSession', out)

        # call without model
        with InOut() as out:
            call_command('minke', 'DummySession')
        self.assertRegex(out[0], 'ERROR: No model specified')

        # call without model
        with InOut() as out:
            call_command('minke', 'DummySession')
        self.assertRegex(out[0], 'ERROR: No model specified')

        # call with invalid session
        with InOut() as out:
            call_command('minke', 'Fake')
        self.assertRegex(out[0], 'ERROR: Unknown session')

        # call with invalid model
        with InOut() as out:
            call_command('minke', 'DummySession', 'Fake')
        self.assertRegex(out[0], 'ERROR: Invalid model for')

        # call with invalid url_query
        with InOut() as out:
            call_command('minke', 'DummySession', 'Server', '--url-query=foobar')
        self.assertRegex(out[0], 'ERROR: Incorrect url-query')

    def test_04_valid_calls(self):
        # list sessions
        with InOut() as out:
            call_command('minke', '--list')
        self.assertIn('DummySession', out)
        self.assertIn('TestFormSession', out)
        self.assertIn('TestUpdateEntriesSession', out)

        # valid call
        with InOut() as out:
            call_command('minke', 'DummySession', 'Server', '--no-color')
        self.assertRegex(out[0], 'host_[0-9]{1,2}_label[0-9]{3}')
        self.assertEqual(len(out), 20)

        # valid call without model
        # works if session where registered with only one model
        with InOut() as out:
            call_command('minke', 'SingleModelDummySession', '--no-color')
        self.assertRegex(out[0], 'host_[0-9]{1,2}_label[0-9]{3}')
        self.assertEqual(len(out), 20)

        # valid call with silent-option
        # skips output for successful processes without any messages
        with InOut() as no_out:
            call_command('minke', 'SingleModelDummySession', '--silent')
        self.assertEqual(len(no_out), 0)

        # slicing the queryset with offset and limit
        with InOut() as out_0_10:
            call_command('minke', 'SingleModelDummySession', '--no-color',
                         '--offset=0', '--limit=10')
        self.assertEqual(len(out_0_10), 10)

        # slicing the queryset with offset and limit
        with InOut() as out_10_20:
            call_command('minke', 'SingleModelDummySession', '--no-color',
                         '--offset=10', '--limit=20')
        self.assertEqual(len(out_10_20), 10)
        self.assertListEqual(sorted(out_0_10 + out_10_20), sorted(out))

        # read form-data from stdin
        with InOut('123', '', 'abc', '123') as out:
            call_command('minke', 'TestFormSession', 'Server', '--limit=0')
        self.assertRegex(out[2], 'This field is required')
        self.assertRegex(out[3], 'Enter a whole number')
