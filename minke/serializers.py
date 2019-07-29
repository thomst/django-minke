# -*- coding: utf-8 -*-

from rest_framework import serializers

from .models import MinkeSession
from .models import BaseMessage


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BaseMessage
        fields = ('level', 'html')


class CmdMessageSerializer(serializers.Serializer):
    level = serializers.CharField()
    html = serializers.CharField()


class SessionSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    cmd_messages = CmdMessageSerializer(many=True, read_only=True)

    class Meta:
        model = MinkeSession
        fields = ('id', 'minkeobj_id', 'session_status', 'proc_status', \
                  'proc_info', 'messages', 'cmd_messages', 'is_done')
        read_only_fields = fields
