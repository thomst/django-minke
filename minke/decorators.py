# -*- coding: utf-8 -*-
from __future__ import unicode_literals

def register(models=None,
             short_description=None,
             permission_required=None,
             create_permission=False):
    """
    Register sessions as an admin-action with the associated models:

    @register(MyModel, 'Do something great!')
    class MySession(Session):
        pass
    """
    from minke.sessions import register

    def _session_wrapper(session_cls):
        register(session_cls, models=models,
                 short_description=short_description,
                 permission_required=permission_required,
                 create_permission=create_permission)
        return session_cls
    return _session_wrapper
