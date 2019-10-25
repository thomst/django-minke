.. minke documentation master file, created by
   sphinx-quickstart on Sun Sep  8 17:03:36 2019.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to minke's documentation!
=================================

A framework for remote-control- and configuration-management-systems
####################################################################
Minke is a framework that combines the full power of djangos admin-interface
with the reliability and configurability of fabric2. A pure open-source- and
pure python-solution to realize the most different szenarios concerning remote-
control and configuration-managment.

Imagine you just need to setup some managment-commands for a handful of servers -
you can do that with minke. Imagine you have lots of servers with different
setups that you need to group and address seperatly - you can do that with
minke. Imagine you have servers with multiple subsystems installed on each of them
and you not just want to manage those systems but also to track configurations,
version-numbers, installed extensions or modules and to filter for all of those
values within your backend - you can do that with minke.

Features
--------
* full django-admin-site-integration
* parrallel session-execution
* realtime monitoring of executed remote-sessions
* command-line-api using djangos management-commands
* session-history


.. toctree::
   :maxdepth: 1
   :caption: Contents:

   docs/setup
   docs/gettingstarted
   docs/concept
   docs/hosts
   docs/minkemodels
   docs/sessions
   docs/messages
   docs/fabricintegration
   docs/adminsite
   docs/contribcommands
   docs/apicommands

.. toctree::
   :maxdepth: 1
   :caption: Api:

   api/sessions
   api/messages



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
