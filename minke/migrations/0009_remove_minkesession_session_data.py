# Generated by Django 2.2.28 on 2023-04-05 21:57

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('minke', '0008_auto_20230405_2153'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='minkesession',
            name='session_data',
        ),
    ]
