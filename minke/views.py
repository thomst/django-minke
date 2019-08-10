# -*- coding: utf-8 -*-

from django.core.exceptions import FieldError
from django.template.loader import render_to_string

from rest_framework.response import Response
from rest_framework.generics import ListAPIView
from rest_framework.filters import BaseFilterBackend
from rest_framework.permissions import IsAuthenticated

from .serializers import SessionSerializer
from .exceptions import InvalidURLQuery
from .models import MinkeSession
from .utils import get_session_summary


class LookupFilter(BaseFilterBackend):
    """
    Use the url-query as lookup-params.
    """
    def get_lookup_params(self, request):
        params = dict()
        for k, v in request.GET.items():
            if k == 'summary': continue
            elif k.endswith('__in'): params[k] = v.split(',')
            else: params[k] = v
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

    def list(self, request, *arg, **kwargs):
        """
        Either return json-formatted sessions or a html-summary-snippet.
        """
        if 'summary' in request.GET:
            sessions = list(self.filter_queryset(self.get_queryset()))
            summary = get_session_summary(sessions)
            context = dict(session_count=summary)
            summary_html = render_to_string('minke/session_summary.html', context)
            return Response(summary_html)
        else:
            return super().list(request, *arg, **kwargs)

    def put(self, request, *arg, **kwargs):
        """
        The put-apicall is used to cancel initialized or running sessions.
        """
        queryset = self.filter_queryset(self.get_queryset())
        for session in queryset:
            if not session.is_done:
                session.cancel()

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
