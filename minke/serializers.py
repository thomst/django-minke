# -*- coding: utf-8 -*-

from rest_framework import serializers

from .models import MinkeSession
from .models import BaseMessage


class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MinkeSession
        fields = ('minkeobj_id', 'session_status', 'proc_status', 'get_html', 'finished')
        read_only_fields = fields
