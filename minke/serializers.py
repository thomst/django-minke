# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from rest_framework import serializers

from .models import BaseSession
from .models import BaseMessage


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BaseMessage
        fields = ('level', 'html')
        read_only_fields = fields


class SessionSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    class Meta:
        model = BaseSession
        fields = ('session_name', 'object_id', 'status', 'proc_status', 'messages')
        read_only_fields = fields
