# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.test import TestCase
from django.test import Client

from minke import sessions
from minke.utils import UnicodeResult
from minke.sessions import register
from minke.sessions import Session
from minke.sessions import UpdateEntriesSession
from minke.exceptions import InvalidMinkeSetup
from minke.models import Host
from minke.engine import process
from ..models import Server
from .utils import create_test_data


class SessionTest(TestCase):
    def setUp(self):
        pass
        # create_test_data()
        # self.client = Client()

    def test_01_change_list(self):
        pass
