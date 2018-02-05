
def register(models=list(), short_description=None):
    """
    Register a Minke-Session to be used as an admin-action with the associated
    models:
    @register(Server, Environment)
    class MySession(Session):
        pass
    """

    if not type(models) == list:
        models = [models]

    def _session_wrapper(session_cls):
        from .engine import register

        if models:
            session_cls.models = session_cls.models + models

        if short_description:
            session_cls.short_description = short_description

        register(session_cls)
        return session_cls
    return _session_wrapper
