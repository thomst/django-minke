# -*- coding: utf-8 -*-

from invoke.runners import Result
from django.test import SimpleTestCase

from minke import sessions
from minke.messages import Message
from minke.messages import PreMessage
from minke.messages import TableMessage
from minke.messages import ExecutionMessage
from minke.messages import ExceptionMessage
from minke.models import CommandResult


class MessageTest(SimpleTestCase):
    def test_01_output(self):
        message = Message('foobär')
        self.assertEqual(message.text, 'foobär')
        self.assertEqual(message.html, 'foobär')
        message = PreMessage('foobär')
        self.assertEqual(message.text, 'foobär')
        self.assertEqual(message.html, '<pre>foobär</pre>')
        message = TableMessage((('foobär',),))
        self.assertEqual(message.text, 'foobär')
        self.assertRegex(message.html, 'foobär')

        result = CommandResult(Result(
            exited=1,
            command='foobär',
            stdout='foobär-out',
            stderr=str()))

        message = ExecutionMessage(result)
        self.assertRegex(message.text, 'foobär')
        self.assertRegex(message.html, 'foobär')

        try: raise Exception('foobär')
        except: message = ExceptionMessage()
        self.assertRegex(message.text, 'foobär')
        self.assertRegex(message.html, 'foobär')

        try: raise Exception('foobär')
        except: message = ExceptionMessage(print_tb=True)
        self.assertRegex(message.text, 'Traceback')
        self.assertRegex(message.html, 'Traceback')
