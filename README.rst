=====
Minke
=====
####################################################################
A framework for remote-control- and configuration-management-systems
####################################################################

Minke is a framework that combines the full power of djangos admin-interface
with the reliability and configurability of fabric2. A pure open-source- and
pure python-solution to realize the most different szenarios concerning remote-
control and configuration-managment.

Guess you just need to setup some managment-commands for a handful of servers -
you can do that with minke. Guess you have lots of servers with different
setups that you need to group and address seperatly - you can do that with
minke. Guess you have servers with multiple subsystems installed on each of them
and you not just want to manage those systems but also to track configurations,
version-numbers, installed extensions or modules and to filter for all of those
values within your backend - you can do that with minke.

Minke features:
---------------
* full django-admin-site-integration

* parrallel ssh-connections and code-execution using celery

* realtime monitoring of executed tasks

* extensive support of fabric2- and invoke-configurations
