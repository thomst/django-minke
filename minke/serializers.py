# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from rest_framework import serializers

from .models import BaseSession
from .models import BaseMessage


class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BaseSession
        fields = ('object_id', 'status', 'proc_status', 'get_html', 'ready')
        read_only_fields = fields
