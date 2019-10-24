================
Welcome to Minke
================
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

Concept
-------
The main idea of minke is to define an arbitrary data-structure that represents
your server- and subsystem-landscape as django-models. And then be able to
run specific remote-tasks for those models right out of their changelist-sites.
Now those tasks could be anything about remote-control and system-managment, but
also fetching relevant data to update your django-data-structure itself.

To make this possible there are three main elements:

* hosts,
* minke-models,
* and sessions.

Hosts
.....
A Host is a django-model that is basically the database-representation of a
specific ssh-config. It holds every information needed by fabric to connect
to the remote-system.

Minke-Models
............
Minke-models now are all those models that you want to run remote-sessions with.
This could be the data-representation of a server, but also of web-applications
running on this server, and even something like installed extensions, patches,
backups and everything else you want to track and manage in your minke-app.

Sessions
........
A session-class defines the code to be executed for minke-models. Sessions are
similar fabric-tasks. Within a session you have access to a connection-object
(as implemented by fabric) as well as to the minke-model-object you are working
with. So a session could be as simple as running a single shell-command on the
remote-machine, up to complex management-routines including manipulating the
data of the minke-model-object itself.
