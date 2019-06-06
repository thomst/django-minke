# -*- coding: utf-8 -*-

from django.core.exceptions import FieldError

from rest_framework.response import Response
from rest_framework.generics import ListAPIView
from rest_framework.filters import BaseFilterBackend
from rest_framework.permissions import IsAuthenticated

from .serializers import SessionSerializer
from .exceptions import InvalidURLQuery

from minke.models import MinkeSession


class LookupFilter(BaseFilterBackend):
    """
    Use the url-query as lookup-params.
    """
    def get_lookup_params(self, request):
        params = dict()
        for k, v in request.GET.items():
            if k.endswith('__in'):
                params[k] = v.split(',')
            else:
                params[k] = v
        return params

    def filter_queryset(self, request, queryset, view):
        lookup_params = self.get_lookup_params(request)
        try:
            return queryset.filter(**lookup_params)
        except (FieldError, ValueError):
            msg = 'Invalid lookup-parameter: {}'.format(lookup_params)
            raise InvalidURLQuery(msg)


class UserFilter(BaseFilterBackend):
    """
    Filter sessions by user.
    """
    def filter_queryset(self, request, queryset, view):
        return queryset.filter(user=request.user)


class SessionListAPI(ListAPIView):
    """
    API endpoint to retrieve sessions.
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = SessionSerializer
    filter_backends = (LookupFilter, UserFilter)
    queryset = MinkeSession.objects.prefetch_related('messages')

    def put(self, request, *arg, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        canceled_sessions = list()
        for session in queryset:
            if session.proc_status in ['initialized', 'running']:
                canceled = session.cancel()
                if canceled: canceled_sessions.append(session)

        serializer = self.get_serializer(canceled_sessions, many=True)
        return Response(serializer.data)
