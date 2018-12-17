# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.test import TestCase

from minke.messages import Message
from minke.messages import PreMessage
from minke.messages import TableMessage
from minke.messages import ExecutionMessage
from minke.messages import ExceptionMessage


class MessageTest(TestCase):
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

        class dummy_result:
            return_code = 1
            command = 'foobär'
            stdout = 'foobär-out'
            stderr = unicode()
        message = ExecutionMessage(dummy_result)
        self.assertRegex(message.text, 'foobär')
        self.assertRegex(message.html, 'foobär')

        try: raise Exception('foobär'.encode('utf-8'))
        except: message = ExceptionMessage()
        self.assertRegex(message.text, 'foobär')
        self.assertRegex(message.html, 'foobär')

        try: raise Exception('foobär'.encode('utf-8'))
        except: message = ExceptionMessage(print_tb=True)
        self.assertRegex(message.text, 'foobär')
        self.assertRegex(message.html, 'foobär')
