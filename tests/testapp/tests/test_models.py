# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.test import TestCase

from minke.models import Host, MinkeModel
from minke.exceptions import InvalidMinkeSetup
from ..models import Server, AnySystem


class MinkeModelTest(TestCase):
    fixtures = ['minke.json', 'testapp.json']

    def setUp(self):
        self.host = Host.objects.get(id=1)
        self.server = Server.objects.get(id=1)
        self.anysystem = AnySystem.objects.get(id=1)

    def test_01_get_host(self):
        server_host = self.server.get_host()
        system_host = self.anysystem.get_host()
        self.assertTrue(type(server_host) == Host)
        self.assertTrue(type(system_host) == Host)

        # invalid MinkeModel
        class InvalidModel(MinkeModel):
            HOST_LOOKUP = 'no__host'

        # host-lookup should fail with InvalidMinkeSetup
        invalid_model = InvalidModel()
        self.assertRaises(InvalidMinkeSetup, invalid_model.get_host)

    def test_02_lock_host(self):
        host_id = self.host.id
        self.assertTrue(Host.objects.get_lock(id=host_id))
        self.assertFalse(Host.objects.get_lock(id=host_id))
        Host.objects.release_lock(id=host_id)
        self.assertFalse(self.host.locked)
