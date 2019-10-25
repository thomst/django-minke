Minke-models
============

To run sessions with a specific model three conditions must be complied:

* The model must be a subclass of :class:`~.models.MinkeModel`.
* The model's ModelAdmin must be a subclass of :class:`~.admin.MinkeAdmin`.
* And the model must have a connection to a :class:`~.models.Host`.

For minke to be able to run a session for a specific minke-model, it must be
able to associate the model with a host in a distinct way. By default minke
looks for a ``host``-attribute as a OneToOne- or a ManyToOne-relation::

    host = models.ForeignKey(Host, on_delete=models.CASCADE)


It is also possible to work with intermediated models. Assumed you have a
model-structure as follows::

    class Server(MinkeModel):
        host = models.OneToOneField(Host, on_delete=models.CASCADE)
        hostname = models.CharField(max_length=128)


    class Drupal(MinkeModel):
        server = models.ForeignKey(Server, on_delete=models.CASCADE)
        name = models.CharField(max_length=128)
        version = models.CharField(max_length=128)

        HOST_LOOKUP = 'server__host'


    class DrupalModule(MinkeModel):
        drupal = models.ForeignKey(Drupal, on_delete=models.CASCADE)
        name = models.CharField(max_length=128)
        version = models.CharField(max_length=128)

        HOST_LOOKUP = 'drupal__server__host'


To be able to use each of those models as a minke-model, you need to assign
a lookup-string to ``HOST_LOOKUP`` with a format you would also use when
:meth:`filtering a queryset <django.db.models.query.QuerySet.filter>`::

    $ DrupalModul.objects.filter(drupal__server__host=host)
