
def register(models=list(), short_description=None):
    """
    Register a Minke-Session to be used as an admin-action with the associated
    models:
    @register(Server, 'Update server-objects')
    class MySession(Session):
        pass
    """
    def _session_wrapper(session_cls):
        from .engine import register
        register(session_cls, models, short_description)
        return session_cls
    return _session_wrapper
