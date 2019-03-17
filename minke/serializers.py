# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from rest_framework import serializers

from .models import SessionData
from .models import MessageData


class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionData
        fields = ('minkeobj_id', 'session_status', 'proc_status', 'get_html', 'ready')
        read_only_fields = fields
