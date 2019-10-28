# -*- coding: utf-8 -*-

from django.test import TestCase

from minke.models import Host, MinkeModel
from minke.exceptions import InvalidMinkeSetup
from ..models import AnySystem
from .utils import create_hosts
from .utils import create_players


class MinkeModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_hosts()
        create_players()

    def setUp(self):
        self.anysystem = AnySystem.objects.all()[0]
        self.server = self.anysystem.server
        self.host = self.server.host

    def test_01_get_host(self):
        host = self.host.get_host()
        server_host = self.server.get_host()
        system_host = self.anysystem.get_host()
        self.assertTrue(type(host) == Host)
        self.assertTrue(type(server_host) == Host)
        self.assertTrue(type(system_host) == Host)

        # invalid MinkeModel
        class InvalidModel(MinkeModel):
            HOST_LOOKUP = 'no__host'

        # host-lookup should fail with InvalidMinkeSetup
        invalid_model = InvalidModel()
        self.assertRaises(InvalidMinkeSetup, invalid_model.get_host)
