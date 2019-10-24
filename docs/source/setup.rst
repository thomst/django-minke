Installation and Setup
======================

Installation
------------
To install django-minke and all its dependencies use pip::

    $ pip install django-minke

The dependencies are:

* `Django <https://www.djangoproject.com>`_ (>=1.11)
* `celery <http://www.celeryproject.org>`_ (>=4.2.2)
* `fabric2 <https://www.fabfile.org>`_ (>=2.4.0)
* `djangorestframework <https://www.django-rest-framework.org>`_ (>=3.9.2)


Setup
-----

Django
......
Minke is build as a django-application. For more informations about how to setup
a django-project please see the django-documentation:

* `Getting started with django <https://www.djangoproject.com/start/>`_

Celery
......
Minke uses celery to realize asynchrouniously and parrallel task-execution.
For more informations about how to setup a django-project with celery please
see the celery-documentation:

* `Getting started with celery <https://docs.celeryproject.org/en/latest/getting-started/index.html>`_
* `Using celery with django <https://docs.celeryproject.org/en/latest/django/index.html>`_

.. note::

    Minke depends on a celery-setup with a working result-backend. We recommend
    to use the django-celery-result-extension:

    * `General informations about result-backends <https://docs.celeryproject.org/en/latest/getting-started/first-steps-with-celery.html#keeping-results>`_
    * `django-celery-result <http://docs.celeryproject.org/en/latest/django/first-steps-with-django.html#django-celery-results-using-the-django-orm-cache-as-a-result-backend>`_

Fabric
......
Minke uses fabric to realize remote-execution. Fabric itself is build on invoke
(command-execution) and paramiko (ssh-connections). Fabric and invoke
are highly configurable. Please see :doc:`../fabricintegration` for more
informations about how to configure fabric within a minke-project.
