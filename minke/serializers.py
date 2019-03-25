# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from rest_framework import serializers

from .models import MinkeSession
from .models import BaseMessage


class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MinkeSession
        fields = ('minkeobj_id', 'session_status', 'proc_status', 'get_html', 'ready')
        read_only_fields = fields
