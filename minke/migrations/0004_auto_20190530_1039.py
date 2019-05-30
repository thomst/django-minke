# Generated by Django 2.1.7 on 2019-05-30 10:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('minke', '0003_auto_20190326_1648'),
    ]

    operations = [
        migrations.AddField(
            model_name='minkesession',
            name='task_id',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AlterField(
            model_name='minkesession',
            name='proc_status',
            field=models.CharField(choices=[('initialized', 'waiting...'), ('running', 'running...'), ('succeeded', 'succeeded in {0:.1f} seconds'), ('stopping', 'stopping...'), ('stopped', 'stopped after {0:.1f} seconds'), ('canceled', 'canceled!'), ('failed', 'failed!')], max_length=128),
        ),
        migrations.AlterField(
            model_name='minkesession',
            name='session_status',
            field=models.CharField(choices=[('success', 0), ('warning', 1), ('error', 2)], max_length=128),
        ),
    ]
