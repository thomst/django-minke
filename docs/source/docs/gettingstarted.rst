Getting started
===============

Install rabbitmq-server as message-broker used by celery (debian)::

    $ apt-get install rabbitmq-server


Install the following python-libraries::

    $ pip install minke-django
    $ pip install django-celery-results


Setup a django-celery-project as described here:

* `First steps with django <https://docs.celeryproject.org/en/latest/django/first-steps-with-django.html>`_


Add the following django-apps to your ``INSTALLED_APPS``::

    INSTALLED_APPS = [
        'minke',
        'rest_framework',
        'django_celery_results',
        'my_minke_app',
        ...
        ...
    ]


Add the following setting-parameters to your *settings.py*::

    CELERY_BROKER_URL = 'amqp://guest:guest@localhost//'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_RESULT_BACKEND = 'django-db'
    CELERY_CACHE_BACKEND = 'django-cache'


Create your first session within *session.py*::

    from minke.models import Host
    from minke.sessions import CommandChainSession


    class ServerInfos(CommandChainSession):
        verbose_name = 'Get informations about the server.'
        work_on = (Host,)
        commands = [
            'lsb_release --all',
            'hostname --long',
            'hostname --ip-address']


Now start your django-development-server...::

    $ python manage.py runserver

...and the celery worker-process::

    $ celery worker --concurrency=8 --events --loglevel=INFO --app my_minke_app


Now you should be able to visit your django-admin-site and create some hosts
pointing to your servers. By default fabric uses your local ssh-agent to
initialize remote-connections. So your minke-app will be able to work on all
those servers you have access to via PubkeyAuthentication.
