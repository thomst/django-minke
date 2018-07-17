# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.test import TestCase

from minke.messages import Message


class MessageTest(TestCase):
    def test_01_set_level(self):
        message = Message(dict(), 'error')
        self.assertEqual(message.level, 'error')
        message = Message(dict(), 'ERROR')
        self.assertEqual(message.level, 'error')
        message = Message(dict(), Message.ERROR)
        self.assertEqual(message.level, 'error')
        message = Message(dict(), False)
        self.assertEqual(message.level, 'error')
        message = Message(dict(), True)
        self.assertEqual(message.level, 'info')
