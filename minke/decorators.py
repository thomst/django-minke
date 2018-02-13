
def register(models=None, short_description=None):
    """
    Register a Minke-Session to be used as an admin-action with the associated
    models:
    @register(Server, 'Update server-objects')
    class MySession(Session):
        pass
    """
    def _session_wrapper(session_cls):
        import minke.engine
        minke.engine.register(session_cls, models, short_description)
        return session_cls
    return _session_wrapper
