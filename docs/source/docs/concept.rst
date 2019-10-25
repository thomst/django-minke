Concept
=======

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

:doc:`Read more about hosts.<hosts>`

Minke-Models
............
Minke-models now are all those models that you want to run remote-sessions with.
This could be the data-representation of a server, but also of web-applications
running on this server, and even something like installed extensions, patches,
backups and everything else you want to track and manage in your minke-app.

:doc:`Read more about minke-models.<minkemodels>`

Sessions
........
A session-class defines the code to be executed for minke-models. Sessions are
similar to fabric-tasks. Within a session you have access to a connection-object
(as implemented by fabric) as well as to the minke-model-object you are working
with. So a session could be as simple as running a single shell-command on the
remote-machine, up to complex management-routines including manipulating the
data of the minke-model-object itself.

:doc:`Read more about sessions.<sessions>`
